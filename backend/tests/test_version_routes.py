import pytest


async def _auth_and_project(client, email="vp@vp.com"):
    await client.post("/api/v1/auth/register", json={"email": email, "password": "hunter22"})
    tok = (
        await client.post("/api/v1/auth/login", json={"email": email, "password": "hunter22"})
    ).json()["access_token"]
    h = {"Authorization": f"Bearer {tok}"}
    pid = (await client.post("/api/v1/projects", json={"name": "P"}, headers=h)).json()["id"]
    return h, pid


@pytest.mark.asyncio
async def test_get_active_version_returns_initial(client):
    h, pid = await _auth_and_project(client)
    resp = await client.get(f"/api/v1/projects/{pid}/versions/active", headers=h)
    assert resp.status_code == 200
    body = resp.json()
    assert body["version_number"] == 0
    assert body["schema"] == []
    assert body["locked"] is False


@pytest.mark.asyncio
async def test_patch_schema_creates_new_version(client):
    h, pid = await _auth_and_project(client, email="vp2@vp.com")
    payload = {
        "schema": [
            {
                "name": "shop_name",
                "type": "string",
                "required": True,
                "description": "店名",
            }
        ],
        "global_notes": "all in JPY",
        "model_id": "gpt-4o-2024-08-06",
    }
    r1 = await client.patch(f"/api/v1/projects/{pid}/schema", json=payload, headers=h)
    assert r1.status_code == 200
    body = r1.json()
    assert body["version_number"] == 1
    assert body["schema"][0]["name"] == "shop_name"
    assert body["global_notes"] == "all in JPY"

    # active is now the new version
    r2 = await client.get(f"/api/v1/projects/{pid}/versions/active", headers=h)
    assert r2.json()["version_number"] == 1


@pytest.mark.asyncio
async def test_patch_schema_validates_field_shape(client):
    h, pid = await _auth_and_project(client, email="vp3@vp.com")
    bad = {
        "schema": [{"name": "ShopName", "type": "string", "description": "bad"}],
        "global_notes": "",
        "model_id": "x",
    }
    resp = await client.patch(f"/api/v1/projects/{pid}/schema", json=bad, headers=h)
    assert resp.status_code == 422
