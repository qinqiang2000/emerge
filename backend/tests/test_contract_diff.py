import pytest

from app.services.contract_diff import diff_schema_snapshots


def test_contract_diff_detects_removed_field_as_breaking():
    old = [{"name": "total_amount", "type": "number", "required": True, "description": "total"}]
    new = []
    out = diff_schema_snapshots(old, new)
    assert out.has_breaking_changes is True
    assert any(i.kind == "field_removed" and i.severity == "breaking" for i in out.items)


def test_contract_diff_detects_optional_field_added_as_non_breaking():
    old = []
    new = [{"name": "currency", "type": "string", "required": False, "description": "ISO code"}]
    out = diff_schema_snapshots(old, new)
    assert out.has_breaking_changes is False
    assert any(i.kind == "optional_field_added" and i.severity == "non_breaking" for i in out.items)


def test_contract_diff_detects_required_field_added_as_breaking():
    old = []
    new = [{"name": "currency", "type": "string", "required": True, "description": "ISO code"}]
    out = diff_schema_snapshots(old, new)
    assert any(i.kind == "required_field_added" and i.severity == "breaking" for i in out.items)


def test_contract_diff_detects_type_change_as_breaking():
    old = [{"name": "date", "type": "string", "required": True, "description": "date"}]
    new = [{"name": "date", "type": "integer", "required": True, "description": "date"}]
    out = diff_schema_snapshots(old, new)
    assert any(i.kind == "type_changed" and i.severity == "breaking" for i in out.items)


def test_contract_diff_detects_required_tightened_as_breaking():
    old = [{"name": "x", "type": "string", "required": False, "description": "x"}]
    new = [{"name": "x", "type": "string", "required": True, "description": "x"}]
    out = diff_schema_snapshots(old, new)
    assert any(i.kind == "required_tightened" and i.severity == "breaking" for i in out.items)


def test_contract_diff_detects_required_loosened_as_non_breaking():
    old = [{"name": "x", "type": "string", "required": True, "description": "x"}]
    new = [{"name": "x", "type": "string", "required": False, "description": "x"}]
    out = diff_schema_snapshots(old, new)
    assert any(i.kind == "required_loosened" and i.severity == "non_breaking" for i in out.items)
    assert out.has_breaking_changes is False


def test_contract_diff_detects_enum_narrowing_as_breaking():
    old = [{"name": "currency", "type": "string", "required": True, "description": "", "enum": ["JPY", "USD", "EUR"]}]
    new = [{"name": "currency", "type": "string", "required": True, "description": "", "enum": ["JPY", "USD"]}]
    out = diff_schema_snapshots(old, new)
    assert any(i.kind == "enum_narrowed" and i.severity == "breaking" for i in out.items)


def test_contract_diff_detects_enum_widening_as_non_breaking():
    old = [{"name": "currency", "type": "string", "required": True, "description": "", "enum": ["JPY"]}]
    new = [{"name": "currency", "type": "string", "required": True, "description": "", "enum": ["JPY", "USD"]}]
    out = diff_schema_snapshots(old, new)
    assert any(i.kind == "enum_widened" and i.severity == "non_breaking" for i in out.items)


def test_contract_diff_description_change_only_is_non_breaking():
    old = [{"name": "x", "type": "string", "required": True, "description": "old"}]
    new = [{"name": "x", "type": "string", "required": True, "description": "new"}]
    out = diff_schema_snapshots(old, new)
    assert out.has_breaking_changes is False
    # description-only change may or may not surface an item, but must not be breaking.
    assert all(i.severity == "non_breaking" for i in out.items)


def test_contract_diff_endpoint_default_resolves_published_to_active(client, db_session):
    """End-to-end: GET /contract-diff defaults from=published, to=active."""
    pass  # exercised in route tests via test_publish_routes.py


@pytest.mark.asyncio
async def test_contract_diff_route_returns_diff_between_versions(client, db_session):
    """Route: GET /api/v1/projects/{pid}/contract-diff."""
    from app.models.project import Project
    from app.models.project_version import ProjectVersion
    from sqlalchemy import select

    await client.post("/api/v1/auth/register", json={"email": "cd@cd.com", "password": "hunter22"})
    tok = (
        await client.post("/api/v1/auth/login", json={"email": "cd@cd.com", "password": "hunter22"})
    ).json()["access_token"]
    h = {"Authorization": f"Bearer {tok}"}
    pid = (await client.post("/api/v1/projects", json={"name": "P"}, headers=h)).json()["id"]
    # Initial v1 (empty schema).
    proj = (await db_session.execute(select(Project).where(Project.id == pid))).scalar_one()
    v1_id = proj.active_version_id
    # Patch -> v2.
    await client.patch(
        f"/api/v1/projects/{pid}/schema",
        json={
            "schema": [{"name": "total", "type": "number", "description": "total"}],
            "global_notes": "",
            "model_id": "m",
        },
        headers=h,
    )
    proj = (await db_session.execute(select(Project).where(Project.id == pid))).scalar_one()
    v2_id = proj.active_version_id

    res = await client.get(
        f"/api/v1/projects/{pid}/contract-diff",
        params={"from_version_id": v1_id, "to_version_id": v2_id},
        headers=h,
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["from_version_id"] == v1_id
    assert body["to_version_id"] == v2_id
    assert any(i["kind"] == "required_field_added" for i in body["items"])


@pytest.mark.asyncio
async def test_contract_diff_route_defaults(client, db_session):
    """Defaults: from=published_version_id, to=active_version_id."""
    from app.models.project import Project
    from app.models.project_version import ProjectVersion
    from sqlalchemy import select

    await client.post("/api/v1/auth/register", json={"email": "cd2@cd.com", "password": "hunter22"})
    tok = (
        await client.post("/api/v1/auth/login", json={"email": "cd2@cd.com", "password": "hunter22"})
    ).json()["access_token"]
    h = {"Authorization": f"Bearer {tok}"}
    pid = (await client.post("/api/v1/projects", json={"name": "P"}, headers=h)).json()["id"]

    # Lock v1, publish.
    await client.patch(
        f"/api/v1/projects/{pid}/schema",
        json={
            "schema": [{"name": "total", "type": "number", "description": "total"}],
            "global_notes": "",
            "model_id": "m",
        },
        headers=h,
    )
    proj = (await db_session.execute(select(Project).where(Project.id == pid))).scalar_one()
    v1 = (
        await db_session.execute(
            select(ProjectVersion).where(ProjectVersion.id == proj.active_version_id)
        )
    ).scalar_one()
    v1.locked = True
    await db_session.commit()
    await client.post(
        f"/api/v1/projects/{pid}/publish",
        json={"api_code": "cd-rcpt"},
        headers=h,
    )

    # Move Lab to v2 (unlock first then patch).
    v1.locked = False
    await db_session.commit()
    await client.patch(
        f"/api/v1/projects/{pid}/schema",
        json={
            "schema": [
                {"name": "total", "type": "number", "description": "total"},
                {"name": "currency", "type": "string", "required": False, "description": "ISO"},
            ],
            "global_notes": "",
            "model_id": "m",
        },
        headers=h,
    )
    v1.locked = True
    await db_session.commit()

    res = await client.get(f"/api/v1/projects/{pid}/contract-diff", headers=h)
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["from_version_id"] == v1.id
    proj = (await db_session.execute(select(Project).where(Project.id == pid))).scalar_one()
    assert body["to_version_id"] == proj.active_version_id
    assert any(i["kind"] == "optional_field_added" for i in body["items"])
    assert body["has_breaking_changes"] is False


@pytest.mark.asyncio
async def test_contract_diff_route_404_for_foreign_version(client, db_session):
    from app.models.project import Project
    from sqlalchemy import select

    await client.post("/api/v1/auth/register", json={"email": "cd3@cd.com", "password": "hunter22"})
    tok = (
        await client.post("/api/v1/auth/login", json={"email": "cd3@cd.com", "password": "hunter22"})
    ).json()["access_token"]
    h = {"Authorization": f"Bearer {tok}"}
    pid_a = (await client.post("/api/v1/projects", json={"name": "A"}, headers=h)).json()["id"]
    pid_b = (await client.post("/api/v1/projects", json={"name": "B"}, headers=h)).json()["id"]
    proj_b = (await db_session.execute(select(Project).where(Project.id == pid_b))).scalar_one()
    foreign = proj_b.active_version_id

    res = await client.get(
        f"/api/v1/projects/{pid_a}/contract-diff",
        params={"to_version_id": foreign},
        headers=h,
    )
    assert res.status_code == 404
