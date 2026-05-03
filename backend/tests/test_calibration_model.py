import pytest

from app.models.judge_calibration import JudgeCalibration
from app.models.project import Project
from app.models.user import User
from app.models.workspace import Workspace


@pytest.mark.asyncio
async def test_calibration_persists(db_session):
    user = User(email="cal@cal.com", password_hash="x")
    db_session.add(user)
    await db_session.flush()
    ws = Workspace(name="W", owner_id=user.id)
    db_session.add(ws)
    await db_session.flush()
    p = Project(workspace_id=ws.id, name="P", created_by=user.id)
    db_session.add(p)
    await db_session.flush()

    c = JudgeCalibration(
        project_id=p.id, judge_model_version="claude-opus-4-7", tp=0, fp=0, fn=0, tn=0
    )
    db_session.add(c)
    await db_session.commit()
    assert c.id is not None


@pytest.mark.asyncio
async def test_unique_per_project_judge(db_session):
    user = User(email="cal2@cal.com", password_hash="x")
    db_session.add(user)
    await db_session.flush()
    ws = Workspace(name="W", owner_id=user.id)
    db_session.add(ws)
    await db_session.flush()
    p = Project(workspace_id=ws.id, name="P", created_by=user.id)
    db_session.add(p)
    await db_session.flush()
    db_session.add(JudgeCalibration(project_id=p.id, judge_model_version="m"))
    await db_session.commit()
    db_session.add(JudgeCalibration(project_id=p.id, judge_model_version="m"))
    with pytest.raises(Exception):
        await db_session.commit()
