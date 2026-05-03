import pytest


async def _auth_and_project(client, email="pb@pb.com") -> tuple[dict, int]:
    await client.post("/api/v1/auth/register", json={"email": email, "password": "hunter22"})
    tok = (
        await client.post("/api/v1/auth/login", json={"email": email, "password": "hunter22"})
    ).json()["access_token"]
    h = {"Authorization": f"Bearer {tok}"}
    pid = (await client.post("/api/v1/projects", json={"name": "P"}, headers=h)).json()["id"]
    return h, pid


@pytest.mark.asyncio
async def test_publish_requires_locked_version(client):
    h, pid = await _auth_and_project(client, "rl@rl.com")
    resp = await client.post(
        f"/api/v1/projects/{pid}/publish", json={"api_code": "ja-rcpt"}, headers=h
    )
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_publish_succeeds_after_lock(client, db_session):
    h, pid = await _auth_and_project(client, "pl@pl.com")
    await client.patch(
        f"/api/v1/projects/{pid}/schema",
        json={
            "schema": [{"name": "shop_name", "type": "string", "description": "店名"}],
            "global_notes": "",
            "model_id": "m",
        },
        headers=h,
    )
    # bypass lock invariants for speed: directly flip the version's `locked` flag
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

    resp = await client.post(
        f"/api/v1/projects/{pid}/publish", json={"api_code": "ja-rcpt"}, headers=h
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["api_code"] == "ja-rcpt"
    assert body["api_published_at"] is not None


@pytest.mark.asyncio
async def test_unpublish_keeps_api_code_clears_published_at(client, db_session):
    """Unpublish pauses the API but keeps the api_code claimed in the workspace.
    Spec §7.2: this lets the public route distinguish 403 (paused) from 404 (unknown)."""
    h, pid = await _auth_and_project(client, "up@up.com")
    from app.models.project import Project
    from sqlalchemy import select
    proj = (await db_session.execute(select(Project).where(Project.id == pid))).scalar_one()
    proj.api_code = "to-unpub"
    from datetime import datetime, timezone
    proj.api_published_at = datetime.now(tz=timezone.utc)
    await db_session.commit()

    resp = await client.post(f"/api/v1/projects/{pid}/unpublish", headers=h)
    assert resp.status_code == 200
    body = resp.json()
    assert body["api_code"] == "to-unpub"
    assert body["api_published_at"] is None


@pytest.mark.asyncio
async def test_create_api_key_returns_plaintext_once(client):
    h, pid = await _auth_and_project(client, "ak@ak.com")
    resp = await client.post(
        f"/api/v1/projects/{pid}/api-keys", json={"name": "default"}, headers=h
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["key"].startswith("ek_")
    assert "key_hash" not in body
    assert body["name"] == "default"

    listing = (await client.get(f"/api/v1/projects/{pid}/api-keys", headers=h)).json()
    assert len(listing) == 1
    assert "key" not in listing[0]
    assert listing[0]["prefix"] == body["prefix"]


@pytest.mark.asyncio
async def test_revoke_api_key_soft_deletes(client, db_session):
    h, pid = await _auth_and_project(client, "rk@rk.com")
    body = (
        await client.post(f"/api/v1/projects/{pid}/api-keys", json={"name": "x"}, headers=h)
    ).json()
    kid = body["id"]
    resp = await client.delete(f"/api/v1/projects/{pid}/api-keys/{kid}", headers=h)
    assert resp.status_code == 200
    listing = (await client.get(f"/api/v1/projects/{pid}/api-keys", headers=h)).json()
    assert listing == []
    # Second DELETE: soft-deleted resource is gone, must 404 not 200.
    second = await client.delete(f"/api/v1/projects/{pid}/api-keys/{kid}", headers=h)
    assert second.status_code == 404


@pytest.mark.asyncio
async def test_api_code_unique_per_workspace(client, db_session):
    h, pid = await _auth_and_project(client, "uq@uq.com")
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

    r1 = await client.post(
        f"/api/v1/projects/{pid}/publish", json={"api_code": "shared-code"}, headers=h
    )
    assert r1.status_code == 200, r1.text

    pid2 = (await client.post("/api/v1/projects", json={"name": "P2"}, headers=h)).json()["id"]
    proj2 = (await db_session.execute(select(Project).where(Project.id == pid2))).scalar_one()
    v2 = (
        await db_session.execute(
            select(ProjectVersion).where(ProjectVersion.id == proj2.active_version_id)
        )
    ).scalar_one()
    v2.locked = True
    await db_session.commit()

    r2 = await client.post(
        f"/api/v1/projects/{pid2}/publish", json={"api_code": "shared-code"}, headers=h
    )
    assert r2.status_code == 409


@pytest.mark.asyncio
async def test_publish_invalid_api_code_validation(client):
    h, pid = await _auth_and_project(client, "inv@inv.com")
    resp = await client.post(
        f"/api/v1/projects/{pid}/publish", json={"api_code": "Bad Code With Spaces"}, headers=h
    )
    assert resp.status_code == 422
