import io

import pytest


async def _scaffold(client, tmp_path, monkeypatch) -> tuple[dict, int, int]:
    monkeypatch.setattr("app.services.storage.settings.storage_root", str(tmp_path))
    await client.post(
        "/api/v1/auth/register", json={"email": "a@a.com", "password": "hunter22"}
    )
    tok = (
        await client.post(
            "/api/v1/auth/login", json={"email": "a@a.com", "password": "hunter22"}
        )
    ).json()["access_token"]
    h = {"Authorization": f"Bearer {tok}"}
    pid = (await client.post("/api/v1/projects", json={"name": "P"}, headers=h)).json()["id"]
    did = (
        await client.post(
            f"/api/v1/projects/{pid}/documents",
            files=[("files", ("a.pdf", io.BytesIO(b"AA"), "application/pdf"))],
            headers=h,
        )
    ).json()[0]["id"]
    return h, pid, did


@pytest.mark.asyncio
async def test_save_correction(client, tmp_path, monkeypatch):
    h, pid, did = await _scaffold(client, tmp_path, monkeypatch)
    resp = await client.post(
        f"/api/v1/projects/{pid}/documents/{did}/annotations",
        json={"output": [{"shop_name": "ABC"}], "notes": "fixed shop"},
        headers=h,
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["role"] == "none"
    assert body["status"] == "saved"
    assert body["output"] == [{"shop_name": "ABC"}]


@pytest.mark.asyncio
async def test_list_annotations(client, tmp_path, monkeypatch):
    h, pid, did = await _scaffold(client, tmp_path, monkeypatch)
    await client.post(
        f"/api/v1/projects/{pid}/documents/{did}/annotations",
        json={"output": [{"a": 1}]},
        headers=h,
    )
    await client.post(
        f"/api/v1/projects/{pid}/documents/{did}/annotations",
        json={"output": [{"a": 2}]},
        headers=h,
    )
    resp = await client.get(
        f"/api/v1/projects/{pid}/documents/{did}/annotations", headers=h
    )
    assert resp.status_code == 200
    assert len(resp.json()) == 2


@pytest.mark.asyncio
async def test_patch_annotation(client, tmp_path, monkeypatch):
    h, pid, did = await _scaffold(client, tmp_path, monkeypatch)
    aid = (
        await client.post(
            f"/api/v1/projects/{pid}/documents/{did}/annotations",
            json={"output": [{"a": 1}]},
            headers=h,
        )
    ).json()["id"]
    resp = await client.patch(
        f"/api/v1/projects/{pid}/annotations/{aid}",
        json={"output": [{"a": 99}], "notes": "amended"},
        headers=h,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["output"] == [{"a": 99}]
    assert body["notes"] == "amended"


@pytest.mark.asyncio
async def test_delete_annotation_soft_deletes(client, tmp_path, monkeypatch):
    h, pid, did = await _scaffold(client, tmp_path, monkeypatch)
    aid = (
        await client.post(
            f"/api/v1/projects/{pid}/documents/{did}/annotations",
            json={"output": [{"a": 1}]},
            headers=h,
        )
    ).json()["id"]
    resp = await client.delete(f"/api/v1/projects/{pid}/annotations/{aid}", headers=h)
    assert resp.status_code == 200
    assert resp.json()["status"] == "cancelled"

    listing = await client.get(
        f"/api/v1/projects/{pid}/documents/{did}/annotations", headers=h
    )
    assert all(a["status"] != "cancelled" for a in listing.json())  # default filter excludes


@pytest.mark.asyncio
async def test_cross_project_annotation_404(client, tmp_path, monkeypatch):
    h, pid, did = await _scaffold(client, tmp_path, monkeypatch)
    # second user
    await client.post("/api/v1/auth/register", json={"email": "z@z.com", "password": "hunter22"})
    tok = (
        await client.post("/api/v1/auth/login", json={"email": "z@z.com", "password": "hunter22"})
    ).json()["access_token"]
    h2 = {"Authorization": f"Bearer {tok}"}
    resp = await client.post(
        f"/api/v1/projects/{pid}/documents/{did}/annotations",
        json={"output": [{"x": 1}]},
        headers=h2,
    )
    assert resp.status_code == 404
