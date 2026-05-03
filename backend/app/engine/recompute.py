from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from sqlalchemy import Select, and_, exists, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.engine.regression import counterexample_regression_score
from app.engine.score import (
    HumanVerdict,
    JudgeVerdict,
    beta_posterior,
    compute_judge_component,
    compute_score,
    precision_point_estimate,
)
from app.models.annotation import Annotation, AnnotationRole, AnnotationStatus
from app.models.document import Document
from app.models.judge_calibration import JudgeCalibration
from app.models.prediction import Prediction

DEFAULT_JUDGE_MODEL_VERSION = "claude-opus-4-7"


def vibe_check_predictions_query(project_id: int) -> Select:
    """Spec §4.1: doc_ids of Documents in project whose latest Prediction is NOT covered
    by a saved Annotation(role='none'). An Annotation covers a Prediction when either
    (a) Annotation.parent_prediction_id IS NULL (doc-level cover, regardless of which
    prediction was active when the user saved), or (b) parent_prediction_id equals the
    document's latest Prediction.id. Re-extraction produces a new Prediction whose id
    exceeds prior parent_prediction_ids, so a doc with a stale parent-pinned annotation
    correctly re-enters vibe-check.

    NB: Annotation.id and Prediction.id are independent autoincrement sequences, so
    bare id comparison across the two tables would not be a reliable temporal check.
    """
    latest_pred_id = (
        select(func.max(Prediction.id))
        .where(Prediction.document_id == Document.id)
        .correlate(Document)
        .scalar_subquery()
    )
    covered_by_annotation = exists().where(
        and_(
            Annotation.document_id == Document.id,
            Annotation.role == AnnotationRole.NONE.value,
            Annotation.status == AnnotationStatus.SAVED.value,
            or_(
                Annotation.parent_prediction_id.is_(None),
                Annotation.parent_prediction_id == latest_pred_id,
            ),
        )
    )
    has_prediction = exists().where(Prediction.document_id == Document.id)
    return select(Document.id).where(
        Document.project_id == project_id, has_prediction, ~covered_by_annotation
    )


@dataclass
class ProjectScoreResult:
    score: float
    judge_component: float
    ce_component: float
    observation_count: int
    vibe_check_size: int


async def recompute_project_score(
    *,
    project_id: int,
    session: AsyncSession,
    rerun: Callable[[int], Awaitable[list[dict]]] | None,
    judge_model_version: str = DEFAULT_JUDGE_MODEL_VERSION,
) -> ProjectScoreResult:
    """`rerun=None` means the live extraction provider is not wired in this call site
    (e.g. the public /score endpoint until R6/R7 plumb the production Provider). In that
    case CE regression is skipped and ce_score=None per spec §4.1 fallback (empty pool
    treated as 1.0). Pass a real callable from contexts that can re-run extraction.
    """
    # 1. find vibe-check docs and their latest predictions
    doc_ids = (
        await session.execute(vibe_check_predictions_query(project_id))
    ).scalars().all()
    pairs: list[tuple[JudgeVerdict, HumanVerdict]] = []
    for did in doc_ids:
        latest = (
            await session.execute(
                select(Prediction)
                .where(Prediction.document_id == did)
                .order_by(Prediction.id.desc())
                .limit(1)
            )
        ).scalar_one()
        for ent_idx, fields in (latest.per_field_confidence or {}).items():
            for fname, verdict_str in fields.items():
                try:
                    j = JudgeVerdict(verdict_str)
                except ValueError:
                    continue
                pairs.append((j, HumanVerdict.NOT_SEEN))

    # 2. calibration → judge_precision_calibrated
    cal = (
        await session.execute(
            select(JudgeCalibration).where(
                JudgeCalibration.project_id == project_id,
                JudgeCalibration.judge_model_version == judge_model_version,
            )
        )
    ).scalar_one_or_none()
    tp = cal.tp if cal else 0
    fp = cal.fp if cal else 0
    a, b = beta_posterior(tp=tp, fp=fp)
    calibrated = precision_point_estimate(a, b)

    # 3. judge component
    judge_component = compute_judge_component(pairs, judge_precision_calibrated=calibrated)

    # 4. counterexample regression
    ce_rows = (
        await session.execute(
            select(Annotation)
            .join(Document, Document.id == Annotation.document_id)
            .where(
                Document.project_id == project_id,
                Annotation.role == AnnotationRole.COUNTEREXAMPLE.value,
                Annotation.status == AnnotationStatus.SAVED.value,
            )
        )
    ).scalars().all()
    ce_score: float | None
    if not ce_rows or rerun is None:
        ce_score = None
        ce_component_for_return = 1.0
    else:
        items = [{"document_id": ann.document_id, "expected": ann.output} for ann in ce_rows]
        ce_score = await counterexample_regression_score(counterexamples=items, rerun=rerun)
        ce_component_for_return = ce_score

    # 5. compose
    score = compute_score(judge_component=judge_component, ce_score=ce_score)
    return ProjectScoreResult(
        score=score,
        judge_component=judge_component,
        ce_component=ce_component_for_return,
        observation_count=len(pairs),
        vibe_check_size=len(doc_ids),
    )


async def record_human_verdict_pair(
    *,
    session: AsyncSession,
    project_id: int,
    judge_model_version: str,
    judge_verdict: JudgeVerdict,
    human_fixed: bool,
) -> JudgeCalibration:
    """Update calibration counts.
    - judge=up, human did not fix → tp += 1
    - judge=up, human fixed → fp += 1
    - judge=down/uncertain, human fixed → fn += 1
    - judge=down/uncertain, human did not fix → tn += 1
    """
    cal = (
        await session.execute(
            select(JudgeCalibration).where(
                JudgeCalibration.project_id == project_id,
                JudgeCalibration.judge_model_version == judge_model_version,
            )
        )
    ).scalar_one_or_none()
    if cal is None:
        cal = JudgeCalibration(
            project_id=project_id, judge_model_version=judge_model_version
        )
        session.add(cal)
        await session.flush()

    if judge_verdict is JudgeVerdict.UP and not human_fixed:
        cal.tp += 1
    elif judge_verdict is JudgeVerdict.UP and human_fixed:
        cal.fp += 1
    elif judge_verdict in (JudgeVerdict.DOWN, JudgeVerdict.UNCERTAIN) and human_fixed:
        cal.fn += 1
    else:
        cal.tn += 1
    cal.observation_count += 1
    await session.commit()
    await session.refresh(cal)
    return cal
