import pytest

from app.models.document import Document, DocumentSource, DocumentStatus
from app.models.project import Project
from app.models.user import User
from app.models.workspace import Workspace


async def _make_project(db_session) -> tuple[int, int]:
    user = User(email="d@d.com", password_hash="x")
    db_session.add(user)
    await db_session.flush()
    ws = Workspace(name="W", owner_id=user.id)
    db_session.add(ws)
    await db_session.flush()
    p = Project(workspace_id=ws.id, name="P", created_by=user.id)
    db_session.add(p)
    await db_session.flush()
    return p.id, user.id


@pytest.mark.asyncio
async def test_document_persists_with_default_status(db_session):
    pid, uid = await _make_project(db_session)
    d = Document(
        project_id=pid,
        filename="r.pdf",
        file_path="/tmp/r.pdf",
        mime_type="application/pdf",
        page_count=2,
        byte_size=1024,
        uploaded_by=uid,
    )
    db_session.add(d)
    await db_session.commit()
    await db_session.refresh(d)
    assert d.status == DocumentStatus.UPLOADED.value
    assert d.data == {}


@pytest.mark.asyncio
async def test_document_invalid_status_rejected(db_session):
    pid, uid = await _make_project(db_session)
    d = Document(
        project_id=pid,
        filename="x.pdf",
        file_path="/tmp/x.pdf",
        mime_type="application/pdf",
        page_count=1,
        byte_size=10,
        uploaded_by=uid,
        status="bogus",
    )
    db_session.add(d)
    with pytest.raises(Exception):
        await db_session.commit()


@pytest.mark.asyncio
async def test_document_source_defaults_to_lab(db_session):
    pid, uid = await _make_project(db_session)
    d = Document(
        project_id=pid,
        filename="r.pdf",
        file_path="/tmp/r.pdf",
        mime_type="application/pdf",
        page_count=0,
        byte_size=10,
        uploaded_by=uid,
    )
    db_session.add(d)
    await db_session.commit()
    await db_session.refresh(d)
    assert d.source == DocumentSource.LAB.value


@pytest.mark.asyncio
async def test_document_source_rejects_unknown(db_session):
    pid, uid = await _make_project(db_session)
    d = Document(
        project_id=pid,
        filename="x.pdf",
        file_path="/tmp/x.pdf",
        mime_type="application/pdf",
        page_count=0,
        byte_size=10,
        uploaded_by=uid,
        source="floofs",
    )
    db_session.add(d)
    with pytest.raises(Exception):
        await db_session.commit()
