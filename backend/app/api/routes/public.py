from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Header, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.engine.extract import extract_document
from app.engine.provider import Provider
from app.engine.providers import get_provider_dep
from app.errors import EmergeError, ErrorCode
from app.models.api_key import ApiKey
from app.models.document import Document, DocumentStatus
from app.models.project import Project
from app.services.api_key import parse_prefix, verify_api_key
from app.services.storage import save_upload

router = APIRouter(tags=["public"])


async def _resolve_project(session: AsyncSession, api_code: str) -> Project:
    """Live read per spec §7.2 — never cache, never version-pin."""
    p = (
        await session.execute(
            select(Project).where(
                Project.api_code == api_code, Project.api_published_at.is_not(None)
            )
        )
    ).scalar_one_or_none()
    if p is None:
        raise EmergeError(ErrorCode.NOT_FOUND, status_code=404)
    return p


async def _authenticate_key(
    session: AsyncSession, project_id: int, presented: str | None
) -> ApiKey:
    if not presented:
        raise EmergeError(ErrorCode.UNAUTHORIZED, status_code=401)
    prefix = parse_prefix(presented)
    if prefix is None:
        raise EmergeError(ErrorCode.UNAUTHORIZED, status_code=401)
    rows = (
        await session.execute(
            select(ApiKey).where(
                ApiKey.project_id == project_id,
                ApiKey.prefix == prefix,
                ApiKey.deleted_at.is_(None),
            )
        )
    ).scalars().all()
    for row in rows:
        if verify_api_key(presented, prefix=row.prefix, key_hash=row.key_hash):
            row.last_used_at = datetime.now(tz=timezone.utc)
            await session.commit()
            return row
    raise EmergeError(ErrorCode.UNAUTHORIZED, status_code=401)


@router.post("/extract/{api_code}")
async def public_extract(
    api_code: str,
    file: UploadFile,
    x_api_key: str | None = Header(default=None, alias="X-Api-Key"),
    provider: Provider = Depends(get_provider_dep),
    session: AsyncSession = Depends(get_session),
) -> dict:
    project = await _resolve_project(session, api_code)
    await _authenticate_key(session, project.id, x_api_key)

    rec = await save_upload(file, project_id=project.id)
    doc = Document(
        project_id=project.id,
        filename=rec.filename,
        file_path=rec.file_path,
        mime_type=rec.mime_type,
        page_count=0,
        byte_size=rec.byte_size,
        uploaded_by=0,  # external API caller — no user
        status=DocumentStatus.UPLOADED.value,
        data={"source": "public_api", "api_code": api_code},
    )
    session.add(doc)
    await session.commit()
    await session.refresh(doc)

    pred = await extract_document(doc.id, session=session, provider=provider)
    return {
        "entities": pred.output,
        "project_version": pred.project_version_id,
        "prediction_id": pred.id,
    }
