import io
from datetime import UTC, datetime

import pytest
from sqlalchemy import select

from app.engine.providers import get_provider_dep
from app.engine.providers.fake import FakeProvider
from app.models.api_key import ApiKey
from app.models.project import Project
from app.services.api_key import parse_prefix
from tests.conftest import _setup_published_project


@pytest.mark.asyncio
async def test_extract_returns_entities(client, db_session, app, tmp_path, monkeypatch):
    api_code, key = await _setup_published_project(client, db_session, monkeypatch, tmp_path)

    fake = FakeProvider(canned=[[{"shop_name": "ABC"}]])
    app.dependency_overrides[get_provider_dep] = lambda: fake

    resp = await client.post(
        f"/extract/{api_code}",
        files=[("file", ("a.pdf", io.BytesIO(b"PDF"), "application/pdf"))],
        headers={"X-Api-Key": key},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["entities"] == [{"shop_name": "ABC"}]
    assert "prediction_id" in body
    assert "project_version" in body


@pytest.mark.asyncio
async def test_extract_missing_key_401(client, db_session, monkeypatch, tmp_path):
    api_code, _ = await _setup_published_project(client, db_session, monkeypatch, tmp_path)
    resp = await client.post(
        f"/extract/{api_code}",
        files=[("file", ("a.pdf", io.BytesIO(b"PDF"), "application/pdf"))],
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_extract_unknown_api_code_404(client):
    resp = await client.post(
        "/extract/nonexistent",
        files=[("file", ("a.pdf", io.BytesIO(b"PDF"), "application/pdf"))],
        headers={"X-Api-Key": "ek_DEADBEEF-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"},
    )
    # Resolve runs before auth — unknown api_code is always 404, never 401.
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_extract_after_unpublish_returns_403(client, db_session, monkeypatch, tmp_path):
    """Spec §7.2: unpublish → 403 (paused), distinct from 404 (unknown api_code)."""
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

    resp = await client.post(
        f"/extract/{api_code}",
        files=[("file", ("a.pdf", io.BytesIO(b"PDF"), "application/pdf"))],
        headers={"X-Api-Key": key},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_extract_with_revoked_key_401(client, db_session, app, tmp_path, monkeypatch):
    """Revoked (soft-deleted) keys must be rejected."""
    api_code, key = await _setup_published_project(client, db_session, monkeypatch, tmp_path)
    # find the key and soft-delete it
    prefix = parse_prefix(key)
    row = (
        await db_session.execute(select(ApiKey).where(ApiKey.prefix == prefix))
    ).scalar_one()
    row.deleted_at = datetime.now(tz=UTC)
    await db_session.commit()

    resp = await client.post(
        f"/extract/{api_code}",
        files=[("file", ("a.pdf", io.BytesIO(b"PDF"), "application/pdf"))],
        headers={"X-Api-Key": key},
    )
    assert resp.status_code == 401
