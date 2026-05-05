from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query, status
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
from app.schemas.contract_diff import ContractDiffOut
from app.schemas.project import ProjectOut
from app.services.api_key import generate_api_key
from app.services.contract_diff import diff_schema_snapshots

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
    # Spec §4.5: empty_schema is a hard publish blocker — promoting a contract
    # with no fields would publish a useless API and leak Lab placeholders.
    if not v.schema_snapshot:
        raise EmergeError(
            ErrorCode.CONFLICT,
            status_code=409,
            message_override="Target version has empty schema; nothing to publish.",
        )
    # api_code is global because /extract/{api_code} has no workspace context
    # (spec §7.1, R7.5 hardening). Two workspaces sharing the same code would
    # make the public route ambiguous, so reject collisions across the system.
    clash = (
        await session.execute(
            select(Project).where(
                Project.api_code == payload.api_code,
                Project.id != p.id,
            )
        )
    ).scalar_one_or_none()
    if clash is not None:
        raise EmergeError(
            ErrorCode.CONFLICT,
            status_code=409,
            message_override=f"api_code '{payload.api_code}' already in use.",
        )

    # Pure api_code rename (same published_version_id, project already
    # published) keeps api_published_at unchanged — the UI shows it as
    # "Activated", and re-stamping on rename misleads the user into
    # thinking Lab was promoted. Only stamp when the version actually
    # changes, or when (re-)publishing after an unpublish that cleared
    # the timestamp.
    is_revision = p.published_version_id != v.id
    is_first_or_resume = p.api_published_at is None
    p.api_code = payload.api_code
    p.published_version_id = v.id
    if is_revision or is_first_or_resume:
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


@router.get("/contract-diff", response_model=ContractDiffOut)
async def contract_diff(
    project_id: int,
    from_version_id: int | None = Query(default=None),
    to_version_id: int | None = Query(default=None),
    workspace_id: int = Depends(current_workspace_id),
    session: AsyncSession = Depends(get_session),
) -> ContractDiffOut:
    """Diff two ProjectVersion schema_snapshots (spec §7.3).

    Defaults: from = `published_version_id` (empty schema if never published),
    to = `active_version_id`. Both versions must belong to the project.
    """
    p = await _project_or_404(session, project_id, workspace_id)
    if from_version_id is None:
        from_version_id = p.published_version_id
    if to_version_id is None:
        to_version_id = p.active_version_id

    async def _load(vid: int | None) -> tuple[int | None, list[dict]]:
        if vid is None:
            return None, []
        v = (
            await session.execute(
                select(ProjectVersion).where(ProjectVersion.id == vid)
            )
        ).scalar_one_or_none()
        if v is None or v.project_id != p.id:
            raise EmergeError(
                ErrorCode.NOT_FOUND,
                status_code=404,
                message_override="Version not found in this project.",
            )
        return v.id, list(v.schema_snapshot or [])

    from_id, from_snapshot = await _load(from_version_id)
    to_id, to_snapshot = await _load(to_version_id)

    out = diff_schema_snapshots(from_snapshot, to_snapshot)
    out.from_version_id = from_id
    out.to_version_id = to_id
    return out


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
