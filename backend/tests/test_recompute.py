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


@pytest.mark.asyncio
async def test_recompute_score_is_doc_weighted_not_field_weighted(db_session):
    """Spec §4.1: per-Project score = mean of per-Document scores. A doc with
    many fields must not dominate a doc with few fields when computing the
    project-level number — otherwise long-line-item invoices would swamp the
    short ones in the project-level signal.
    """
    uid, pid, docs = await _setup_with_two_docs(db_session)
    # doc[0]: single field, judge says up → doc_judge = 0.8 (calibrated prior)
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
    # doc[1]: three fields, all judge=down with NOT_SEEN human → doc_judge = 0.0
    db_session.add(
        Prediction(
            document_id=docs[1],
            project_version_id=None,
            model_id="m",
            prompt_hash="h2",
            output=[{"x": 1, "y": 2, "z": 3}],
            per_field_confidence={"0": {"x": "down", "y": "down", "z": "down"}},
            status=PredictionStatus.SUCCESS.value,
        )
    )
    await db_session.commit()

    async def rerun(_doc_id):
        return []

    result = await recompute_project_score(project_id=pid, session=db_session, rerun=rerun)
    # doc-weighted: (0.8 + 0.0) / 2 = 0.4
    # field-weighted (wrong) would give (0.8 + 0 + 0 + 0) / 4 = 0.2
    assert result.judge_component == pytest.approx(0.4, abs=1e-3)
    # composite score = 0.7*0.4 + 0.3*1.0 = 0.58
    assert result.score == pytest.approx(0.7 * 0.4 + 0.3 * 1.0, abs=1e-3)
    # observation_count is total verdicts across the vibe-check set
    assert result.observation_count == 4


@pytest.mark.asyncio
async def test_vibe_check_re_includes_doc_after_re_extraction(db_session):
    """Spec §4.1: a doc whose old saved annotation pre-dates a newly generated
    Prediction (e.g. after schema update) re-enters the vibe-check set, because
    the latest Prediction is not covered by a *later* Annotation.
    """
    uid, pid, docs = await _setup_with_two_docs(db_session)
    did = docs[0]
    p1 = Prediction(
        document_id=did,
        project_version_id=None,
        model_id="m",
        prompt_hash="h",
        output=[{"a": 1}],
        per_field_confidence={"0": {"a": "up"}},
        status=PredictionStatus.SUCCESS.value,
    )
    db_session.add(p1)
    await db_session.flush()
    db_session.add(
        Annotation(
            document_id=did,
            parent_prediction_id=p1.id,
            output=[{"a": 1}],
            role=AnnotationRole.NONE.value,
            status=AnnotationStatus.SAVED.value,
            created_by=uid,
            last_modified_by=uid,
        )
    )
    await db_session.commit()
    before = (
        await db_session.execute(vibe_check_predictions_query(pid))
    ).scalars().all()
    assert did not in before

    db_session.add(
        Prediction(
            document_id=did,
            project_version_id=None,
            model_id="m",
            prompt_hash="h2",
            output=[{"a": 2}],
            per_field_confidence={"0": {"a": "up"}},
            status=PredictionStatus.SUCCESS.value,
        )
    )
    await db_session.commit()
    after = (
        await db_session.execute(vibe_check_predictions_query(pid))
    ).scalars().all()
    assert did in after
