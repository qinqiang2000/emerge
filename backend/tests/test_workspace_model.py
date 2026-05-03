import pytest

from app.models.user import User
from app.models.workspace import Workspace, WorkspaceMembership, WorkspaceRole


@pytest.mark.asyncio
async def test_workspace_with_owner_membership(db_session):
    user = User(email="owner@example.com", password_hash="x")
    db_session.add(user)
    await db_session.flush()
    ws = Workspace(name="Team A", owner_id=user.id)
    db_session.add(ws)
    await db_session.flush()
    db_session.add(
        WorkspaceMembership(workspace_id=ws.id, user_id=user.id, role=WorkspaceRole.OWNER)
    )
    await db_session.commit()
    assert ws.id is not None


@pytest.mark.asyncio
async def test_membership_role_check(db_session):
    user = User(email="u@u.com", password_hash="x")
    db_session.add(user)
    await db_session.flush()
    ws = Workspace(name="W", owner_id=user.id)
    db_session.add(ws)
    await db_session.flush()
    db_session.add(WorkspaceMembership(workspace_id=ws.id, user_id=user.id, role="bogus"))
    with pytest.raises(Exception):
        await db_session.commit()
