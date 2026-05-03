import pytest

from app.engine.judge import FakeJudgeProvider, run_judge
from app.engine.score import JudgeVerdict
from app.models.document import Document
from app.models.prediction import Prediction, PredictionStatus
from app.models.project import Project
from app.models.project_version import ProjectVersion, VersionSource
from app.models.user import User
from app.models.workspace import Workspace
from app.schemas.schema_field import FieldType, SchemaField


async def _scaffold(db_session) -> tuple[Project, ProjectVersion, Document, Prediction]:
    user = User(email="j@j.com", password_hash="x")
    db_session.add(user)
    await db_session.flush()
    ws = Workspace(name="W", owner_id=user.id)
    db_session.add(ws)
    await db_session.flush()
    p = Project(workspace_id=ws.id, name="P", created_by=user.id)
    db_session.add(p)
    await db_session.flush()
    fields = [SchemaField(name="shop_name", type=FieldType.STRING, description="d")]
    v = ProjectVersion(
        project_id=p.id,
        version_number=0,
        schema_snapshot=[f.model_dump() for f in fields],
        global_notes_snapshot="",
        model_id_snapshot="m",
        counterexample_ids=[],
        source=VersionSource.INITIAL.value,
        source_metadata={},
        created_by=user.id,
    )
    db_session.add(v)
    await db_session.flush()
    p.active_version_id = v.id
    d = Document(
        project_id=p.id,
        filename="x",
        file_path="/tmp/x",
        mime_type="application/pdf",
        page_count=1,
        byte_size=1,
        uploaded_by=user.id,
    )
    db_session.add(d)
    await db_session.flush()
    pred = Prediction(
        document_id=d.id,
        project_version_id=v.id,
        model_id="m",
        prompt_hash="h",
        output=[{"shop_name": "ABC"}],
        per_field_confidence={},
        status=PredictionStatus.SUCCESS.value,
    )
    db_session.add(pred)
    await db_session.commit()
    return p, v, d, pred


@pytest.mark.asyncio
async def test_run_judge_writes_per_field_confidence(db_session, tmp_path):
    p, v, d, pred = await _scaffold(db_session)
    fp = tmp_path / "x"
    fp.write_bytes(b"PDF")
    d.file_path = str(fp)
    await db_session.commit()

    fake = FakeJudgeProvider(canned=[{"0": {"shop_name": "up"}}])
    await run_judge(pred.id, session=db_session, judge=fake)
    await db_session.refresh(pred)
    assert pred.per_field_confidence == {"0": {"shop_name": "up"}}


@pytest.mark.asyncio
async def test_run_judge_failure_records_empty(db_session, tmp_path):
    p, v, d, pred = await _scaffold(db_session)
    fp = tmp_path / "x"
    fp.write_bytes(b"PDF")
    d.file_path = str(fp)
    await db_session.commit()

    fake = FakeJudgeProvider(canned=[RuntimeError("judge boom")])
    await run_judge(pred.id, session=db_session, judge=fake)
    await db_session.refresh(pred)
    # judge failure is non-fatal — confidence stays {}; UI shows "judge unavailable"
    assert pred.per_field_confidence == {}


@pytest.mark.asyncio
async def test_run_judge_tolerates_unpinned_project_version(db_session, tmp_path):
    """A Prediction whose project_version_id is NULL (legacy / test fixture state)
    must not crash run_judge. The judge runs with the bare system frame.
    """
    p, v, d, pred = await _scaffold(db_session)
    pred.project_version_id = None
    fp = tmp_path / "x"
    fp.write_bytes(b"PDF")
    d.file_path = str(fp)
    await db_session.commit()

    fake = FakeJudgeProvider(canned=[{"0": {"shop_name": "up"}}])
    await run_judge(pred.id, session=db_session, judge=fake)
    await db_session.refresh(pred)
    assert pred.per_field_confidence == {"0": {"shop_name": "up"}}
