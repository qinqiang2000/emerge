import io

import pytest

from app.models.annotation import Annotation, AnnotationRole, AnnotationStatus
from app.models.prediction import Prediction, PredictionStatus
from sqlalchemy import select


@pytest.mark.asyncio
async def test_counterexample_list_excludes_role_none_and_cancelled(
    client, db_session, tmp_path, monkeypatch
):
    monkeypatch.setattr("app.services.storage.settings.storage_root", str(tmp_path))
    await client.post("/api/v1/auth/register", json={"email": "ce@ce.com", "password": "hunter22"})
    tok = (
        await client.post("/api/v1/auth/login", json={"email": "ce@ce.com", "password": "hunter22"})
    ).json()["access_token"]
    h = {"Authorization": f"Bearer {tok}"}
    pid = (await client.post("/api/v1/projects", json={"name": "P"}, headers=h)).json()["id"]
    did = (
        await client.post(
            f"/api/v1/projects/{pid}/documents",
            files=[("files", ("a.pdf", io.BytesIO(b"A"), "application/pdf"))],
            headers=h,
        )
    ).json()[0]["id"]

    # save a regular correction (role=none)
    await client.post(
        f"/api/v1/projects/{pid}/documents/{did}/annotations",
        json={"output": [{"a": 1}]},
        headers=h,
    )

    # seed a Prediction + a counterexample directly
    from app.models.user import User

    user_id = (await db_session.execute(select(User))).scalar_one().id
    pred = Prediction(
        document_id=did,
        model_id="m",
        prompt_hash="h",
        output=[{"a": 1}],
        per_field_confidence={},
        status=PredictionStatus.SUCCESS.value,
    )
    db_session.add(pred)
    await db_session.flush()
    db_session.add(
        Annotation(
            document_id=did,
            parent_prediction_id=pred.id,
            output=[{"a": 99}],
            role=AnnotationRole.COUNTEREXAMPLE.value,
            status=AnnotationStatus.SAVED.value,
            created_by=user_id,
            last_modified_by=user_id,
        )
    )
    db_session.add(
        Annotation(
            document_id=did,
            parent_prediction_id=pred.id,
            output=[{"a": 88}],
            role=AnnotationRole.COUNTEREXAMPLE.value,
            status=AnnotationStatus.CANCELLED.value,
            created_by=user_id,
            last_modified_by=user_id,
        )
    )
    await db_session.commit()

    resp = await client.get(f"/api/v1/projects/{pid}/counterexamples", headers=h)
    assert resp.status_code == 200
    rows = resp.json()
    assert len(rows) == 1
    assert rows[0]["output"] == [{"a": 99}]
    assert rows[0]["role"] == "counterexample"


@pytest.mark.asyncio
async def test_create_counterexample_endpoint(client, db_session, tmp_path, monkeypatch):
    monkeypatch.setattr("app.services.storage.settings.storage_root", str(tmp_path))
    await client.post("/api/v1/auth/register", json={"email": "f@f.com", "password": "hunter22"})
    tok = (
        await client.post("/api/v1/auth/login", json={"email": "f@f.com", "password": "hunter22"})
    ).json()["access_token"]
    h = {"Authorization": f"Bearer {tok}"}
    pid = (await client.post("/api/v1/projects", json={"name": "P"}, headers=h)).json()["id"]
    did = (
        await client.post(
            f"/api/v1/projects/{pid}/documents",
            files=[("files", ("a.pdf", io.BytesIO(b"A"), "application/pdf"))],
            headers=h,
        )
    ).json()[0]["id"]
    # seed a prediction
    from app.models.prediction import Prediction, PredictionStatus

    pred = Prediction(
        document_id=did,
        model_id="m",
        prompt_hash="h",
        output=[{"a": 1}],
        per_field_confidence={},
        status=PredictionStatus.SUCCESS.value,
    )
    db_session.add(pred)
    await db_session.commit()

    resp = await client.post(
        f"/api/v1/projects/{pid}/counterexamples",
        json={"request_id": pred.id, "correct_output": [{"a": 99}]},
        headers=h,
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["role"] == "counterexample"
    assert body["parent_prediction_id"] == pred.id
