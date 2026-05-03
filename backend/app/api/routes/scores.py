import random

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import current_workspace_id
from app.db import get_session
from app.engine.recompute import (
    DEFAULT_JUDGE_MODEL_VERSION,
    recompute_project_score,
    vibe_check_predictions_query,
)
from app.engine.score import (
    beta_posterior,
    precision_ci_95,
    precision_point_estimate,
)
from app.engine.judge import JudgeProvider, get_judge_provider, run_judge
from app.errors import EmergeError, ErrorCode
from app.models.document import Document
from app.models.judge_calibration import JudgeCalibration
from app.models.prediction import Prediction
from app.models.project import Project
from app.schemas.score import (
    CalibrationOut,
    JudgeRunOut,
    ProjectScoreOut,
    ReviewItemOut,
    ReviewQueueOut,
)

router = APIRouter(prefix="/projects/{project_id}", tags=["scores"])


async def _project_or_404(session, project_id, workspace_id):
    p = (
        await session.execute(
            select(Project).where(
                Project.id == project_id, Project.workspace_id == workspace_id
            )
        )
    ).scalar_one_or_none()
    if p is None:
        raise EmergeError(ErrorCode.NOT_FOUND, status_code=404)
    return p


@router.get("/score", response_model=ProjectScoreOut)
async def get_score(
    project_id: int,
    workspace_id: int = Depends(current_workspace_id),
    session: AsyncSession = Depends(get_session),
):
    await _project_or_404(session, project_id, workspace_id)
    # rerun=None until the live extraction provider is plumbed (R6/R7); the
    # orchestrator falls back to ce_component=1.0 in that case per spec §4.1.
    result = await recompute_project_score(
        project_id=project_id, session=session, rerun=None
    )
    return ProjectScoreOut(
        score=result.score,
        judge_component=result.judge_component,
        ce_component=result.ce_component,
        observation_count=result.observation_count,
        vibe_check_size=result.vibe_check_size,
    )


@router.get("/calibration", response_model=CalibrationOut)
async def get_calibration(
    project_id: int,
    workspace_id: int = Depends(current_workspace_id),
    session: AsyncSession = Depends(get_session),
):
    await _project_or_404(session, project_id, workspace_id)
    cal = (
        await session.execute(
            select(JudgeCalibration).where(
                JudgeCalibration.project_id == project_id,
                JudgeCalibration.judge_model_version == DEFAULT_JUDGE_MODEL_VERSION,
            )
        )
    ).scalar_one_or_none()
    tp, fp, fn, tn = (cal.tp, cal.fp, cal.fn, cal.tn) if cal else (0, 0, 0, 0)
    obs = cal.observation_count if cal else 0
    a, b = beta_posterior(tp=tp, fp=fp)
    point = precision_point_estimate(a, b)
    lo, hi = precision_ci_95(a, b)
    return CalibrationOut(
        tp=tp, fp=fp, fn=fn, tn=tn,
        point_estimate=point, ci_low=lo, ci_high=hi,
        observation_count=obs,
    )


@router.get("/review-queue", response_model=ReviewQueueOut)
async def get_review_queue(
    project_id: int,
    workspace_id: int = Depends(current_workspace_id),
    session: AsyncSession = Depends(get_session),
):
    await _project_or_404(session, project_id, workspace_id)
    doc_ids = (
        await session.execute(vibe_check_predictions_query(project_id))
    ).scalars().all()
    required: list[ReviewItemOut] = []
    up_only: list[ReviewItemOut] = []
    all_items: list[ReviewItemOut] = []
    for did in doc_ids:
        pred = (
            await session.execute(
                select(Prediction)
                .where(Prediction.document_id == did)
                .order_by(Prediction.id.desc())
                .limit(1)
            )
        ).scalar_one()
        doc = (
            await session.execute(select(Document).where(Document.id == did))
        ).scalar_one()
        flagged: list[str] = []
        for fields in (pred.per_field_confidence or {}).values():
            for fname, verdict in fields.items():
                if verdict in ("down", "uncertain"):
                    flagged.append(fname)
        item = ReviewItemOut(
            id=did, filename=doc.filename, flagged_fields=sorted(set(flagged))[:3]
        )
        all_items.append(item)
        if flagged:
            required.append(item)
        else:
            up_only.append(item)
    rng = random.Random(project_id)  # deterministic per project
    spot_check = rng.sample(up_only, k=min(2, len(up_only)))
    return ReviewQueueOut(required_review=required, spot_check=spot_check, all=all_items)


@router.post("/judge", response_model=JudgeRunOut)
async def trigger_judge(
    project_id: int,
    workspace_id: int = Depends(current_workspace_id),
    judge: JudgeProvider = Depends(get_judge_provider),
    session: AsyncSession = Depends(get_session),
):
    await _project_or_404(session, project_id, workspace_id)
    doc_ids = (
        await session.execute(vibe_check_predictions_query(project_id))
    ).scalars().all()
    # Serial commits per run_judge are acceptable: vibe-check is capped at 50 per spec §4.1.
    judged: list[int] = []
    failed: list[int] = []
    for did in doc_ids:
        pred = (
            await session.execute(
                select(Prediction)
                .where(Prediction.document_id == did)
                .order_by(Prediction.id.desc())
                .limit(1)
            )
        ).scalar_one()
        # run_judge swallows provider errors and writes per_field_confidence={}; treat
        # an empty result as failed so callers can distinguish from a real verdict.
        updated = await run_judge(pred.id, session=session, judge=judge)
        if updated.per_field_confidence:
            judged.append(pred.id)
        else:
            failed.append(pred.id)
    return JudgeRunOut(judged_predictions=judged, failed_predictions=failed)
