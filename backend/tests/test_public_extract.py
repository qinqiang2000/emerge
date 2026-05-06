import io
from datetime import UTC, datetime

import pytest
from sqlalchemy import select

from app.engine.providers import get_provider_dep
from app.engine.providers.fake import FakeProvider
from app.models.api_key import ApiKey
from app.models.project import Project
from app.services.api_key import parse_prefix
from tests.conftest import _setup_published_project


@pytest.mark.asyncio
async def test_extract_returns_entities(client, db_session, app, tmp_path, monkeypatch):
    api_code, key = await _setup_published_project(client, db_session, monkeypatch, tmp_path)

    fake = FakeProvider(canned=[[{"shop_name": "ABC"}]])
    app.dependency_overrides[get_provider_dep] = lambda: fake

    resp = await client.post(
        f"/extract/{api_code}",
        files=[("file", ("a.pdf", io.BytesIO(b"PDF"), "application/pdf"))],
        headers={"X-Api-Key": key},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    # Dogfood follow-up #2: response envelope matches docs/local-demo.md.
    # Top-level entities are gone; an `output` envelope wraps them so future
    # confidence/evidence fields can land without further shape churn.
    # `request_id` mirrors `prediction_id` so feedback POSTs have an obvious
    # source. `project_version` renamed to `project_version_id`.
    assert body["output"]["entities"] == [{"shop_name": "ABC"}]
    assert isinstance(body["prediction_id"], int)
    assert body["request_id"] == body["prediction_id"]
    assert isinstance(body["project_version_id"], int)
    assert "entities" not in body
    assert "project_version" not in body


@pytest.mark.asyncio
async def test_extract_missing_key_401(client, db_session, monkeypatch, tmp_path):
    api_code, _ = await _setup_published_project(client, db_session, monkeypatch, tmp_path)
    resp = await client.post(
        f"/extract/{api_code}",
        files=[("file", ("a.pdf", io.BytesIO(b"PDF"), "application/pdf"))],
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_extract_unknown_api_code_404(client):
    resp = await client.post(
        "/extract/nonexistent",
        files=[("file", ("a.pdf", io.BytesIO(b"PDF"), "application/pdf"))],
        headers={"X-Api-Key": "ek_DEADBEEF-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"},
    )
    # Resolve runs before auth — unknown api_code is always 404, never 401.
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_extract_after_unpublish_returns_403(client, db_session, monkeypatch, tmp_path):
    """Spec §7.2: unpublish → 403 (paused), distinct from 404 (unknown api_code)."""
    api_code, key = await _setup_published_project(client, db_session, monkeypatch, tmp_path)
    tok = (
        await client.post(
            "/api/v1/auth/login", json={"email": "px@px.com", "password": "hunter22"}
        )
    ).json()["access_token"]
    h = {"Authorization": f"Bearer {tok}"}
    pid = (
        await db_session.execute(select(Project).where(Project.api_code == api_code))
    ).scalar_one().id
    await client.post(f"/api/v1/projects/{pid}/unpublish", headers=h)

    resp = await client.post(
        f"/extract/{api_code}",
        files=[("file", ("a.pdf", io.BytesIO(b"PDF"), "application/pdf"))],
        headers={"X-Api-Key": key},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_extract_with_revoked_key_401(client, db_session, app, tmp_path, monkeypatch):
    """Revoked (soft-deleted) keys must be rejected."""
    api_code, key = await _setup_published_project(client, db_session, monkeypatch, tmp_path)
    # find the key and soft-delete it
    prefix = parse_prefix(key)
    row = (
        await db_session.execute(select(ApiKey).where(ApiKey.prefix == prefix))
    ).scalar_one()
    row.deleted_at = datetime.now(tz=UTC)
    await db_session.commit()

    resp = await client.post(
        f"/extract/{api_code}",
        files=[("file", ("a.pdf", io.BytesIO(b"PDF"), "application/pdf"))],
        headers={"X-Api-Key": key},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_public_extract_uses_published_version_not_active(
    client, db_session, app, tmp_path, monkeypatch
):
    """Public API serves published_version_id even when Lab moves to a new
    active version (spec §7.2)."""
    from app.models.project import Project
    from app.models.project_version import ProjectVersion, VersionSource

    api_code, key = await _setup_published_project(client, db_session, monkeypatch, tmp_path)
    proj = (
        await db_session.execute(select(Project).where(Project.api_code == api_code))
    ).scalar_one()
    published_version_id = proj.published_version_id
    assert published_version_id is not None

    # Add a new active version (different schema, unrelated to public API).
    parent = (
        await db_session.execute(
            select(ProjectVersion).where(ProjectVersion.id == proj.active_version_id)
        )
    ).scalar_one()
    new_active = ProjectVersion(
        project_id=proj.id,
        parent_version_id=parent.id,
        version_number=parent.version_number + 1,
        schema_snapshot=[{"name": "different", "type": "string", "description": "x"}],
        global_notes_snapshot="",
        model_id_snapshot="m",
        counterexample_ids=parent.counterexample_ids,
        source=VersionSource.USER_EDIT.value,
        source_metadata={},
        locked=False,
        created_by=parent.created_by,
    )
    db_session.add(new_active)
    await db_session.flush()
    proj.active_version_id = new_active.id
    await db_session.commit()
    assert proj.active_version_id != proj.published_version_id

    fake = FakeProvider(canned=[[{"shop_name": "ABC"}]])
    app.dependency_overrides[get_provider_dep] = lambda: fake

    resp = await client.post(
        f"/extract/{api_code}",
        files=[("file", ("a.pdf", io.BytesIO(b"PDF"), "application/pdf"))],
        headers={"X-Api-Key": key},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["project_version_id"] == published_version_id


@pytest.mark.asyncio
async def test_public_extract_creates_public_api_document(
    client, db_session, app, tmp_path, monkeypatch
):
    """Spec §7.1: public-API extracts must NOT pollute the Lab Documents list."""
    api_code, key = await _setup_published_project(client, db_session, monkeypatch, tmp_path)
    fake = FakeProvider(canned=[[{"shop_name": "ABC"}]])
    app.dependency_overrides[get_provider_dep] = lambda: fake

    resp = await client.post(
        f"/extract/{api_code}",
        files=[("file", ("a.pdf", io.BytesIO(b"PDF"), "application/pdf"))],
        headers={"X-Api-Key": key},
    )
    assert resp.status_code == 200, resp.text

    from app.models.document import Document, DocumentSource
    docs = (await db_session.execute(select(Document))).scalars().all()
    assert any(d.source == DocumentSource.PUBLIC_API.value for d in docs), (
        [d.source for d in docs]
    )


@pytest.mark.asyncio
async def test_editor_list_documents_excludes_public_api(
    client, db_session, app, tmp_path, monkeypatch
):
    """Editor's /documents must hide rows created by integrator traffic."""
    api_code, key = await _setup_published_project(client, db_session, monkeypatch, tmp_path)
    fake = FakeProvider(canned=[[{"shop_name": "ABC"}]])
    app.dependency_overrides[get_provider_dep] = lambda: fake

    await client.post(
        f"/extract/{api_code}",
        files=[("file", ("public.pdf", io.BytesIO(b"PDF"), "application/pdf"))],
        headers={"X-Api-Key": key},
    )

    tok = (
        await client.post(
            "/api/v1/auth/login", json={"email": "px@px.com", "password": "hunter22"}
        )
    ).json()["access_token"]
    h = {"Authorization": f"Bearer {tok}"}
    pid = (
        await db_session.execute(select(Project).where(Project.api_code == api_code))
    ).scalar_one().id
    listed = (
        await client.get(f"/api/v1/projects/{pid}/documents", headers=h)
    ).json()
    assert all(d["filename"] != "public.pdf" for d in listed), listed


@pytest.mark.asyncio
async def test_public_extract_forbidden_when_published_pointer_missing(
    client, db_session, app, tmp_path, monkeypatch
):
    """If api_published_at is set but published_version_id is None, refuse to serve."""
    from app.models.project import Project

    api_code, key = await _setup_published_project(client, db_session, monkeypatch, tmp_path)
    proj = (
        await db_session.execute(select(Project).where(Project.api_code == api_code))
    ).scalar_one()
    proj.published_version_id = None
    await db_session.commit()

    resp = await client.post(
        f"/extract/{api_code}",
        files=[("file", ("a.pdf", io.BytesIO(b"PDF"), "application/pdf"))],
        headers={"X-Api-Key": key},
    )
    assert resp.status_code == 403
