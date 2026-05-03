from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Header, Request, UploadFile
from pydantic import BaseModel
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
from app.schemas.annotation import FeedbackIn
from app.services.api_key import parse_prefix, verify_api_key
from app.services.corrections import PredictionScopeError, save_counterexample
from app.services.ratelimit import _extract_limit, limiter
from app.services.storage import save_upload

router = APIRouter(tags=["public"])


class PublicExtractOut(BaseModel):
    entities: list[dict]
    project_version: int
    prediction_id: int


class PublicFeedbackOut(BaseModel):
    counterexample_id: int


async def _resolve_project(session: AsyncSession, api_code: str) -> Project:
    """Live read per spec §7.2 — never cache, never version-pin.

    Spec §7 distinguishes 404 (unknown api_code) from 403 (known but unpublished).
    """
    p = (
        await session.execute(
            select(Project).where(Project.api_code == api_code)
        )
    ).scalar_one_or_none()
    if p is None:
        raise EmergeError(ErrorCode.NOT_FOUND, status_code=404)
    if p.api_published_at is None:
        raise EmergeError(ErrorCode.FORBIDDEN, status_code=403)
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
            await session.flush()
            return row
    raise EmergeError(ErrorCode.UNAUTHORIZED, status_code=401)


@router.post("/extract/{api_code}", response_model=PublicExtractOut)
@limiter.limit(_extract_limit)
async def public_extract(
    request: Request,
    api_code: str,
    file: UploadFile,
    x_api_key: str | None = Header(default=None, alias="X-Api-Key"),
    provider: Provider = Depends(get_provider_dep),
    session: AsyncSession = Depends(get_session),
) -> PublicExtractOut:
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

    try:
        pred = await extract_document(doc.id, session=session, provider=provider)
    except ValueError as exc:
        raise EmergeError(ErrorCode.CONFLICT, status_code=409, message_override=str(exc)) from exc
    return PublicExtractOut(
        entities=pred.output,
        project_version=pred.project_version_id,
        prediction_id=pred.id,
    )


@router.post("/extract/{api_code}/feedback", response_model=PublicFeedbackOut)
@limiter.limit(_extract_limit)
async def public_feedback(
    request: Request,
    api_code: str,
    payload: FeedbackIn,
    x_api_key: str | None = Header(default=None, alias="X-Api-Key"),
    session: AsyncSession = Depends(get_session),
) -> PublicFeedbackOut:
    project = await _resolve_project(session, api_code)
    await _authenticate_key(session, project.id, x_api_key)
    try:
        ann = await save_counterexample(
            session=session,
            project_id=project.id,
            prediction_id=payload.request_id,
            correct_output=payload.correct_output,
            user_id=0,
            notes=payload.notes,
        )
    except PredictionScopeError as exc:
        raise EmergeError(
            ErrorCode.VALIDATION_FAILED, status_code=422, message_override=str(exc)
        ) from exc
    return PublicFeedbackOut(counterexample_id=ann.id)
