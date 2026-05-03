import pytest

from app.models.auto_research_run import (
    AutoResearchRun,
    AutoResearchStatus,
    TerminationReason,
)
from app.models.project import Project
from app.models.user import User
from app.models.workspace import Workspace


@pytest.mark.asyncio
async def test_run_persists(db_session):
    user = User(email="ar@ar.com", password_hash="x")
    db_session.add(user)
    await db_session.flush()
    ws = Workspace(name="W", owner_id=user.id)
    db_session.add(ws)
    await db_session.flush()
    p = Project(workspace_id=ws.id, name="P", created_by=user.id)
    db_session.add(p)
    await db_session.commit()

    run = AutoResearchRun(
        project_id=p.id,
        status=AutoResearchStatus.RUNNING.value,
        starting_version_id=None,
        output_version_id=None,
        judge_model_id="m1",
        researcher_model_id="m2",
        turn_count=0,
        max_turn=10,
        turn_history=[],
    )
    db_session.add(run)
    await db_session.commit()
    assert run.id is not None


@pytest.mark.asyncio
async def test_invalid_status_rejected(db_session):
    user = User(email="ar2@ar.com", password_hash="x")
    db_session.add(user)
    await db_session.flush()
    ws = Workspace(name="W", owner_id=user.id)
    db_session.add(ws)
    await db_session.flush()
    p = Project(workspace_id=ws.id, name="P", created_by=user.id)
    db_session.add(p)
    await db_session.commit()
    run = AutoResearchRun(
        project_id=p.id,
        status="bogus",
        judge_model_id="m",
        researcher_model_id="m",
        turn_count=0,
        max_turn=10,
        turn_history=[],
    )
    db_session.add(run)
    with pytest.raises(Exception):
        await db_session.commit()
