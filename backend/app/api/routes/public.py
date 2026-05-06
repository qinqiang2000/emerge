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
from app.models.document import Document, DocumentSource, DocumentStatus
from app.models.project import Project
from app.schemas.annotation import FeedbackIn
from app.services.api_key import parse_prefix, verify_api_key
from app.services.corrections import (
    FeedbackPatchError,
    PredictionScopeError,
    apply_feedback_corrections,
    save_counterexample,
)
from app.services.ratelimit import _extract_limit, limiter
from app.services.storage import save_upload

router = APIRouter(tags=["public"])


class PublicExtractOutput(BaseModel):
    """Inner envelope for the public extract response.

    Wrapping `entities` here leaves room for `output.confidence` /
    `output.field_evidence` etc. without another shape churn (dogfood #2).
    """

    entities: list[dict]


class PublicExtractOut(BaseModel):
    request_id: int
    prediction_id: int
    project_version_id: int
    output: PublicExtractOutput


class PublicFeedbackOut(BaseModel):
    counterexample_id: int


async def _resolve_project(session: AsyncSession, api_code: str) -> Project:
    """Resolve project by api_code and serve its `published_version_id`.

    Spec §7.2: public API only serves the explicitly published version, never
    `active_version_id`. Editing/AutoResearch must not change production by
    accident. 404 distinguishes unknown api_code; 403 distinguishes paused or
    missing-published-pointer projects.
    """
    p = (
        await session.execute(
            select(Project).where(Project.api_code == api_code)
        )
    ).scalar_one_or_none()
    if p is None:
        raise EmergeError(ErrorCode.NOT_FOUND, status_code=404)
    if p.api_published_at is None or p.published_version_id is None:
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
        # Spec §7.1 / dogfood follow-up #1: public-API traffic must not show
        # up in the editor's Documents list, vibe-check pool, or Readiness
        # annotated_* counts. The typed `source` column is authoritative;
        # `data["source"]` stays for back-compat audit only.
        source=DocumentSource.PUBLIC_API.value,
        data={"source": "public_api", "api_code": api_code},
    )
    session.add(doc)
    await session.commit()
    await session.refresh(doc)

    try:
        pred = await extract_document(
            doc.id,
            session=session,
            provider=provider,
            project_version_id=project.published_version_id,
        )
    except ValueError as exc:
        raise EmergeError(ErrorCode.CONFLICT, status_code=409, message_override=str(exc)) from exc
    return PublicExtractOut(
        request_id=pred.id,
        prediction_id=pred.id,
        project_version_id=pred.project_version_id,
        output=PublicExtractOutput(entities=pred.output),
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
    """Receive production feedback from API consumers (spec §7.1).

    Accepts either a full `correct_output` array, or partial `corrections`
    keyed by `entity_index`/`field_path`. Partial corrections are merged
    onto the original prediction output to form the counterexample's
    `correct_output`, so callers can patch a single field without knowing
    the entire schema.
    """
    project = await _resolve_project(session, api_code)
    await _authenticate_key(session, project.id, x_api_key)

    correct_output = payload.correct_output
    raw_corrections: list[dict] | None = None
    if correct_output is None:
        # Partial path: load the referenced prediction and apply corrections.
        from app.models.prediction import Prediction as _Pred  # local import to avoid circular

        from sqlalchemy import select as _select

        pred = (
            await session.execute(_select(_Pred).where(_Pred.id == payload.request_id))
        ).scalar_one_or_none()
        if pred is None:
            raise EmergeError(
                ErrorCode.VALIDATION_FAILED,
                status_code=422,
                message_override=f"prediction {payload.request_id} not found",
            )
        raw_corrections = [c.model_dump() for c in (payload.corrections or [])]
        try:
            correct_output = apply_feedback_corrections(
                pred.output or [], raw_corrections
            )
        except FeedbackPatchError as exc:
            raise EmergeError(
                ErrorCode.VALIDATION_FAILED, status_code=422, message_override=str(exc)
            ) from exc

    notes = payload.notes
    if raw_corrections is not None:
        # Preserve partial-feedback metadata in the Annotation notes for AutoResearch
        # readability; the structured corrections payload would need a dedicated column
        # which v1 does not model — string is the most stable carrier today.
        import json as _json

        suffix = f"\n[partial_feedback]={_json.dumps({'corrections': raw_corrections, 'issue_type': payload.issue_type})}"
        notes = (notes or "") + suffix

    try:
        ann = await save_counterexample(
            session=session,
            project_id=project.id,
            prediction_id=payload.request_id,
            correct_output=correct_output,
            user_id=0,
            notes=notes,
        )
    except PredictionScopeError as exc:
        raise EmergeError(
            ErrorCode.VALIDATION_FAILED, status_code=422, message_override=str(exc)
        ) from exc
    return PublicFeedbackOut(counterexample_id=ann.id)
