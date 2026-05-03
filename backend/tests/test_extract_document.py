import pytest

from app.engine.extract import extract_document
from app.engine.providers.fake import FakeProvider
from app.models.document import Document, DocumentStatus
from app.models.prediction import Prediction
from app.models.project import Project
from app.models.project_version import ProjectVersion, VersionSource
from app.models.user import User
from app.models.workspace import Workspace


async def _setup(db_session, schema=None):
    user = User(email="e@e.com", password_hash="x")
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
        schema_snapshot=schema or [],
        global_notes_snapshot="",
        model_id_snapshot="any-model",
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
        filename="x.pdf",
        file_path="/tmp/x.pdf",
        mime_type="application/pdf",
        page_count=1,
        byte_size=10,
        uploaded_by=user.id,
    )
    db_session.add(d)
    await db_session.commit()
    return p, v, d


@pytest.mark.asyncio
async def test_extract_writes_prediction_and_flips_status(db_session, tmp_path):
    p, v, d = await _setup(db_session)
    fp = tmp_path / "x.pdf"
    fp.write_bytes(b"PDF")
    d.file_path = str(fp)
    await db_session.commit()

    fake = FakeProvider(canned=[[{"shop_name": "ABC"}]])
    pred = await extract_document(d.id, session=db_session, provider=fake)
    assert pred.output == [{"shop_name": "ABC"}]
    assert pred.status == "success"
    await db_session.refresh(d)
    assert d.status == DocumentStatus.EXTRACTED.value


@pytest.mark.asyncio
async def test_extract_failure_sets_errored(db_session, tmp_path):
    p, v, d = await _setup(db_session)
    fp = tmp_path / "x.pdf"
    fp.write_bytes(b"PDF")
    d.file_path = str(fp)
    await db_session.commit()

    fake = FakeProvider(canned=[RuntimeError("boom")])
    pred = await extract_document(d.id, session=db_session, provider=fake)
    assert pred.status == "failed"
    assert pred.error_message and "boom" in pred.error_message
    await db_session.refresh(d)
    assert d.status == DocumentStatus.ERRORED.value
