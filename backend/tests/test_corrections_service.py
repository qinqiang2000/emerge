import pytest

from app.models.annotation import Annotation, AnnotationRole, AnnotationStatus
from app.models.document import Document
from app.models.prediction import Prediction, PredictionStatus
from app.models.project import Project
from app.models.project_version import ProjectVersion, VersionSource
from app.models.user import User
from app.models.workspace import Workspace
from app.services.corrections import (
    PredictionScopeError,
    save_correction,
    save_counterexample,
)


async def _scaffold(db_session) -> tuple[int, int, int]:
    """Returns (user_id, project_id, document_id)."""
    user = User(email="c@c.com", password_hash="x")
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
        source=VersionSource.INITIAL.value,
        source_metadata={},
        created_by=user.id,
    )
    db_session.add(v)
    await db_session.flush()
    p.active_version_id = v.id
    d = Document(
        project_id=p.id,
        filename="f",
        file_path="/tmp/f",
        mime_type="application/pdf",
        page_count=1,
        byte_size=1,
        uploaded_by=user.id,
    )
    db_session.add(d)
    await db_session.commit()
    return user.id, p.id, d.id


@pytest.mark.asyncio
async def test_save_correction_creates_role_none(db_session):
    uid, pid, did = await _scaffold(db_session)
    ann = await save_correction(
        session=db_session,
        document_id=did,
        output=[{"shop_name": "X"}],
        user_id=uid,
        notes="manual edit",
    )
    assert ann.role == AnnotationRole.NONE.value
    assert ann.status == AnnotationStatus.SAVED.value
    assert ann.created_by == uid
    assert ann.last_modified_by == uid


@pytest.mark.asyncio
async def test_save_counterexample_creates_role_counterexample(db_session):
    uid, pid, did = await _scaffold(db_session)
    pred = Prediction(
        document_id=did,
        project_version_id=None,
        model_id="m",
        prompt_hash="h",
        output=[{"a": 1}],
        per_field_confidence={},
        status=PredictionStatus.SUCCESS.value,
    )
    db_session.add(pred)
    await db_session.commit()

    ann = await save_counterexample(
        session=db_session,
        project_id=pid,
        prediction_id=pred.id,
        correct_output=[{"a": 99}],
        user_id=uid,
    )
    assert ann.role == AnnotationRole.COUNTEREXAMPLE.value
    assert ann.parent_prediction_id == pred.id


@pytest.mark.asyncio
async def test_save_counterexample_rejects_cross_project_prediction(db_session):
    uid, pid_a, did_a = await _scaffold(db_session)
    # second project + prediction
    user2 = User(email="z@z.com", password_hash="x")
    db_session.add(user2)
    await db_session.flush()
    ws2 = Workspace(name="W2", owner_id=user2.id)
    db_session.add(ws2)
    await db_session.flush()
    p2 = Project(workspace_id=ws2.id, name="P2", created_by=user2.id)
    db_session.add(p2)
    await db_session.flush()
    d2 = Document(
        project_id=p2.id,
        filename="f",
        file_path="/tmp/f",
        mime_type="application/pdf",
        page_count=1,
        byte_size=1,
        uploaded_by=user2.id,
    )
    db_session.add(d2)
    await db_session.flush()
    pred = Prediction(
        document_id=d2.id,
        project_version_id=None,
        model_id="m",
        prompt_hash="h",
        output=[],
        per_field_confidence={},
        status=PredictionStatus.SUCCESS.value,
    )
    db_session.add(pred)
    await db_session.commit()

    with pytest.raises(PredictionScopeError):
        await save_counterexample(
            session=db_session,
            project_id=pid_a,
            prediction_id=pred.id,
            correct_output=[{"x": 1}],
            user_id=uid,
        )


@pytest.mark.asyncio
async def test_save_correction_rejects_parent_prediction_from_other_document(db_session):
    """parent_prediction_id must belong to the same document as the
    correction; otherwise the linkage in DocumentDetailOut.latest_annotation
    and any future provenance display would silently point at someone else's
    prediction. Symmetric to save_counterexample's project-scope guard.
    """
    uid, pid, did = await _scaffold(db_session)
    other_doc = Document(
        project_id=pid,
        filename="other.pdf",
        file_path="/tmp/other",
        mime_type="application/pdf",
        page_count=1,
        byte_size=1,
        uploaded_by=uid,
    )
    db_session.add(other_doc)
    await db_session.flush()
    pred_on_other = Prediction(
        document_id=other_doc.id,
        project_version_id=None,
        model_id="m",
        prompt_hash="h",
        output=[],
        per_field_confidence={},
        status=PredictionStatus.SUCCESS.value,
    )
    db_session.add(pred_on_other)
    await db_session.commit()

    with pytest.raises(PredictionScopeError):
        await save_correction(
            session=db_session,
            document_id=did,
            output=[{"x": 1}],
            user_id=uid,
            parent_prediction_id=pred_on_other.id,
        )


@pytest.mark.asyncio
async def test_save_correction_rejects_unknown_parent_prediction(db_session):
    uid, pid, did = await _scaffold(db_session)
    with pytest.raises(PredictionScopeError):
        await save_correction(
            session=db_session,
            document_id=did,
            output=[{"x": 1}],
            user_id=uid,
            parent_prediction_id=99999,  # does not exist
        )
