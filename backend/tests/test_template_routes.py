import pytest


async def _auth(client, email="tt@tt.com"):
    await client.post("/api/v1/auth/register", json={"email": email, "password": "hunter22"})
    tok = (
        await client.post("/api/v1/auth/login", json={"email": email, "password": "hunter22"})
    ).json()["access_token"]
    return {"Authorization": f"Bearer {tok}"}


@pytest.mark.asyncio
async def test_list_templates_includes_builtins(client, db_session):
    h = await _auth(client)
    from app.models.template import Template
    from app.models.user import User
    from sqlalchemy import select

    user_id = (await db_session.execute(select(User).order_by(User.id).limit(1))).scalar_one().id
    db_session.add(
        Template(
            workspace_id=None,
            name="china_vat",
            description="builtin",
            version=1,
            schema_json=[],
            global_notes="",
            recommended_model_id="m",
            created_by=user_id,
            builtin=True,
        )
    )
    await db_session.commit()
    resp = await client.get("/api/v1/templates", headers=h)
    body = resp.json()
    assert any(t["name"] == "china_vat" and t["builtin"] is True for t in body)


@pytest.mark.asyncio
async def test_template_isolated_per_workspace(client, db_session):
    """Template owned by one workspace is not visible to another."""
    h1 = await _auth(client, "u1@u1.com")
    h2 = await _auth(client, "u2@u2.com")
    from app.models.template import Template
    from app.models.user import User
    from sqlalchemy import select

    rows = (await db_session.execute(select(User).order_by(User.id))).scalars().all()
    user1, user2 = rows[0], rows[1]
    from app.models.workspace import WorkspaceMembership

    ws1 = (
        await db_session.execute(
            select(WorkspaceMembership).where(WorkspaceMembership.user_id == user1.id)
        )
    ).scalar_one().workspace_id
    db_session.add(
        Template(
            workspace_id=ws1,
            name="custom",
            description="d",
            version=1,
            schema_json=[],
            global_notes="",
            recommended_model_id="m",
            created_by=user1.id,
            builtin=False,
        )
    )
    await db_session.commit()
    resp = await client.get("/api/v1/templates", headers=h2)
    assert all(t["name"] != "custom" for t in resp.json())


@pytest.mark.asyncio
async def test_save_as_template_promotes_active_schema(client):
    h = await _auth(client, "saveas@s.com")
    pid = (await client.post("/api/v1/projects", json={"name": "P"}, headers=h)).json()["id"]
    await client.patch(
        f"/api/v1/projects/{pid}/schema",
        json={
            "schema": [{"name": "shop_name", "type": "string", "description": "店名"}],
            "global_notes": "JPY",
            "model_id": "m",
        },
        headers=h,
    )
    resp = await client.post(
        f"/api/v1/templates/projects/{pid}/save-as-template",
        json={"name": "japan_receipts", "description": "from project P"},
        headers=h,
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["name"] == "japan_receipts"
    assert body["version"] == 1
    assert body["schema"][0]["name"] == "shop_name"


@pytest.mark.asyncio
async def test_save_as_creates_new_version_when_name_exists(client):
    h = await _auth(client, "sv@s.com")
    pid = (await client.post("/api/v1/projects", json={"name": "P"}, headers=h)).json()["id"]
    payload = {"name": "tplA", "description": ""}
    r1 = await client.post(
        f"/api/v1/templates/projects/{pid}/save-as-template",
        json={**payload, "create_new_version": False},
        headers=h,
    )
    assert r1.json()["version"] == 1
    r2 = await client.post(
        f"/api/v1/templates/projects/{pid}/save-as-template",
        json={**payload, "create_new_version": True},
        headers=h,
    )
    assert r2.json()["version"] == 2


@pytest.mark.asyncio
async def test_save_as_duplicate_name_without_flag_409(client):
    h = await _auth(client, "dup@s.com")
    pid = (await client.post("/api/v1/projects", json={"name": "P"}, headers=h)).json()["id"]
    payload = {"name": "tplDup", "description": "", "create_new_version": False}
    r1 = await client.post(
        f"/api/v1/templates/projects/{pid}/save-as-template", json=payload, headers=h
    )
    assert r1.status_code == 201
    r2 = await client.post(
        f"/api/v1/templates/projects/{pid}/save-as-template", json=payload, headers=h
    )
    assert r2.status_code == 409


@pytest.mark.asyncio
async def test_get_template_cross_workspace_404(client, db_session):
    """GET /templates/{id} returns 404 when the template belongs to a different workspace."""
    from sqlalchemy import select

    from app.models.template import Template
    from app.models.user import User
    from app.models.workspace import WorkspaceMembership

    # Create two users in separate workspaces
    await _auth(client, "cw1@cw.com")
    h2 = await _auth(client, "cw2@cw.com")

    rows = (await db_session.execute(select(User).order_by(User.id))).scalars().all()
    user1 = next(u for u in rows if u.email == "cw1@cw.com")
    ws1 = (
        await db_session.execute(
            select(WorkspaceMembership).where(WorkspaceMembership.user_id == user1.id)
        )
    ).scalar_one().workspace_id

    # Create a template belonging to workspace 1
    tpl = Template(
        workspace_id=ws1,
        name="ws1_only",
        description="d",
        version=1,
        schema_json=[],
        global_notes="",
        recommended_model_id="m",
        created_by=user1.id,
        builtin=False,
    )
    db_session.add(tpl)
    await db_session.commit()
    await db_session.refresh(tpl)

    # User 2 (different workspace) should get 404
    resp = await client.get(f"/api/v1/templates/{tpl.id}", headers=h2)
    assert resp.status_code == 404
