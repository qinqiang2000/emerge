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


@pytest.mark.asyncio
async def test_batch_extract_skips_public_api_documents(
    client, db_session, app, tmp_path, monkeypatch
):
    """Spec §7.1 / dogfood follow-up #1: editor's batch extract must NOT
    pick up `source='public_api'` rows. If a public extraction errored,
    the editor's "Extract all" used to re-run it against the Lab
    `active_version_id` — silently mutating integrator predictions with
    a non-published version. Pin the boundary.
    """
    from sqlalchemy import select

    from app.engine.providers import get_provider_dep
    from app.engine.providers.fake import FakeProvider
    from app.models.document import Document, DocumentSource, DocumentStatus
    from app.models.project import Project
    from tests.conftest import _setup_published_project

    api_code, key = await _setup_published_project(client, db_session, monkeypatch, tmp_path)
    proj = (
        await db_session.execute(select(Project).where(Project.api_code == api_code))
    ).scalar_one()

    # Forge an ERRORED public_api Document directly (a real failed extract
    # would land here too).
    leaked = Document(
        project_id=proj.id,
        filename="leaked.pdf",
        file_path="/tmp/leaked.pdf",
        mime_type="application/pdf",
        page_count=0,
        byte_size=3,
        uploaded_by=0,
        status=DocumentStatus.ERRORED.value,
        source=DocumentSource.PUBLIC_API.value,
    )
    db_session.add(leaked)
    await db_session.commit()
    await db_session.refresh(leaked)

    fake = FakeProvider(canned=[[{"shop_name": "X"}]])
    app.dependency_overrides[get_provider_dep] = lambda: fake

    tok = (
        await client.post(
            "/api/v1/auth/login", json={"email": "px@px.com", "password": "hunter22"}
        )
    ).json()["access_token"]
    h = {"Authorization": f"Bearer {tok}"}
    resp = await client.post(f"/api/v1/projects/{proj.id}/extract", headers=h)
    assert resp.status_code == 200
    body = resp.text
    # The leaked public_api Document.id must NEVER appear in any
    # progress event for the editor's batch extract.
    assert f'"document_id": {leaked.id}' not in body, body
