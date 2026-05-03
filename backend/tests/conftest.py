import asyncio
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db import get_session
from app.main import create_app
from app.models.base import Base


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
