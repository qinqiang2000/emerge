import pytest

from app.models.project import Project
from app.models.project_version import ProjectVersion, VersionSource
from app.models.user import User
from app.models.workspace import Workspace


@pytest.mark.asyncio
async def test_project_version_persists(db_session):
    user = User(email="v@v.com", password_hash="x")
    db_session.add(user)
    await db_session.flush()
    ws = Workspace(name="W", owner_id=user.id)
    db_session.add(ws)
    await db_session.flush()
    p = Project(workspace_id=ws.id, name="P", created_by=user.id)
    db_session.add(p)
    await db_session.flush()

    v = ProjectVersion(
        project_id=p.id,
        version_number=0,
        schema_snapshot=[],
        global_notes_snapshot="",
        model_id_snapshot="claude-opus-4-7",
        counterexample_ids=[],
        source=VersionSource.INITIAL.value,
        source_metadata={},
        created_by=user.id,
    )
    db_session.add(v)
    await db_session.commit()
    await db_session.refresh(v)
    assert v.id is not None
    assert v.version_number == 0


@pytest.mark.asyncio
async def test_invalid_source_rejected(db_session):
    user = User(email="vv@v.com", password_hash="x")
    db_session.add(user)
    await db_session.flush()
    ws = Workspace(name="W", owner_id=user.id)
    db_session.add(ws)
    await db_session.flush()
    p = Project(workspace_id=ws.id, name="P", created_by=user.id)
    db_session.add(p)
    await db_session.flush()
    v = ProjectVersion(
        project_id=p.id,
        version_number=0,
        schema_snapshot=[],
        global_notes_snapshot="",
        model_id_snapshot="x",
        counterexample_ids=[],
        source="bogus",
        source_metadata={},
        created_by=user.id,
    )
    db_session.add(v)
    with pytest.raises(Exception):
        await db_session.commit()
