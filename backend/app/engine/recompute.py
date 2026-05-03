from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from sqlalchemy import Select, and_, exists, select
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


def vibe_check_predictions_query(project_id: int) -> Select:
    """Returns SQL: doc_id of Documents in project whose latest Prediction is NOT covered by
    a later saved Annotation(role='none'). Implemented as: Documents with at least one
    Prediction AND no saved role=none Annotation.
    """
    has_saved_none = exists().where(
        and_(
            Annotation.document_id == Document.id,
            Annotation.role == AnnotationRole.NONE.value,
            Annotation.status == AnnotationStatus.SAVED.value,
        )
    )
    has_prediction = exists().where(Prediction.document_id == Document.id)
    return select(Document.id).where(
        Document.project_id == project_id, has_prediction, ~has_saved_none
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
    rerun: Callable[[int], Awaitable[list[dict]]],
    judge_model_version: str = "claude-opus-4-7",
) -> ProjectScoreResult:
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
            select(Annotation, Document.id)
            .join(Document, Document.id == Annotation.document_id)
            .where(
                Document.project_id == project_id,
                Annotation.role == AnnotationRole.COUNTEREXAMPLE.value,
                Annotation.status == AnnotationStatus.SAVED.value,
            )
        )
    ).all()
    ce_score: float | None
    if not ce_rows:
        ce_score = None
        ce_component_for_return = 1.0
    else:
        items = [{"document_id": d_id, "expected": ann.output} for ann, d_id in ce_rows]
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
