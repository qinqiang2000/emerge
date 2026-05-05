from fastapi import APIRouter, Depends, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import _project_or_404, current_user, current_workspace_id
from app.db import get_session
from app.errors import EmergeError, ErrorCode
from app.models.annotation import Annotation, AnnotationStatus
from app.models.document import Document
from app.models.prediction import Prediction
from app.models.user import User
from app.schemas.document import DocumentDetailOut, DocumentOut
from app.services.storage import save_upload

router = APIRouter(prefix="/projects/{project_id}/documents", tags=["documents"])



@router.post("", response_model=list[DocumentOut], status_code=status.HTTP_201_CREATED)
async def upload_documents(
    project_id: int,
    files: list[UploadFile],
    user: User = Depends(current_user),
    workspace_id: int = Depends(current_workspace_id),
    session: AsyncSession = Depends(get_session),
) -> list[DocumentOut]:
    project = await _project_or_404(session, project_id, workspace_id)
    saved: list[Document] = []
    for f in files:
        rec = await save_upload(f, project_id=project.id)
        d = Document(
            project_id=project.id,
            filename=rec.filename,
            file_path=rec.file_path,
            mime_type=rec.mime_type,
            page_count=0,  # backfilled by R3 extraction pipeline
            byte_size=rec.byte_size,
            uploaded_by=user.id,
        )
        session.add(d)
        saved.append(d)
    await session.commit()
    for d in saved:
        await session.refresh(d)
    return [DocumentOut.model_validate(d) for d in saved]


@router.get("", response_model=list[DocumentOut])
async def list_documents(
    project_id: int,
    workspace_id: int = Depends(current_workspace_id),
    session: AsyncSession = Depends(get_session),
) -> list[DocumentOut]:
    await _project_or_404(session, project_id, workspace_id)
    rows = (
        await session.execute(
            select(Document).where(Document.project_id == project_id).order_by(Document.id.desc())
        )
    ).scalars().all()
    return [DocumentOut.model_validate(d) for d in rows]


@router.get("/{document_id}", response_model=DocumentDetailOut)
async def get_document(
    project_id: int,
    document_id: int,
    workspace_id: int = Depends(current_workspace_id),
    session: AsyncSession = Depends(get_session),
) -> DocumentDetailOut:
    await _project_or_404(session, project_id, workspace_id)
    d = (
        await session.execute(
            select(Document).where(
                Document.id == document_id, Document.project_id == project_id
            )
        )
    ).scalar_one_or_none()
    if d is None:
        raise EmergeError(ErrorCode.NOT_FOUND, status_code=404)
    payload = DocumentOut.model_validate(d).model_dump()
    latest = (
        await session.execute(
            select(Prediction)
            .where(Prediction.document_id == d.id)
            .order_by(Prediction.id.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    payload["latest_prediction"] = (
        {
            "id": latest.id,
            "output": latest.output,
            "status": latest.status,
            "model_id": latest.model_id,
            "tokens_used": latest.tokens_used,
            "error_message": latest.error_message,
            # Spec §3.2 / §8.2: surface field-level evidence + confidence so
            # Studio can render the popover and chip without a second roundtrip.
            # Evidence shape is page/quote/rationale/source_text_hash only — no
            # bbox / coordinates / polygon / region / span. Forbidden keys are
            # stripped on write at app/engine/extract.py::_sanitize_evidence;
            # this read path is an intentional pass-through.
            "per_field_confidence": latest.per_field_confidence,
            "per_field_evidence": latest.per_field_evidence,
        }
        if latest
        else None
    )
    latest_ann = (
        await session.execute(
            select(Annotation)
            .where(
                Annotation.document_id == d.id,
                Annotation.role == "none",
                Annotation.status == AnnotationStatus.SAVED.value,
            )
            .order_by(Annotation.id.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    payload["latest_annotation"] = (
        {
            "id": latest_ann.id,
            "output": latest_ann.output,
            "role": latest_ann.role,
            "notes": latest_ann.notes,
        }
        if latest_ann
        else None
    )
    return DocumentDetailOut(**payload)
