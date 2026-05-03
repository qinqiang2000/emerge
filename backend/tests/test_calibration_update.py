import io

import pytest
from sqlalchemy import select

from app.engine.recompute import record_human_verdict_pair
from app.engine.score import JudgeVerdict
from app.models.judge_calibration import JudgeCalibration


@pytest.mark.asyncio
async def test_record_pair_increments_fp_when_judge_up_human_down(db_session):
    from app.models.project import Project
    from app.models.user import User
    from app.models.workspace import Workspace

    user = User(email="cu@cu.com", password_hash="x")
    db_session.add(user)
    await db_session.flush()
    ws = Workspace(name="W", owner_id=user.id)
    db_session.add(ws)
    await db_session.flush()
    p = Project(workspace_id=ws.id, name="P", created_by=user.id)
    db_session.add(p)
    await db_session.commit()

    await record_human_verdict_pair(
        session=db_session,
        project_id=p.id,
        judge_model_version="m",
        judge_verdict=JudgeVerdict.UP,
        human_fixed=True,
    )
    await record_human_verdict_pair(
        session=db_session,
        project_id=p.id,
        judge_model_version="m",
        judge_verdict=JudgeVerdict.UP,
        human_fixed=False,
    )

    cal = (
        await db_session.execute(
            select(JudgeCalibration).where(JudgeCalibration.project_id == p.id)
        )
    ).scalar_one()
    assert cal.tp == 1
    assert cal.fp == 1
    assert cal.observation_count == 2


@pytest.mark.asyncio
async def test_annotation_save_updates_calibration(client, db_session, tmp_path, monkeypatch):
    monkeypatch.setattr("app.services.storage.settings.storage_root", str(tmp_path))
    await client.post("/api/v1/auth/register", json={"email": "ua@ua.com", "password": "hunter22"})
    tok = (
        await client.post("/api/v1/auth/login", json={"email": "ua@ua.com", "password": "hunter22"})
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

    from app.models.prediction import Prediction, PredictionStatus

    pred = Prediction(
        document_id=did,
        model_id="m",
        prompt_hash="h",
        output=[{"shop_name": "ABC"}],
        per_field_confidence={"0": {"shop_name": "up"}},
        status=PredictionStatus.SUCCESS.value,
    )
    db_session.add(pred)
    await db_session.commit()

    await client.post(
        f"/api/v1/projects/{pid}/documents/{did}/annotations",
        json={"output": [{"shop_name": "DEF"}], "parent_prediction_id": pred.id},
        headers=h,
    )

    cal = (
        await db_session.execute(select(JudgeCalibration).where(JudgeCalibration.project_id == pid))
    ).scalar_one()
    assert cal.fp == 1
    assert cal.tp == 0
