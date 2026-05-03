import pytest


@pytest.mark.asyncio
async def test_register_creates_user_and_workspace(client, db_session):
    resp = await client.post(
        "/api/v1/auth/register",
        json={"email": "alice@example.com", "password": "hunter22"},
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["email"] == "alice@example.com"
    assert "id" in body

    # exactly one Workspace + Membership owner row created
    from sqlalchemy import select

    from app.models.user import User
    from app.models.workspace import Workspace, WorkspaceMembership

    user = (await db_session.execute(select(User))).scalar_one()
    ws = (await db_session.execute(select(Workspace))).scalar_one()
    mem = (await db_session.execute(select(WorkspaceMembership))).scalar_one()
    assert ws.owner_id == user.id
    assert mem.role == "owner"


@pytest.mark.asyncio
async def test_register_duplicate_email_returns_conflict(client):
    payload = {"email": "dup@example.com", "password": "hunter22"}
    r1 = await client.post("/api/v1/auth/register", json=payload)
    assert r1.status_code == 201
    r2 = await client.post("/api/v1/auth/register", json=payload)
    assert r2.status_code == 409
    assert r2.json()["error_code"] == "CONFLICT"


@pytest.mark.asyncio
async def test_login_returns_token(client):
    await client.post(
        "/api/v1/auth/register", json={"email": "l@l.com", "password": "hunter22"}
    )
    resp = await client.post(
        "/api/v1/auth/login", json={"email": "l@l.com", "password": "hunter22"}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["token_type"] == "bearer"
    assert isinstance(body["access_token"], str) and len(body["access_token"]) > 20


@pytest.mark.asyncio
async def test_login_wrong_password_returns_unauthorized(client):
    await client.post(
        "/api/v1/auth/register", json={"email": "x@x.com", "password": "hunter22"}
    )
    resp = await client.post(
        "/api/v1/auth/login", json={"email": "x@x.com", "password": "WRONG"}
    )
    assert resp.status_code == 401
    assert resp.json()["error_code"] == "UNAUTHORIZED"
