import pytest

from app.models.annotation import Annotation, AnnotationRole, AnnotationStatus
from app.models.document import Document
from app.models.project import Project
from app.models.user import User
from app.models.workspace import Workspace


@pytest.mark.asyncio
async def test_annotation_persists_with_role_none(db_session):
    user = User(email="a@a.com", password_hash="x")
    db_session.add(user)
    await db_session.flush()
    ws = Workspace(name="W", owner_id=user.id)
    db_session.add(ws)
    await db_session.flush()
    p = Project(workspace_id=ws.id, name="P", created_by=user.id)
    db_session.add(p)
    await db_session.flush()
    d = Document(
        project_id=p.id,
        filename="x.pdf",
        file_path="/tmp/x",
        mime_type="application/pdf",
        page_count=1,
        byte_size=10,
        uploaded_by=user.id,
    )
    db_session.add(d)
    await db_session.flush()

    ann = Annotation(
        document_id=d.id,
        output=[{"shop": "ABC"}],
        role=AnnotationRole.NONE.value,
        status=AnnotationStatus.SAVED.value,
        created_by=user.id,
        last_modified_by=user.id,
    )
    db_session.add(ann)
    await db_session.commit()
    await db_session.refresh(ann)
    assert ann.id is not None


@pytest.mark.asyncio
async def test_annotation_invalid_role_rejected(db_session):
    user = User(email="b@b.com", password_hash="x")
    db_session.add(user)
    await db_session.flush()
    ws = Workspace(name="W", owner_id=user.id)
    db_session.add(ws)
    await db_session.flush()
    p = Project(workspace_id=ws.id, name="P", created_by=user.id)
    db_session.add(p)
    await db_session.flush()
    d = Document(
        project_id=p.id,
        filename="x.pdf",
        file_path="/tmp/x",
        mime_type="application/pdf",
        page_count=1,
        byte_size=10,
        uploaded_by=user.id,
    )
    db_session.add(d)
    await db_session.flush()

    ann = Annotation(
        document_id=d.id,
        output=[],
        role="growth",  # not allowed
        status="saved",
        created_by=user.id,
        last_modified_by=user.id,
    )
    db_session.add(ann)
    with pytest.raises(Exception):
        await db_session.commit()
