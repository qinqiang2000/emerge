import pytest


@pytest.mark.asyncio
async def test_me_requires_auth(client):
    resp = await client.get("/api/v1/me")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_me_returns_user_and_workspace(client):
    await client.post(
        "/api/v1/auth/register", json={"email": "m@m.com", "password": "hunter22"}
    )
    tok = (
        await client.post(
            "/api/v1/auth/login", json={"email": "m@m.com", "password": "hunter22"}
        )
    ).json()["access_token"]
    resp = await client.get("/api/v1/me", headers={"Authorization": f"Bearer {tok}"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["email"] == "m@m.com"
    assert isinstance(body["workspace_id"], int)


@pytest.mark.asyncio
async def test_me_with_bad_token_returns_unauthorized(client):
    resp = await client.get("/api/v1/me", headers={"Authorization": "Bearer garbage"})
    assert resp.status_code == 401
