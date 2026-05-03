import io

import pytest


async def _auth_and_project(client) -> tuple[dict, int]:
    await client.post("/api/v1/auth/register", json={"email": "ex@ex.com", "password": "hunter22"})
    tok = (
        await client.post("/api/v1/auth/login", json={"email": "ex@ex.com", "password": "hunter22"})
    ).json()["access_token"]
    h = {"Authorization": f"Bearer {tok}"}
    pid = (await client.post("/api/v1/projects", json={"name": "P"}, headers=h)).json()["id"]
    return h, pid


@pytest.mark.asyncio
async def test_batch_extract_streams_per_document_events(client, tmp_path, monkeypatch, app):
    monkeypatch.setattr("app.services.storage.settings.storage_root", str(tmp_path))
    h, pid = await _auth_and_project(client)
    await client.post(
        f"/api/v1/projects/{pid}/documents",
        files=[
            ("files", ("a.pdf", io.BytesIO(b"AAA"), "application/pdf")),
            ("files", ("b.pdf", io.BytesIO(b"BB"), "application/pdf")),
        ],
        headers=h,
    )

    from app.engine.providers import get_provider_dep
    from app.engine.providers.fake import FakeProvider

    fake = FakeProvider(canned=[[{"x": "1"}], [{"x": "2"}]])
    app.dependency_overrides[get_provider_dep] = lambda: fake

    resp = await client.post(f"/api/v1/projects/{pid}/extract", headers=h)
    assert resp.status_code == 200
    assert "text/event-stream" in resp.headers["content-type"]
    body = resp.text
    # two `data: {...}` lines at minimum
    assert body.count("event: progress") == 2
    assert body.count("event: done") == 1
