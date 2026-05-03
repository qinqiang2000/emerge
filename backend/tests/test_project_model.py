import pytest

from app.models.project import Project
from app.models.user import User
from app.models.workspace import Workspace


@pytest.mark.asyncio
async def test_project_persists(db_session):
    user = User(email="o@o.com", password_hash="x")
    db_session.add(user)
    await db_session.flush()
    ws = Workspace(name="W", owner_id=user.id)
    db_session.add(ws)
    await db_session.flush()
    p = Project(workspace_id=ws.id, name="Receipts", created_by=user.id)
    db_session.add(p)
    await db_session.commit()
    await db_session.refresh(p)
    assert p.id is not None
    assert p.api_code is None
    assert p.active_version_id is None


@pytest.mark.asyncio
async def test_api_code_is_unique_per_workspace(db_session):
    user = User(email="u@u.com", password_hash="x")
    db_session.add(user)
    await db_session.flush()
    ws = Workspace(name="W", owner_id=user.id)
    db_session.add(ws)
    await db_session.flush()
    db_session.add(Project(workspace_id=ws.id, name="A", created_by=user.id, api_code="x"))
    await db_session.commit()
    db_session.add(Project(workspace_id=ws.id, name="B", created_by=user.id, api_code="x"))
    with pytest.raises(Exception):
        await db_session.commit()
