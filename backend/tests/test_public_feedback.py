import io

import pytest
from sqlalchemy import select

from app.engine.providers import get_provider_dep
from app.engine.providers.fake import FakeProvider
from app.models.annotation import Annotation, AnnotationRole
from app.models.project import Project
from tests.conftest import _setup_published_project


@pytest.mark.asyncio
async def test_public_feedback_creates_counterexample(client, db_session, app, tmp_path, monkeypatch):
    api_code, key = await _setup_published_project(client, db_session, monkeypatch, tmp_path)

    fake = FakeProvider(canned=[[{"shop_name": "WRONG"}]])
    app.dependency_overrides[get_provider_dep] = lambda: fake

    extract_resp = await client.post(
        f"/extract/{api_code}",
        files=[("file", ("a.pdf", io.BytesIO(b"PDF"), "application/pdf"))],
        headers={"X-Api-Key": key},
    )
    assert extract_resp.status_code == 200, extract_resp.text
    pred_id = extract_resp.json()["prediction_id"]

    fb = await client.post(
        f"/extract/{api_code}/feedback",
        json={"request_id": pred_id, "correct_output": [{"shop_name": "RIGHT"}]},
        headers={"X-Api-Key": key},
    )
    assert fb.status_code == 200, fb.text
    body = fb.json()
    assert "counterexample_id" in body

    # verify a counterexample row exists
    rows = (
        await db_session.execute(
            select(Annotation).where(Annotation.role == AnnotationRole.COUNTEREXAMPLE.value)
        )
    ).scalars().all()
    assert len(rows) == 1
    assert rows[0].output == [{"shop_name": "RIGHT"}]


@pytest.mark.asyncio
async def test_feedback_with_mismatched_prediction_returns_422(client, db_session, app, tmp_path, monkeypatch):
    api_code, key = await _setup_published_project(client, db_session, monkeypatch, tmp_path)
    fb = await client.post(
        f"/extract/{api_code}/feedback",
        json={"request_id": 999_999, "correct_output": [{"x": 1}]},
        headers={"X-Api-Key": key},
    )
    assert fb.status_code == 422


@pytest.mark.asyncio
async def test_feedback_unknown_api_code_404(client):
    """Resolve runs before auth — unknown api_code is always 404."""
    fb = await client.post(
        "/extract/nonexistent/feedback",
        json={"request_id": 1, "correct_output": [{"x": 1}]},
        headers={"X-Api-Key": "ek_DEADBEEF-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"},
    )
    assert fb.status_code == 404


@pytest.mark.asyncio
async def test_feedback_missing_key_401(client, db_session, monkeypatch, tmp_path):
    api_code, _ = await _setup_published_project(client, db_session, monkeypatch, tmp_path)
    fb = await client.post(
        f"/extract/{api_code}/feedback",
        json={"request_id": 1, "correct_output": [{"x": 1}]},
    )
    assert fb.status_code == 401


@pytest.mark.asyncio
async def test_feedback_after_unpublish_returns_403(client, db_session, monkeypatch, tmp_path):
    """Spec §7.2: feedback follows the same 403/404 distinction as extract."""
    api_code, key = await _setup_published_project(client, db_session, monkeypatch, tmp_path)
    tok = (
        await client.post(
            "/api/v1/auth/login", json={"email": "px@px.com", "password": "hunter22"}
        )
    ).json()["access_token"]
    h = {"Authorization": f"Bearer {tok}"}
    pid = (
        await db_session.execute(select(Project).where(Project.api_code == api_code))
    ).scalar_one().id
    await client.post(f"/api/v1/projects/{pid}/unpublish", headers=h)

    fb = await client.post(
        f"/extract/{api_code}/feedback",
        json={"request_id": 1, "correct_output": [{"x": 1}]},
        headers={"X-Api-Key": key},
    )
    assert fb.status_code == 403


@pytest.mark.asyncio
async def test_public_feedback_accepts_partial_field_corrections(
    client, db_session, app, tmp_path, monkeypatch
):
    """Partial feedback: client patches single fields without resending full output."""
    api_code, key = await _setup_published_project(client, db_session, monkeypatch, tmp_path)

    fake = FakeProvider(canned=[[{"shop_name": "WRONG", "total": 1000}]])
    app.dependency_overrides[get_provider_dep] = lambda: fake
    extract_resp = await client.post(
        f"/extract/{api_code}",
        files=[("file", ("a.pdf", io.BytesIO(b"PDF"), "application/pdf"))],
        headers={"X-Api-Key": key},
    )
    pred_id = extract_resp.json()["prediction_id"]

    fb = await client.post(
        f"/extract/{api_code}/feedback",
        json={
            "request_id": pred_id,
            "corrections": [
                {
                    "entity_index": 0,
                    "field_path": "total",
                    "correct_value": 1234,
                    "comment": "model picked subtotal",
                }
            ],
        },
        headers={"X-Api-Key": key},
    )
    assert fb.status_code in (200, 201), fb.text
    rows = (
        await db_session.execute(
            select(Annotation).where(Annotation.role == AnnotationRole.COUNTEREXAMPLE.value)
        )
    ).scalars().all()
    assert len(rows) == 1
    # Merged output: original WRONG/1000 patched to 1234.
    assert rows[0].output == [{"shop_name": "WRONG", "total": 1234}]


@pytest.mark.asyncio
async def test_public_feedback_partial_supports_nested_paths(
    client, db_session, app, tmp_path, monkeypatch
):
    api_code, key = await _setup_published_project(client, db_session, monkeypatch, tmp_path)

    fake = FakeProvider(canned=[[{"line_items": [{"name": "A", "price": 1}, {"name": "B", "price": 2}]}]])
    app.dependency_overrides[get_provider_dep] = lambda: fake
    extract_resp = await client.post(
        f"/extract/{api_code}",
        files=[("file", ("a.pdf", io.BytesIO(b"PDF"), "application/pdf"))],
        headers={"X-Api-Key": key},
    )
    pred_id = extract_resp.json()["prediction_id"]

    fb = await client.post(
        f"/extract/{api_code}/feedback",
        json={
            "request_id": pred_id,
            "corrections": [
                {"entity_index": 0, "field_path": "line_items[1].price", "correct_value": 99}
            ],
        },
        headers={"X-Api-Key": key},
    )
    assert fb.status_code in (200, 201), fb.text
    rows = (
        await db_session.execute(
            select(Annotation).where(Annotation.role == AnnotationRole.COUNTEREXAMPLE.value)
        )
    ).scalars().all()
    assert len(rows) == 1
    assert rows[0].output[0]["line_items"][1]["price"] == 99


@pytest.mark.asyncio
async def test_public_feedback_partial_invalid_path_returns_422(
    client, db_session, app, tmp_path, monkeypatch
):
    api_code, key = await _setup_published_project(client, db_session, monkeypatch, tmp_path)

    fake = FakeProvider(canned=[[{"total": 1}]])
    app.dependency_overrides[get_provider_dep] = lambda: fake
    extract_resp = await client.post(
        f"/extract/{api_code}",
        files=[("file", ("a.pdf", io.BytesIO(b"PDF"), "application/pdf"))],
        headers={"X-Api-Key": key},
    )
    pred_id = extract_resp.json()["prediction_id"]

    fb = await client.post(
        f"/extract/{api_code}/feedback",
        json={
            "request_id": pred_id,
            "corrections": [
                {"entity_index": 5, "field_path": "total", "correct_value": 1}
            ],
        },
        headers={"X-Api-Key": key},
    )
    assert fb.status_code == 422


@pytest.mark.asyncio
async def test_public_feedback_requires_full_or_partial(
    client, db_session, monkeypatch, tmp_path
):
    api_code, key = await _setup_published_project(client, db_session, monkeypatch, tmp_path)
    fb = await client.post(
        f"/extract/{api_code}/feedback",
        json={"request_id": 1},
        headers={"X-Api-Key": key},
    )
    assert fb.status_code == 422
