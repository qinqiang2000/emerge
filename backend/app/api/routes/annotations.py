from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import current_user, current_workspace_id
from app.db import get_session
from app.engine.recompute import DEFAULT_JUDGE_MODEL_VERSION, record_human_verdict_pair
from app.engine.score import JudgeVerdict
from app.errors import EmergeError, ErrorCode
from app.models.annotation import Annotation, AnnotationRole, AnnotationStatus
from app.models.document import Document
from app.models.prediction import Prediction
from app.models.project import Project
from app.models.user import User
from app.schemas.annotation import AnnotationIn, AnnotationOut, AnnotationPatchIn, FeedbackIn
from app.services.corrections import PredictionScopeError, save_correction, save_counterexample

router = APIRouter(prefix="/projects/{project_id}", tags=["annotations"])


async def _project_or_404(session, project_id, workspace_id) -> Project:
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


async def _document_in_project(session, project_id, document_id) -> Document:
    d = (
        await session.execute(
            select(Document).where(
                Document.id == document_id, Document.project_id == project_id
            )
        )
    ).scalar_one_or_none()
    if d is None:
        raise EmergeError(ErrorCode.NOT_FOUND, status_code=404)
    return d


async def _annotation_in_project(session, project_id, annotation_id) -> Annotation:
    ann = (
        await session.execute(
            select(Annotation)
            .join(Document, Document.id == Annotation.document_id)
            .where(Annotation.id == annotation_id, Document.project_id == project_id)
        )
    ).scalar_one_or_none()
    if ann is None:
        raise EmergeError(ErrorCode.NOT_FOUND, status_code=404)
    return ann


@router.post(
    "/documents/{document_id}/annotations",
    response_model=AnnotationOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_annotation(
    project_id: int,
    document_id: int,
    payload: AnnotationIn,
    user: User = Depends(current_user),
    workspace_id: int = Depends(current_workspace_id),
    session: AsyncSession = Depends(get_session),
):
    await _project_or_404(session, project_id, workspace_id)
    await _document_in_project(session, project_id, document_id)
    ann = await save_correction(
        session=session,
        document_id=document_id,
        output=payload.output,
        user_id=user.id,
        notes=payload.notes,
        parent_prediction_id=payload.parent_prediction_id,
    )
    if payload.parent_prediction_id is not None:
        parent = (
            await session.execute(
                select(Prediction).where(Prediction.id == payload.parent_prediction_id)
            )
        ).scalar_one_or_none()
        if parent is not None:
            for ent_idx_str, field_verdicts in (parent.per_field_confidence or {}).items():
                try:
                    ent_idx = int(ent_idx_str)
                except ValueError:
                    continue
                old_entity = parent.output[ent_idx] if ent_idx < len(parent.output) else {}
                new_entity = payload.output[ent_idx] if ent_idx < len(payload.output) else {}
                for fname, verdict_str in field_verdicts.items():
                    try:
                        j = JudgeVerdict(verdict_str)
                    except ValueError:
                        continue
                    human_fixed = old_entity.get(fname) != new_entity.get(fname)
                    await record_human_verdict_pair(
                        session=session,
                        project_id=project_id,
                        judge_model_version=DEFAULT_JUDGE_MODEL_VERSION,
                        judge_verdict=j,
                        human_fixed=human_fixed,
                    )
    return ann


@router.get(
    "/documents/{document_id}/annotations", response_model=list[AnnotationOut]
)
async def list_annotations(
    project_id: int,
    document_id: int,
    workspace_id: int = Depends(current_workspace_id),
    session: AsyncSession = Depends(get_session),
):
    await _project_or_404(session, project_id, workspace_id)
    await _document_in_project(session, project_id, document_id)
    rows = (
        await session.execute(
            select(Annotation)
            .where(
                Annotation.document_id == document_id,
                Annotation.status != AnnotationStatus.CANCELLED.value,
            )
            .order_by(Annotation.id.desc())
        )
    ).scalars().all()
    return [AnnotationOut.model_validate(a) for a in rows]


@router.patch("/annotations/{annotation_id}", response_model=AnnotationOut)
async def patch_annotation(
    project_id: int,
    annotation_id: int,
    payload: AnnotationPatchIn,
    user: User = Depends(current_user),
    workspace_id: int = Depends(current_workspace_id),
    session: AsyncSession = Depends(get_session),
):
    await _project_or_404(session, project_id, workspace_id)
    ann = await _annotation_in_project(session, project_id, annotation_id)
    if payload.output is not None:
        ann.output = payload.output
    if payload.notes is not None:
        ann.notes = payload.notes
    ann.last_modified_by = user.id
    await session.commit()
    await session.refresh(ann)
    return ann


@router.delete("/annotations/{annotation_id}", response_model=AnnotationOut)
async def delete_annotation(
    project_id: int,
    annotation_id: int,
    user: User = Depends(current_user),
    workspace_id: int = Depends(current_workspace_id),
    session: AsyncSession = Depends(get_session),
):
    await _project_or_404(session, project_id, workspace_id)
    ann = await _annotation_in_project(session, project_id, annotation_id)
    ann.status = AnnotationStatus.CANCELLED.value
    ann.last_modified_by = user.id
    await session.commit()
    await session.refresh(ann)
    return ann


@router.get("/counterexamples", response_model=list[AnnotationOut])
async def list_counterexamples(
    project_id: int,
    workspace_id: int = Depends(current_workspace_id),
    session: AsyncSession = Depends(get_session),
):
    await _project_or_404(session, project_id, workspace_id)
    rows = (
        await session.execute(
            select(Annotation)
            .join(Document, Document.id == Annotation.document_id)
            .where(
                Document.project_id == project_id,
                Annotation.role == AnnotationRole.COUNTEREXAMPLE.value,
                Annotation.status == AnnotationStatus.SAVED.value,
            )
            .order_by(Annotation.id.desc())
        )
    ).scalars().all()
    return [AnnotationOut.model_validate(a) for a in rows]


@router.post(
    "/counterexamples",
    response_model=AnnotationOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_counterexample(
    project_id: int,
    payload: FeedbackIn,
    user: User = Depends(current_user),
    workspace_id: int = Depends(current_workspace_id),
    session: AsyncSession = Depends(get_session),
):
    await _project_or_404(session, project_id, workspace_id)
    try:
        ann = await save_counterexample(
            session=session,
            project_id=project_id,
            prediction_id=payload.request_id,
            correct_output=payload.correct_output,
            user_id=user.id,
            notes=payload.notes,
        )
    except PredictionScopeError as e:
        raise EmergeError(
            ErrorCode.VALIDATION_FAILED, status_code=422, message_override=str(e)
        ) from e
    return ann
