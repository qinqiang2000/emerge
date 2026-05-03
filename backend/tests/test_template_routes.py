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

    user_id = (await db_session.execute(select(User))).scalar_one().id
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
