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
async def test_api_code_unique_globally_across_workspaces(client, db_session):
    """The public route /extract/{api_code} has no workspace context, so the
    same api_code in two different workspaces would be ambiguous. R7.5
    hardening: enforce global uniqueness, not just per-workspace.
    """
    from sqlalchemy import select

    from app.models.project import Project
    from app.models.project_version import ProjectVersion

    h_a, pid_a = await _auth_and_project(client, "ga@ga.com")
    await client.patch(
        f"/api/v1/projects/{pid_a}/schema",
        json={
            "schema": [{"name": "shop_name", "type": "string", "description": "店名"}],
            "global_notes": "",
            "model_id": "m",
        },
        headers=h_a,
    )
    proj_a = (await db_session.execute(select(Project).where(Project.id == pid_a))).scalar_one()
    v_a = (
        await db_session.execute(
            select(ProjectVersion).where(ProjectVersion.id == proj_a.active_version_id)
        )
    ).scalar_one()
    v_a.locked = True
    await db_session.commit()
    r1 = await client.post(
        f"/api/v1/projects/{pid_a}/publish", json={"api_code": "global-code"}, headers=h_a
    )
    assert r1.status_code == 200, r1.text

    # Different user → different workspace.
    h_b, pid_b = await _auth_and_project(client, "gb@gb.com")
    await client.patch(
        f"/api/v1/projects/{pid_b}/schema",
        json={
            "schema": [{"name": "shop_name", "type": "string", "description": "店名"}],
            "global_notes": "",
            "model_id": "m",
        },
        headers=h_b,
    )
    proj_b = (await db_session.execute(select(Project).where(Project.id == pid_b))).scalar_one()
    assert proj_b.workspace_id != proj_a.workspace_id
    v_b = (
        await db_session.execute(
            select(ProjectVersion).where(ProjectVersion.id == proj_b.active_version_id)
        )
    ).scalar_one()
    v_b.locked = True
    await db_session.commit()

    r2 = await client.post(
        f"/api/v1/projects/{pid_b}/publish", json={"api_code": "global-code"}, headers=h_b
    )
    assert r2.status_code == 409


@pytest.mark.asyncio
async def test_publish_invalid_api_code_validation(client):
    h, pid = await _auth_and_project(client, "inv@inv.com")
    resp = await client.post(
        f"/api/v1/projects/{pid}/publish", json={"api_code": "Bad Code With Spaces"}, headers=h
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_publish_rejects_api_code_too_long(client):
    """Spec §7.1 / R7.5 hardening: api_code length must be 1-64 chars."""
    h, pid = await _auth_and_project(client, "len@len.com")
    too_long = "a" * 65
    resp = await client.post(
        f"/api/v1/projects/{pid}/publish", json={"api_code": too_long}, headers=h
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_publish_rejects_empty_api_code(client):
    h, pid = await _auth_and_project(client, "len2@len.com")
    resp = await client.post(
        f"/api/v1/projects/{pid}/publish", json={"api_code": ""}, headers=h
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_publish_accepts_max_length_api_code(client, db_session):
    h, pid = await _auth_and_project(client, "len3@len.com")
    _, _ = await _patch_and_lock(client, db_session, pid, h)
    code = "a" + ("b" * 62) + "c"  # 64 chars
    assert len(code) == 64
    resp = await client.post(
        f"/api/v1/projects/{pid}/publish", json={"api_code": code}, headers=h
    )
    assert resp.status_code == 200, resp.text


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
async def test_publish_rejects_empty_schema(client, db_session):
    """Spec §4.5 publish blocker: target version with empty schema snapshot
    must not be promoted to public API. Empty contract = no useful API."""
    from sqlalchemy import select

    from app.models.project import Project
    from app.models.project_version import ProjectVersion

    h, pid = await _auth_and_project(client, "es@es.com")
    proj = (await db_session.execute(select(Project).where(Project.id == pid))).scalar_one()
    v = (
        await db_session.execute(
            select(ProjectVersion).where(ProjectVersion.id == proj.active_version_id)
        )
    ).scalar_one()
    # Initial ProjectVersion has [] schema_snapshot. Lock it directly to bypass
    # other publish gates so we isolate the empty-schema blocker.
    assert v.schema_snapshot == []
    v.locked = True
    await db_session.commit()

    resp = await client.post(
        f"/api/v1/projects/{pid}/publish", json={"api_code": "es-rcpt"}, headers=h
    )
    assert resp.status_code == 409
    assert "empty" in resp.json()["error_message_en"].lower() or "schema" in resp.json()["error_message_en"].lower()


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


async def _publish_simple(client, db_session, email: str, api_code: str = "ja-rcpt"):
    """Helper: register user, create project, lock active version, publish."""
    h, pid = await _auth_and_project(client, email)
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
    res = await client.post(
        f"/api/v1/projects/{pid}/publish", json={"api_code": api_code}, headers=h
    )
    assert res.status_code == 200
    return h, pid, res.json()


@pytest.mark.asyncio
async def test_published_at_serialized_with_timezone_offset(client, db_session):
    """JS new Date() reads naive ISO as local time; we must always emit
    explicit offset so /api/v1/projects/* timestamps render as UTC."""
    _, _, body = await _publish_simple(client, db_session, "tz@tz.com")
    api_pub = body["api_published_at"]
    created = body["created_at"]
    # ISO 8601 with offset ends in "Z" or "+HH:MM" / "-HH:MM"
    assert api_pub.endswith("Z") or api_pub[-6] in ("+", "-"), api_pub
    assert created.endswith("Z") or created[-6] in ("+", "-"), created


@pytest.mark.asyncio
async def test_rename_api_code_keeps_api_published_at(client, db_session):
    """Pure rename (same published_version_id, different api_code) must
    not bump api_published_at. Re-stamping makes the UI claim a fresh
    publish event when no Lab promotion happened (R8.2 smoke #B)."""
    h, pid, first = await _publish_simple(client, db_session, "rn@rn.com", "ja-rcpt")
    first_published_at = first["api_published_at"]
    first_version_id = first["published_version_id"]

    # Same project_version_id (the one we just published), new api_code.
    res = await client.post(
        f"/api/v1/projects/{pid}/publish",
        json={"api_code": "ja-rcpt-v2", "project_version_id": first_version_id},
        headers=h,
    )
    assert res.status_code == 200
    after = res.json()
    assert after["api_code"] == "ja-rcpt-v2"
    assert after["published_version_id"] == first_version_id
    assert after["api_published_at"] == first_published_at, (
        "rename should not touch api_published_at"
    )


@pytest.mark.asyncio
async def test_re_publish_after_unpublish_re_stamps_api_published_at(
    client, db_session
):
    """If api_published_at was cleared by unpublish, re-publishing the same
    version DOES re-stamp it — this is the integrator-visible 'now serving'
    moment."""
    h, pid, first = await _publish_simple(client, db_session, "rp@rp.com", "ja-rcpt")
    first_version_id = first["published_version_id"]
    await client.post(f"/api/v1/projects/{pid}/unpublish", headers=h)

    res = await client.post(
        f"/api/v1/projects/{pid}/publish",
        json={"api_code": "ja-rcpt", "project_version_id": first_version_id},
        headers=h,
    )
    assert res.status_code == 200
    assert res.json()["api_published_at"] is not None
