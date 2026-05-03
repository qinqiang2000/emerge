import pytest


async def _auth(client, email="p@p.com"):
    await client.post("/api/v1/auth/register", json={"email": email, "password": "hunter22"})
    tok = (
        await client.post("/api/v1/auth/login", json={"email": email, "password": "hunter22"})
    ).json()["access_token"]
    return {"Authorization": f"Bearer {tok}"}


@pytest.mark.asyncio
async def test_create_project(client):
    h = await _auth(client)
    resp = await client.post("/api/v1/projects", json={"name": "Receipts"}, headers=h)
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["name"] == "Receipts"
    assert body["api_code"] is None


@pytest.mark.asyncio
async def test_list_projects_returns_only_my_workspace(client):
    h1 = await _auth(client, "a@a.com")
    h2 = await _auth(client, "b@b.com")
    await client.post("/api/v1/projects", json={"name": "P-A"}, headers=h1)
    await client.post("/api/v1/projects", json={"name": "P-B"}, headers=h2)

    r1 = await client.get("/api/v1/projects", headers=h1)
    r2 = await client.get("/api/v1/projects", headers=h2)
    assert [p["name"] for p in r1.json()] == ["P-A"]
    assert [p["name"] for p in r2.json()] == ["P-B"]


@pytest.mark.asyncio
async def test_get_project_404_for_other_workspace(client):
    h1 = await _auth(client, "a@a.com")
    h2 = await _auth(client, "b@b.com")
    pid = (await client.post("/api/v1/projects", json={"name": "P"}, headers=h1)).json()["id"]
    resp = await client.get(f"/api/v1/projects/{pid}", headers=h2)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_create_project_creates_initial_version(client, db_session):
    h = await _auth(client)
    body = (await client.post("/api/v1/projects", json={"name": "P"}, headers=h)).json()
    pid = body["id"]
    assert body["active_version_id"] is not None

    from sqlalchemy import select

    from app.models.project_version import ProjectVersion

    rows = (
        await db_session.execute(
            select(ProjectVersion).where(ProjectVersion.project_id == pid)
        )
    ).scalars().all()
    assert len(rows) == 1
    assert rows[0].version_number == 0
    assert rows[0].source == "initial"
    assert rows[0].schema_snapshot == []


@pytest.mark.asyncio
async def test_create_project_from_template_forks_schema(client, db_session):
    h = await _auth(client, "fork@f.com")
    from app.models.template import Template
    from app.models.user import User
    from sqlalchemy import select

    user_id = (await db_session.execute(select(User))).scalar_one().id
    db_session.add(
        Template(
            workspace_id=None,
            name="builtin_for_fork",
            description="d",
            version=1,
            schema_json=[
                {"name": "shop_name", "type": "string", "description": "店名"},
            ],
            global_notes="hi",
            recommended_model_id="m1",
            created_by=user_id,
            builtin=True,
        )
    )
    await db_session.commit()
    tpl_id = (
        await db_session.execute(select(Template).where(Template.name == "builtin_for_fork"))
    ).scalar_one().id

    resp = await client.post(
        "/api/v1/projects",
        json={"name": "P", "template_id": tpl_id},
        headers=h,
    )
    body = resp.json()
    pid = body["id"]
    assert body["template_id"] == tpl_id

    active = (
        await client.get(f"/api/v1/projects/{pid}/versions/active", headers=h)
    ).json()
    assert active["schema"][0]["name"] == "shop_name"
    assert active["global_notes"] == "hi"
    assert active["model_id"] == "m1"
