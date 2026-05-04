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


async def _patch_and_lock(client, db_session, pid: int, headers, schema=None):
    """Patch schema, lock the new ProjectVersion, return (project, version).

    Tests need multiple locked versions on a single project; the schema PATCH
    route 409s when parent is locked, so we temporarily unlock the parent,
    PATCH, then re-lock both. The product flow uses unlock/lock UI gestures.
    """
    from app.models.project import Project
    from app.models.project_version import ProjectVersion
    from sqlalchemy import select

    proj = (await db_session.execute(select(Project).where(Project.id == pid))).scalar_one()
    parent = None
    if proj.active_version_id is not None:
        parent = (
            await db_session.execute(
                select(ProjectVersion).where(ProjectVersion.id == proj.active_version_id)
            )
        ).scalar_one()
        if parent.locked:
            parent.locked = False
            await db_session.commit()

    res = await client.patch(
        f"/api/v1/projects/{pid}/schema",
        json={
            "schema": schema or [{"name": "shop_name", "type": "string", "description": "店名"}],
            "global_notes": "",
            "model_id": "m",
        },
        headers=headers,
    )
    assert res.status_code == 200, res.text
    proj = (await db_session.execute(select(Project).where(Project.id == pid))).scalar_one()
    v = (
        await db_session.execute(
            select(ProjectVersion).where(ProjectVersion.id == proj.active_version_id)
        )
    ).scalar_one()
    v.locked = True
    if parent is not None and parent.id != v.id:
        # Restore parent's locked state so older locked versions remain rollback targets.
        parent.locked = True
    await db_session.commit()
    return proj, v


@pytest.mark.asyncio
async def test_publish_sets_published_version_to_active_by_default(client, db_session):
    h, pid = await _auth_and_project(client, "pv1@pv.com")
    _, v = await _patch_and_lock(client, db_session, pid, h)

    res = await client.post(
        f"/api/v1/projects/{pid}/publish",
        json={"api_code": "japan-receipts"},
        headers=h,
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["published_version_id"] == v.id
    assert body["active_version_id"] == v.id
    assert body["api_code"] == "japan-receipts"
    assert body["api_published_at"] is not None


@pytest.mark.asyncio
async def test_publish_can_target_locked_non_active_version(client, db_session):
    """User publishes an older locked version while Lab moves on to a new active one."""
    h, pid = await _auth_and_project(client, "pv2@pv.com")
    _, old_locked = await _patch_and_lock(client, db_session, pid, h)
    _, new_active = await _patch_and_lock(
        client,
        db_session,
        pid,
        h,
        schema=[
            {"name": "shop_name", "type": "string", "description": "店名"},
            {"name": "total", "type": "number", "description": "総額"},
        ],
    )
    assert new_active.id != old_locked.id

    res = await client.post(
        f"/api/v1/projects/{pid}/publish",
        json={"api_code": "japan-receipts", "project_version_id": old_locked.id},
        headers=h,
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["active_version_id"] == new_active.id
    assert body["published_version_id"] == old_locked.id


@pytest.mark.asyncio
async def test_publish_rejects_unlocked_target_version(client, db_session):
    from app.models.project import Project
    from app.models.project_version import ProjectVersion
    from sqlalchemy import select

    h, pid = await _auth_and_project(client, "pv3@pv.com")
    _, locked_v = await _patch_and_lock(client, db_session, pid, h)
    # Unlock and patch a second version (left unlocked).
    locked_v.locked = False
    await db_session.commit()
    res2 = await client.patch(
        f"/api/v1/projects/{pid}/schema",
        json={
            "schema": [{"name": "shop_name", "type": "string", "description": "x"}],
            "global_notes": "",
            "model_id": "m",
        },
        headers=h,
    )
    assert res2.status_code == 200, res2.text
    proj = (await db_session.execute(select(Project).where(Project.id == pid))).scalar_one()
    unlocked = (
        await db_session.execute(
            select(ProjectVersion).where(ProjectVersion.id == proj.active_version_id)
        )
    ).scalar_one()
    assert unlocked.id != locked_v.id
    assert unlocked.locked is False

    res = await client.post(
        f"/api/v1/projects/{pid}/publish",
        json={"api_code": "japan-receipts-3", "project_version_id": unlocked.id},
        headers=h,
    )
    assert res.status_code == 409


@pytest.mark.asyncio
async def test_publish_rejects_target_version_from_other_project(client, db_session):
    from app.models.project import Project
    from app.models.project_version import ProjectVersion
    from sqlalchemy import select

    h, pid_a = await _auth_and_project(client, "pv4@pv.com")
    _, va = await _patch_and_lock(client, db_session, pid_a, h)

    pid_b = (await client.post("/api/v1/projects", json={"name": "B"}, headers=h)).json()["id"]
    proj_b = (await db_session.execute(select(Project).where(Project.id == pid_b))).scalar_one()
    vb = (
        await db_session.execute(
            select(ProjectVersion).where(ProjectVersion.id == proj_b.active_version_id)
        )
    ).scalar_one()
    vb.locked = True
    await db_session.commit()

    # Try publishing project A using project B's locked version.
    res = await client.post(
        f"/api/v1/projects/{pid_a}/publish",
        json={"api_code": "japan-receipts-x", "project_version_id": vb.id},
        headers=h,
    )
    assert res.status_code in (404, 409)


@pytest.mark.asyncio
async def test_rollback_changes_published_not_active(client, db_session):
    """Rollback moves published_version_id to a previous locked version without
    touching active_version_id (spec §7.2)."""
    h, pid = await _auth_and_project(client, "rb@rb.com")
    _, old_locked = await _patch_and_lock(client, db_session, pid, h)
    # Publish first (the old locked) — active_version_id == old_locked.id at this moment.
    pub = await client.post(
        f"/api/v1/projects/{pid}/publish",
        json={"api_code": "rb-receipts"},
        headers=h,
    )
    assert pub.status_code == 200, pub.text

    # Move Lab to a new active locked version.
    _, new_active = await _patch_and_lock(
        client,
        db_session,
        pid,
        h,
        schema=[
            {"name": "shop_name", "type": "string", "description": "x"},
            {"name": "total", "type": "number", "description": "y"},
        ],
    )
    assert new_active.id != old_locked.id

    # Promote new_active to published.
    pub2 = await client.post(
        f"/api/v1/projects/{pid}/publish",
        json={"api_code": "rb-receipts", "project_version_id": new_active.id},
        headers=h,
    )
    assert pub2.status_code == 200, pub2.text
    assert pub2.json()["published_version_id"] == new_active.id

    # Now rollback to the old locked version.
    res = await client.post(
        f"/api/v1/projects/{pid}/rollback",
        json={"project_version_id": old_locked.id},
        headers=h,
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["published_version_id"] == old_locked.id
    assert body["active_version_id"] == new_active.id


@pytest.mark.asyncio
async def test_rollback_rejects_unpublished_project(client, db_session):
    h, pid = await _auth_and_project(client, "rb2@rb.com")
    _, v = await _patch_and_lock(client, db_session, pid, h)
    res = await client.post(
        f"/api/v1/projects/{pid}/rollback",
        json={"project_version_id": v.id},
        headers=h,
    )
    assert res.status_code == 409


@pytest.mark.asyncio
async def test_rollback_rejects_unlocked_or_foreign_version(client, db_session):
    from app.models.project import Project
    from app.models.project_version import ProjectVersion
    from sqlalchemy import select

    h, pid = await _auth_and_project(client, "rb3@rb.com")
    _, v_locked = await _patch_and_lock(client, db_session, pid, h)
    pub = await client.post(
        f"/api/v1/projects/{pid}/publish",
        json={"api_code": "rb3-rcpt"},
        headers=h,
    )
    assert pub.status_code == 200

    # Unlock parent then add an unlocked version on top.
    v_locked.locked = False
    await db_session.commit()
    res2 = await client.patch(
        f"/api/v1/projects/{pid}/schema",
        json={
            "schema": [{"name": "shop_name", "type": "string", "description": "x"}],
            "global_notes": "",
            "model_id": "m",
        },
        headers=h,
    )
    assert res2.status_code == 200, res2.text
    proj = (await db_session.execute(select(Project).where(Project.id == pid))).scalar_one()
    unlocked = (
        await db_session.execute(
            select(ProjectVersion).where(ProjectVersion.id == proj.active_version_id)
        )
    ).scalar_one()
    assert unlocked.locked is False

    res = await client.post(
        f"/api/v1/projects/{pid}/rollback",
        json={"project_version_id": unlocked.id},
        headers=h,
    )
    assert res.status_code == 409
