"""Semi-automatic AutoResearch trigger heuristic.

Reads the workspace-level setting ``auto_research.after_n_counterexamples`` and
counts counterexample annotations that were created since the last completed
AutoResearchRun for the project.  Returns ``True`` when the count >= threshold.

v1 NOTE: The "since last completed run" cutoff is based on comparing
``Annotation.id > last_run.id``.  Because these are IDs from two separate
sequences, this is a heuristic only — if many annotations were created before
the run row was inserted, they may be missed.  Replace with a timestamp-based
comparison (e.g. ``Annotation.created_at > last_run.completed_at``) in v2.

Red-line: this function only *counts* CE rows.  It never loads
``Annotation.output`` content into any prompt path.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.annotation import Annotation, AnnotationRole, AnnotationStatus
from app.models.auto_research_run import AutoResearchRun, AutoResearchStatus
from app.models.document import Document
from app.models.project import Project
from app.models.workspace_setting import WorkspaceSetting

KEY = "auto_research.after_n_counterexamples"


async def maybe_should_trigger(*, session: AsyncSession, project_id: int) -> bool:
    """Return True if enough new counterexamples have accumulated to warrant a new run.

    Does NOT invoke the runner — purely a boolean indicator.  Runner invocation
    is future work (R7+).
    """
    project = (
        await session.execute(select(Project).where(Project.id == project_id))
    ).scalar_one()
    setting = (
        await session.execute(
            select(WorkspaceSetting).where(
                WorkspaceSetting.workspace_id == project.workspace_id,
                WorkspaceSetting.key == KEY,
            )
        )
    ).scalar_one_or_none()
    threshold = int(setting.value) if setting else 0
    if threshold <= 0:
        return False
    last_run = (
        await session.execute(
            select(AutoResearchRun)
            .where(
                AutoResearchRun.project_id == project_id,
                AutoResearchRun.status.in_(
                    [AutoResearchStatus.COMPLETED.value, AutoResearchStatus.EARLY_STOPPED.value]
                ),
            )
            .order_by(AutoResearchRun.id.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    cutoff_id = last_run.id if last_run else 0
    new_ce = (
        await session.execute(
            select(Annotation)
            .join(Document, Document.id == Annotation.document_id)
            .where(
                Document.project_id == project_id,
                Annotation.role == AnnotationRole.COUNTEREXAMPLE.value,
                Annotation.status == AnnotationStatus.SAVED.value,
                Annotation.id > cutoff_id,
            )
        )
    ).scalars().all()
    return len(new_ce) >= threshold
