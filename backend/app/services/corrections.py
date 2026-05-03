from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.annotation import Annotation, AnnotationRole, AnnotationStatus
from app.models.document import Document
from app.models.prediction import Prediction


class PredictionScopeError(Exception):
    """Prediction does not belong to the supplied project or document."""


async def save_correction(
    *,
    session: AsyncSession,
    document_id: int,
    output: list[dict],
    user_id: int,
    notes: str | None = None,
    parent_prediction_id: int | None = None,
) -> Annotation:
    if parent_prediction_id is not None:
        # Symmetry with save_counterexample: never let an Annotation reference
        # a prediction belonging to a different document. Even though the
        # current API path scopes by document_id, callers reaching this
        # service layer directly (R5/R6) must not bypass the guard.
        pred = (
            await session.execute(
                select(Prediction).where(Prediction.id == parent_prediction_id)
            )
        ).scalar_one_or_none()
        if pred is None or pred.document_id != document_id:
            raise PredictionScopeError(
                f"prediction {parent_prediction_id} does not belong to document {document_id}"
            )
    ann = Annotation(
        document_id=document_id,
        parent_prediction_id=parent_prediction_id,
        output=output,
        role=AnnotationRole.NONE.value,
        status=AnnotationStatus.SAVED.value,
        notes=notes,
        created_by=user_id,
        last_modified_by=user_id,
    )
    session.add(ann)
    await session.commit()
    await session.refresh(ann)
    return ann


async def save_counterexample(
    *,
    session: AsyncSession,
    project_id: int,
    prediction_id: int,
    correct_output: list[dict],
    user_id: int,
    notes: str | None = None,
) -> Annotation:
    pred = (
        await session.execute(
            select(Prediction).where(Prediction.id == prediction_id)
        )
    ).scalar_one_or_none()
    if pred is None:
        raise PredictionScopeError(f"prediction {prediction_id} not found")
    doc = (
        await session.execute(select(Document).where(Document.id == pred.document_id))
    ).scalar_one()
    if doc.project_id != project_id:
        raise PredictionScopeError(
            f"prediction {prediction_id} does not belong to project {project_id}"
        )
    ann = Annotation(
        document_id=doc.id,
        parent_prediction_id=pred.id,
        output=correct_output,
        role=AnnotationRole.COUNTEREXAMPLE.value,
        status=AnnotationStatus.SAVED.value,
        notes=notes,
        created_by=user_id,
        last_modified_by=user_id,
    )
    session.add(ann)
    await session.commit()
    await session.refresh(ann)
    return ann
