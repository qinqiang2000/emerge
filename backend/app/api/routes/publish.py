from datetime import datetime, timezone

from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import _project_or_404, current_user, current_workspace_id
from app.db import get_session
from app.errors import EmergeError, ErrorCode
from app.models.api_key import ApiKey
from app.models.project import Project
from app.models.project_version import ProjectVersion
from app.models.user import User
from app.schemas.api_key import ApiKeyIn, ApiKeyOnceOut, ApiKeyOut, PublishIn, RollbackIn
from app.schemas.project import ProjectOut
from app.services.api_key import generate_api_key

router = APIRouter(prefix="/projects/{project_id}", tags=["publish"])


@router.post("/publish", response_model=ProjectOut)
async def publish(
    project_id: int,
    payload: PublishIn,
    workspace_id: int = Depends(current_workspace_id),
    session: AsyncSession = Depends(get_session),
) -> ProjectOut:
    """Publish target ProjectVersion to the public API.

    Spec §7.2: editing/AutoResearch never auto-promote. Public API serves
    `project.published_version_id`, which this route is the only writer for.
    Defaults to `project.active_version_id` if no explicit target is given.
    """
    p = await _project_or_404(session, project_id, workspace_id)
    target_id = payload.project_version_id or p.active_version_id
    if target_id is None:
        raise EmergeError(
            ErrorCode.CONFLICT,
            status_code=409,
            message_override="Project has no active version.",
        )
    v = (
        await session.execute(select(ProjectVersion).where(ProjectVersion.id == target_id))
    ).scalar_one_or_none()
    if v is None or v.project_id != p.id:
        raise EmergeError(
            ErrorCode.NOT_FOUND,
            status_code=404,
            message_override="Target version not found in this project.",
        )
    if not v.locked:
        raise EmergeError(
            ErrorCode.CONFLICT,
            status_code=409,
            message_override="Target version must be locked before publishing.",
        )
    clash = (
        await session.execute(
            select(Project).where(
                Project.workspace_id == workspace_id,
                Project.api_code == payload.api_code,
                Project.id != p.id,
            )
        )
    ).scalar_one_or_none()
    if clash is not None:
        raise EmergeError(
            ErrorCode.CONFLICT,
            status_code=409,
            message_override=f"api_code '{payload.api_code}' already in use in this workspace.",
        )

    p.api_code = payload.api_code
    p.published_version_id = v.id
    p.api_published_at = datetime.now(tz=timezone.utc)
    await session.commit()
    await session.refresh(p)
    return ProjectOut.model_validate(p)


@router.post("/rollback", response_model=ProjectOut)
async def rollback(
    project_id: int,
    payload: RollbackIn,
    workspace_id: int = Depends(current_workspace_id),
    session: AsyncSession = Depends(get_session),
) -> ProjectOut:
    """Roll back the public API to a previous locked ProjectVersion.

    Only mutates `published_version_id`; Lab `active_version_id` is untouched.
    """
    p = await _project_or_404(session, project_id, workspace_id)
    if p.api_published_at is None:
        raise EmergeError(
            ErrorCode.CONFLICT,
            status_code=409,
            message_override="Project must be published before rollback.",
        )
    v = (
        await session.execute(
            select(ProjectVersion).where(ProjectVersion.id == payload.project_version_id)
        )
    ).scalar_one_or_none()
    if v is None or v.project_id != p.id:
        raise EmergeError(
            ErrorCode.NOT_FOUND,
            status_code=404,
            message_override="Target version not found in this project.",
        )
    if not v.locked:
        raise EmergeError(
            ErrorCode.CONFLICT,
            status_code=409,
            message_override="Rollback target must be locked.",
        )
    p.published_version_id = v.id
    await session.commit()
    await session.refresh(p)
    return ProjectOut.model_validate(p)


@router.post("/unpublish", response_model=ProjectOut)
async def unpublish(
    project_id: int,
    workspace_id: int = Depends(current_workspace_id),
    session: AsyncSession = Depends(get_session),
) -> ProjectOut:
    """Pause the public API for this project. The api_code stays bound so the
    same code can be re-published later; spec §7.2 returns 403 to callers in
    the meantime (vs 404 for unknown codes).
    """
    p = await _project_or_404(session, project_id, workspace_id)
    p.api_published_at = None
    await session.commit()
    await session.refresh(p)
    return ProjectOut.model_validate(p)


@router.post(
    "/api-keys", response_model=ApiKeyOnceOut, status_code=status.HTTP_201_CREATED
)
async def create_api_key(
    project_id: int,
    payload: ApiKeyIn,
    user: User = Depends(current_user),
    workspace_id: int = Depends(current_workspace_id),
    session: AsyncSession = Depends(get_session),
) -> ApiKeyOnceOut:
    await _project_or_404(session, project_id, workspace_id)
    full, prefix, hashed = generate_api_key()
    row = ApiKey(
        project_id=project_id,
        name=payload.name,
        prefix=prefix,
        key_hash=hashed,
        created_by=user.id,
    )
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return ApiKeyOnceOut(id=row.id, prefix=prefix, name=row.name, key=full)


@router.get("/api-keys", response_model=list[ApiKeyOut])
async def list_api_keys(
    project_id: int,
    workspace_id: int = Depends(current_workspace_id),
    session: AsyncSession = Depends(get_session),
) -> list[ApiKeyOut]:
    await _project_or_404(session, project_id, workspace_id)
    rows = (
        await session.execute(
            select(ApiKey)
            .where(ApiKey.project_id == project_id, ApiKey.deleted_at.is_(None))
            .order_by(ApiKey.id.desc())
        )
    ).scalars().all()
    return [ApiKeyOut.model_validate(r) for r in rows]


@router.delete("/api-keys/{key_id}", response_model=ApiKeyOut)
async def revoke_api_key(
    project_id: int,
    key_id: int,
    workspace_id: int = Depends(current_workspace_id),
    session: AsyncSession = Depends(get_session),
) -> ApiKeyOut:
    await _project_or_404(session, project_id, workspace_id)
    row = (
        await session.execute(
            select(ApiKey).where(
                ApiKey.id == key_id,
                ApiKey.project_id == project_id,
                ApiKey.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if row is None:
        raise EmergeError(ErrorCode.NOT_FOUND, status_code=404)
    row.deleted_at = datetime.now(tz=timezone.utc)
    await session.commit()
    await session.refresh(row)
    return ApiKeyOut.model_validate(row)
