import io

import pytest


async def _setup_published_project(client, db_session, monkeypatch, tmp_path) -> tuple[str, str]:
    """Returns (api_code, api_key) for a published project with a locked active version."""
    monkeypatch.setattr("app.services.storage.settings.storage_root", str(tmp_path))
    await client.post("/api/v1/auth/register", json={"email": "px@px.com", "password": "hunter22"})
    tok = (
        await client.post("/api/v1/auth/login", json={"email": "px@px.com", "password": "hunter22"})
    ).json()["access_token"]
    h = {"Authorization": f"Bearer {tok}"}
    pid = (await client.post("/api/v1/projects", json={"name": "P"}, headers=h)).json()["id"]
    await client.patch(
        f"/api/v1/projects/{pid}/schema",
        json={
            "schema": [{"name": "shop_name", "type": "string", "description": "店名"}],
            "global_notes": "",
            "model_id": "m",
        },
        headers=h,
    )
    from app.models.project import Project
    from app.models.project_version import ProjectVersion
    from sqlalchemy import select

    proj = (await db_session.execute(select(Project).where(Project.id == pid))).scalar_one()
    v = (
        await db_session.execute(
            select(ProjectVersion).where(ProjectVersion.id == proj.active_version_id)
        )
    ).scalar_one()
    v.locked = True
    await db_session.commit()

    await client.post(
        f"/api/v1/projects/{pid}/publish", json={"api_code": "test-receipts"}, headers=h
    )
    key = (
        await client.post(
            f"/api/v1/projects/{pid}/api-keys", json={"name": "default"}, headers=h
        )
    ).json()["key"]
    return "test-receipts", key


@pytest.mark.asyncio
async def test_extract_returns_entities(client, db_session, app, tmp_path, monkeypatch):
    api_code, key = await _setup_published_project(client, db_session, monkeypatch, tmp_path)

    from app.engine.providers import get_provider_dep
    from app.engine.providers.fake import FakeProvider

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
    assert resp.status_code in (401, 404)


@pytest.mark.asyncio
async def test_extract_after_unpublish_returns_404(client, db_session, monkeypatch, tmp_path):
    api_code, key = await _setup_published_project(client, db_session, monkeypatch, tmp_path)
    tok = (
        await client.post(
            "/api/v1/auth/login", json={"email": "px@px.com", "password": "hunter22"}
        )
    ).json()["access_token"]
    h = {"Authorization": f"Bearer {tok}"}
    from app.models.project import Project
    from sqlalchemy import select

    pid = (
        await db_session.execute(select(Project).where(Project.api_code == api_code))
    ).scalar_one().id
    await client.post(f"/api/v1/projects/{pid}/unpublish", headers=h)

    resp = await client.post(
        f"/extract/{api_code}",
        files=[("file", ("a.pdf", io.BytesIO(b"PDF"), "application/pdf"))],
        headers={"X-Api-Key": key},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_extract_with_revoked_key_401(client, db_session, app, tmp_path, monkeypatch):
    """Revoked (soft-deleted) keys must be rejected."""
    api_code, key = await _setup_published_project(client, db_session, monkeypatch, tmp_path)
    # find the key and soft-delete it
    from app.models.api_key import ApiKey
    from app.services.api_key import parse_prefix
    from datetime import datetime, timezone
    from sqlalchemy import select
    prefix = parse_prefix(key)
    row = (
        await db_session.execute(select(ApiKey).where(ApiKey.prefix == prefix))
    ).scalar_one()
    row.deleted_at = datetime.now(tz=timezone.utc)
    await db_session.commit()

    resp = await client.post(
        f"/extract/{api_code}",
        files=[("file", ("a.pdf", io.BytesIO(b"PDF"), "application/pdf"))],
        headers={"X-Api-Key": key},
    )
    assert resp.status_code == 401
