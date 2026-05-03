import pytest

from app.engine.recompute import recompute_project_score, vibe_check_predictions_query
from app.engine.score import HumanVerdict, JudgeVerdict
from app.models.annotation import Annotation, AnnotationRole, AnnotationStatus
from app.models.document import Document
from app.models.prediction import Prediction, PredictionStatus
from app.models.project import Project
from app.models.project_version import ProjectVersion, VersionSource
from app.models.user import User
from app.models.workspace import Workspace


async def _setup_with_two_docs(db_session) -> tuple[int, int, list[int]]:
    user = User(email="rc@rc.com", password_hash="x")
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
        model_id_snapshot="m",
        counterexample_ids=[],
        source=VersionSource.INITIAL.value,
        source_metadata={},
        created_by=user.id,
    )
    db_session.add(v)
    await db_session.flush()
    p.active_version_id = v.id
    docs: list[int] = []
    for n in ("a", "b"):
        d = Document(
            project_id=p.id,
            filename=n,
            file_path=f"/tmp/{n}",
            mime_type="application/pdf",
            page_count=1,
            byte_size=1,
            uploaded_by=user.id,
        )
        db_session.add(d)
        await db_session.flush()
        docs.append(d.id)
    await db_session.commit()
    return user.id, p.id, docs


@pytest.mark.asyncio
async def test_vibe_check_excludes_documents_with_saved_annotation(db_session):
    uid, pid, docs = await _setup_with_two_docs(db_session)
    # both docs have a prediction
    for did in docs:
        db_session.add(
            Prediction(
                document_id=did,
                project_version_id=None,
                model_id="m",
                prompt_hash="h",
                output=[{"a": 1}],
                per_field_confidence={"0": {"a": "up"}},
                status=PredictionStatus.SUCCESS.value,
            )
        )
    await db_session.commit()
    # second doc has saved annotation (covers prediction → excludes from vibe-check)
    db_session.add(
        Annotation(
            document_id=docs[1],
            output=[{"a": 1}],
            role=AnnotationRole.NONE.value,
            status=AnnotationStatus.SAVED.value,
            created_by=uid,
            last_modified_by=uid,
        )
    )
    await db_session.commit()

    vibe_doc_ids = [
        row[0]
        for row in (await db_session.execute(vibe_check_predictions_query(pid))).all()
    ]
    # only doc[0] in vibe-check
    assert set(vibe_doc_ids) == {docs[0]}


@pytest.mark.asyncio
async def test_recompute_score_with_one_judge_up_and_no_counterexamples(db_session):
    uid, pid, docs = await _setup_with_two_docs(db_session)
    db_session.add(
        Prediction(
            document_id=docs[0],
            project_version_id=None,
            model_id="m",
            prompt_hash="h",
            output=[{"a": 1}],
            per_field_confidence={"0": {"a": "up"}},
            status=PredictionStatus.SUCCESS.value,
        )
    )
    await db_session.commit()

    async def rerun(doc_id):
        return []  # ce pool empty so unused

    result = await recompute_project_score(project_id=pid, session=db_session, rerun=rerun)
    # judge says up, human not seen, calibrated 0.8 (prior) → judge_component = 0.8
    # ce empty → ce contributes 1.0; total = 0.7*0.8 + 0.3*1.0 = 0.86
    assert result.score == pytest.approx(0.7 * 0.8 + 0.3 * 1.0, abs=1e-3)
