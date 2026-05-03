from datetime import datetime, timezone

from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import _project_or_404, current_user, current_workspace_id
from app.db import get_session
from app.engine.recompute import recompute_project_score
from app.errors import EmergeError, ErrorCode
from app.models.auto_research_run import (
    AutoResearchRun,
    AutoResearchStatus,
    TerminationReason,
)
from app.models.project_version import ProjectVersion, VersionSource
from app.models.user import User
from app.schemas.auto_research import AutoResearchRunOut, RunIn
from app.schemas.schema_field import SchemaField
from app.services.autoresearch.reflexion import run_reflexion_loop
from app.services.autoresearch.researcher import FakeResearcherProvider, ResearcherProvider
from app.settings import settings

router = APIRouter(prefix="/projects/{project_id}/auto-research", tags=["auto-research"])


def get_researcher_provider_dep() -> ResearcherProvider:
    """Default returns a FakeResearcherProvider with empty queue.
    Production wiring is a deliberate config step. Tests override via dependency_overrides.
    """
    return FakeResearcherProvider(canned=[])


def get_scorer_dep():
    """Returns a scorer callable: (schema, notes) -> float.
    Default uses recompute_project_score with no live rerun (T5; live rerun is R7+ scope).
    Tests override with a simple lambda.
    """
    async def _score(_schema, _notes):
        return 0.0

    return _score


@router.post("/run", response_model=AutoResearchRunOut, status_code=status.HTTP_201_CREATED)
async def run(
    project_id: int,
    payload: RunIn,
    user: User = Depends(current_user),
    workspace_id: int = Depends(current_workspace_id),
    researcher: ResearcherProvider = Depends(get_researcher_provider_dep),
    scorer=Depends(get_scorer_dep),
    session: AsyncSession = Depends(get_session),
):
    project = await _project_or_404(session, project_id, workspace_id)

    busy = (
        await session.execute(
            select(AutoResearchRun).where(
                AutoResearchRun.project_id == project_id,
                AutoResearchRun.status == AutoResearchStatus.RUNNING.value,
            )
        )
    ).scalar_one_or_none()
    if busy is not None:
        raise EmergeError(ErrorCode.CONFLICT, status_code=409)

    if project.active_version_id is None:
        raise EmergeError(ErrorCode.CONFLICT, status_code=409)
    parent = (
        await session.execute(
            select(ProjectVersion).where(ProjectVersion.id == project.active_version_id)
        )
    ).scalar_one()

    arr = AutoResearchRun(
        project_id=project_id,
        status=AutoResearchStatus.RUNNING.value,
        starting_version_id=parent.id,
        judge_model_id=settings.default_model_pro,
        researcher_model_id=settings.default_model_pro,
        turn_count=0,
        max_turn=payload.max_turn,
        turn_history=[],
        started_at=datetime.now(tz=timezone.utc),
    )
    session.add(arr)
    await session.commit()

    schema = [SchemaField(**f) for f in parent.schema_snapshot]
    notes = parent.global_notes_snapshot

    try:
        result = await run_reflexion_loop(
            schema=schema,
            global_notes=notes,
            researcher=researcher,
            scorer=scorer,
            threshold=payload.threshold,
            max_turn=payload.max_turn,
        )
    except Exception as e:
        arr.status = AutoResearchStatus.FAILED.value
        arr.termination_reason = TerminationReason.ERROR.value
        arr.completed_at = datetime.now(tz=timezone.utc)
        await session.commit()
        raise EmergeError(
            ErrorCode.INTERNAL_ERROR, status_code=500, message_override=str(e)
        ) from e

    new_version = ProjectVersion(
        project_id=project_id,
        parent_version_id=parent.id,
        version_number=parent.version_number + 1,
        schema_snapshot=[f.model_dump() for f in result.schema],
        global_notes_snapshot=result.global_notes,
        model_id_snapshot=parent.model_id_snapshot,
        counterexample_ids=parent.counterexample_ids,
        source=VersionSource.AUTO_RESEARCH.value,
        source_metadata={"run_id": arr.id, "termination_reason": result.termination_reason},
        created_by=user.id,
    )
    session.add(new_version)
    await session.flush()

    arr.output_version_id = new_version.id
    arr.turn_count = result.turn_count
    arr.turn_history = [t.__dict__ for t in result.turns]
    arr.termination_reason = result.termination_reason

    if result.termination_reason == "threshold_met":
        arr.status = AutoResearchStatus.COMPLETED.value
    elif result.termination_reason in ("no_improvement", "max_turn"):
        arr.status = AutoResearchStatus.EARLY_STOPPED.value
    elif result.termination_reason == "error":
        arr.status = AutoResearchStatus.FAILED.value
    else:
        arr.status = AutoResearchStatus.COMPLETED.value

    arr.completed_at = datetime.now(tz=timezone.utc)
    await session.commit()
    await session.refresh(arr)
    return arr


@router.get("/runs", response_model=list[AutoResearchRunOut])
async def list_runs(
    project_id: int,
    workspace_id: int = Depends(current_workspace_id),
    session: AsyncSession = Depends(get_session),
):
    await _project_or_404(session, project_id, workspace_id)
    rows = (
        await session.execute(
            select(AutoResearchRun)
            .where(AutoResearchRun.project_id == project_id)
            .order_by(AutoResearchRun.id.desc())
        )
    ).scalars().all()
    return [AutoResearchRunOut.model_validate(r) for r in rows]


@router.get("/runs/{run_id}", response_model=AutoResearchRunOut)
async def get_run(
    project_id: int,
    run_id: int,
    workspace_id: int = Depends(current_workspace_id),
    session: AsyncSession = Depends(get_session),
):
    await _project_or_404(session, project_id, workspace_id)
    arr = (
        await session.execute(
            select(AutoResearchRun).where(
                AutoResearchRun.id == run_id, AutoResearchRun.project_id == project_id
            )
        )
    ).scalar_one_or_none()
    if arr is None:
        raise EmergeError(ErrorCode.NOT_FOUND, status_code=404)
    return arr


@router.post("/runs/{run_id}/stop", response_model=AutoResearchRunOut)
async def stop_run(
    project_id: int,
    run_id: int,
    workspace_id: int = Depends(current_workspace_id),
    session: AsyncSession = Depends(get_session),
):
    """Synchronous loop in v1 finishes inside POST /run; this endpoint exists for the
    eventual async-mode rollout. In v1 it no-ops if status != 'running'."""
    await _project_or_404(session, project_id, workspace_id)
    arr = (
        await session.execute(
            select(AutoResearchRun).where(
                AutoResearchRun.id == run_id, AutoResearchRun.project_id == project_id
            )
        )
    ).scalar_one_or_none()
    if arr is None:
        raise EmergeError(ErrorCode.NOT_FOUND, status_code=404)
    if arr.status == AutoResearchStatus.RUNNING.value:
        arr.status = AutoResearchStatus.MANUAL_STOPPED.value
        arr.termination_reason = TerminationReason.MANUAL_STOP.value
        arr.completed_at = datetime.now(tz=timezone.utc)
        await session.commit()
        await session.refresh(arr)
    return arr
