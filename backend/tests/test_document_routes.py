import io

import pytest


async def _auth_and_project(client) -> tuple[dict, int]:
    await client.post("/api/v1/auth/register", json={"email": "d@d.com", "password": "hunter22"})
    tok = (
        await client.post("/api/v1/auth/login", json={"email": "d@d.com", "password": "hunter22"})
    ).json()["access_token"]
    h = {"Authorization": f"Bearer {tok}"}
    pid = (await client.post("/api/v1/projects", json={"name": "P"}, headers=h)).json()["id"]
    return h, pid


@pytest.mark.asyncio
async def test_upload_two_files(client, tmp_path, monkeypatch):
    monkeypatch.setattr("app.services.storage.settings.storage_root", str(tmp_path))
    h, pid = await _auth_and_project(client)
    files = [
        ("files", ("a.pdf", io.BytesIO(b"AAA"), "application/pdf")),
        ("files", ("b.pdf", io.BytesIO(b"BB"), "application/pdf")),
    ]
    resp = await client.post(f"/api/v1/projects/{pid}/documents", files=files, headers=h)
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert len(body) == 2
    assert {d["filename"] for d in body} == {"a.pdf", "b.pdf"}
    assert all(d["status"] == "uploaded" for d in body)


@pytest.mark.asyncio
async def test_list_documents_for_project(client, tmp_path, monkeypatch):
    monkeypatch.setattr("app.services.storage.settings.storage_root", str(tmp_path))
    h, pid = await _auth_and_project(client)
    await client.post(
        f"/api/v1/projects/{pid}/documents",
        files=[("files", ("a.pdf", io.BytesIO(b"AAA"), "application/pdf"))],
        headers=h,
    )
    resp = await client.get(f"/api/v1/projects/{pid}/documents", headers=h)
    assert resp.status_code == 200
    assert len(resp.json()) == 1


@pytest.mark.asyncio
async def test_upload_into_other_workspace_404(client, tmp_path, monkeypatch):
    monkeypatch.setattr("app.services.storage.settings.storage_root", str(tmp_path))
    h1, pid = await _auth_and_project(client)
    # second user
    await client.post("/api/v1/auth/register", json={"email": "z@z.com", "password": "hunter22"})
    tok = (
        await client.post("/api/v1/auth/login", json={"email": "z@z.com", "password": "hunter22"})
    ).json()["access_token"]
    h2 = {"Authorization": f"Bearer {tok}"}
    resp = await client.post(
        f"/api/v1/projects/{pid}/documents",
        files=[("files", ("a.pdf", io.BytesIO(b"AAA"), "application/pdf"))],
        headers=h2,
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_document_detail(client, tmp_path, monkeypatch):
    monkeypatch.setattr("app.services.storage.settings.storage_root", str(tmp_path))
    h, pid = await _auth_and_project(client)
    did = (
        await client.post(
            f"/api/v1/projects/{pid}/documents",
            files=[("files", ("a.pdf", io.BytesIO(b"AAA"), "application/pdf"))],
            headers=h,
        )
    ).json()[0]["id"]
    resp = await client.get(f"/api/v1/projects/{pid}/documents/{did}", headers=h)
    assert resp.status_code == 200
    body = resp.json()
    assert body["filename"] == "a.pdf"
    assert body["latest_prediction"] is None
    assert body["latest_annotation"] is None
