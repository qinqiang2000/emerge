import asyncio
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db import get_session
from app.main import create_app
from app.models.base import Base
from app.models.project import Project
from app.models.project_version import ProjectVersion


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture
async def db_engine():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(db_engine) -> AsyncIterator[AsyncSession]:
    factory = async_sessionmaker(db_engine, expire_on_commit=False)
    async with factory() as session:
        from app.services.builtin_templates import seed_builtin_templates

        await seed_builtin_templates(session)
        yield session


@pytest_asyncio.fixture
async def app(db_session, db_engine):
    import app.db as db_module
    from app.engine.providers import get_provider_dep
    from app.engine.providers.fake import FakeProvider

    application = create_app()

    async def _override_session():
        yield db_session

    application.dependency_overrides[get_session] = _override_session
    # Default to FakeProvider so tests that don't exercise extraction don't need
    # a real API key.  Tests that need specific canned outputs override this again.
    application.dependency_overrides[get_provider_dep] = lambda: FakeProvider(canned=[])

    # Also swap SessionFactory so background tasks (extraction) hit the test's engine
    original_factory = db_module.SessionFactory
    db_module.SessionFactory = async_sessionmaker(db_engine, expire_on_commit=False)
    try:
        yield application
    finally:
        db_module.SessionFactory = original_factory


@pytest_asyncio.fixture
async def client(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://t") as c:
        yield c


async def _setup_published_project(client, db_session, monkeypatch, tmp_path) -> tuple[str, str]:
    """Returns (api_code, api_key) for a published project with a locked active version."""
    monkeypatch.setattr("app.services.storage.settings.storage_root", str(tmp_path))
    await client.post("/api/v1/auth/register", json={"email": "px@px.com", "password": "hunter22"})
    tok = (
        await client.post("/api/v1/auth/login", json={"email": "px@px.com", "password": "hunter22"})
    ).json()["access_token"]
    h = {"Authorization": f"Bearer {tok}"}
    pid = (await client.post("/api/v1/projects", json={"name": "P"}, headers=h)).json()["id"]
    await client.patch(
        f"/api/v1/projects/{pid}/schema",
        json={
            "schema": [{"name": "shop_name", "type": "string", "description": "店名"}],
            "global_notes": "",
            "model_id": "m",
        },
        headers=h,
    )
    proj = (await db_session.execute(select(Project).where(Project.id == pid))).scalar_one()
    v = (
        await db_session.execute(
            select(ProjectVersion).where(ProjectVersion.id == proj.active_version_id)
        )
    ).scalar_one()
    v.locked = True
    await db_session.commit()

    await client.post(
        f"/api/v1/projects/{pid}/publish", json={"api_code": "test-receipts"}, headers=h
    )
    key = (
        await client.post(
            f"/api/v1/projects/{pid}/api-keys", json={"name": "default"}, headers=h
        )
    ).json()["key"]
    return "test-receipts", key
