from fastapi import APIRouter, Depends, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import current_user, current_workspace_id
from app.db import get_session
from app.errors import EmergeError, ErrorCode
from app.models.document import Document
from app.models.project import Project
from app.models.user import User
from app.schemas.document import DocumentOut
from app.services.storage import save_upload

router = APIRouter(prefix="/projects/{project_id}/documents", tags=["documents"])


async def _project_or_404(session: AsyncSession, project_id: int, workspace_id: int) -> Project:
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
