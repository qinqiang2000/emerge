from fastapi import APIRouter, Depends
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import current_user, current_workspace_id
from app.db import get_session
from app.errors import EmergeError, ErrorCode
from app.models.annotation import Annotation, AnnotationRole, AnnotationStatus
from app.models.document import Document
from app.models.project import Project
from app.models.project_version import ProjectVersion, VersionSource
from app.models.user import User
from app.schemas.project_version import ProjectVersionOut, SchemaPatchIn

router = APIRouter(prefix="/projects/{project_id}", tags=["versions"])


async def _get_project(session, project_id, workspace_id) -> Project:
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


async def _active_version(session, p: Project) -> ProjectVersion:
    if p.active_version_id is None:
        raise EmergeError(ErrorCode.NOT_FOUND, status_code=404)
    return (
        await session.execute(
            select(ProjectVersion).where(ProjectVersion.id == p.active_version_id)
        )
    ).scalar_one()


@router.get("/versions/active", response_model=ProjectVersionOut)
async def get_active_version(
    project_id: int,
    workspace_id: int = Depends(current_workspace_id),
    session: AsyncSession = Depends(get_session),
):
    p = await _get_project(session, project_id, workspace_id)
    return await _active_version(session, p)


@router.patch("/schema", response_model=ProjectVersionOut)
async def patch_schema(
    project_id: int,
    payload: SchemaPatchIn,
    user: User = Depends(current_user),
    workspace_id: int = Depends(current_workspace_id),
    session: AsyncSession = Depends(get_session),
):
    p = await _get_project(session, project_id, workspace_id)
    parent = await _active_version(session, p)
    if parent.locked:
        raise EmergeError(ErrorCode.CONFLICT, status_code=409)
    new_v = ProjectVersion(
        project_id=p.id,
        parent_version_id=parent.id,
        version_number=parent.version_number + 1,
        schema_snapshot=[f.model_dump() for f in payload.schema],
        global_notes_snapshot=payload.global_notes,
        model_id_snapshot=payload.model_id,
        counterexample_ids=parent.counterexample_ids,
        source=VersionSource.USER_EDIT.value,
        source_metadata={"editor": "form"},
        created_by=user.id,
    )
    session.add(new_v)
    await session.flush()
    p.active_version_id = new_v.id
    await session.commit()
    await session.refresh(new_v)
    return new_v


@router.get("/lock-status")
async def lock_status(
    project_id: int,
    workspace_id: int = Depends(current_workspace_id),
    session: AsyncSession = Depends(get_session),
):
    await _get_project(session, project_id, workspace_id)

    saved = (
        await session.execute(
            select(Annotation)
            .join(Document, Document.id == Annotation.document_id)
            .where(
                Document.project_id == project_id,
                Annotation.role == AnnotationRole.NONE.value,
                Annotation.status == AnnotationStatus.SAVED.value,
                # Dogfood follow-up #3 / CSE C2: `flagField` writes rows
                # whose `output` matches the prediction and whose `notes`
                # carries `[lab_flag]={...}`. Those are flag-without-
                # correcting markers, not real corrections — exclude them
                # from the lock threshold so a user can't game the gate by
                # ⋮-flagging two fields. Until Annotation gets a typed
                # `kind` column the notes-prefix is the available
                # discriminator. NB: SQL `NULL NOT LIKE` evaluates to NULL
                # (truthy-excluding) so notes IS NULL must be explicit.
                or_(
                    Annotation.notes.is_(None),
                    ~Annotation.notes.like("[lab_flag]=%"),
                ),
            )
        )
    ).scalars().all()
    if len(saved) < 2:
        return {"can_lock": False, "reason": "Need at least 2 saved corrections."}
    keys = [set(e.keys()) for ann in saved for e in ann.output]
    if not keys:
        return {"can_lock": False, "reason": "No entities yet in any annotation."}
    union = set().union(*keys)
    intersection = set(keys[0]).intersection(*keys[1:])
    if len(union - intersection) > 1:
        return {"can_lock": False, "reason": "Field set still differs by >1 between corrections."}
    return {"can_lock": True, "reason": None}


@router.post("/lock", response_model=ProjectVersionOut)
async def lock(
    project_id: int,
    workspace_id: int = Depends(current_workspace_id),
    session: AsyncSession = Depends(get_session),
):
    p = await _get_project(session, project_id, workspace_id)
    v = await _active_version(session, p)
    status_resp = await lock_status(project_id, workspace_id, session)
    if not status_resp["can_lock"]:
        raise EmergeError(
            ErrorCode.CONFLICT, status_code=409, message_override=status_resp["reason"]
        )
    v.locked = True
    await session.commit()
    await session.refresh(v)
    return v


@router.post("/unlock", response_model=ProjectVersionOut)
async def unlock(
    project_id: int,
    workspace_id: int = Depends(current_workspace_id),
    session: AsyncSession = Depends(get_session),
):
    p = await _get_project(session, project_id, workspace_id)
    v = await _active_version(session, p)
    v.locked = False
    await session.commit()
    await session.refresh(v)
    return v


@router.post("/versions/{version_id}/activate", response_model=ProjectVersionOut)
async def activate_version(
    project_id: int,
    version_id: int,
    workspace_id: int = Depends(current_workspace_id),
    session: AsyncSession = Depends(get_session),
):
    """Set Lab/editor active version. Does NOT change public API: spec §7.2
    routes public extract through `published_version_id`, which only the
    publish/rollback endpoints can mutate.
    """
    p = await _get_project(session, project_id, workspace_id)
    v = (
        await session.execute(
            select(ProjectVersion).where(
                ProjectVersion.id == version_id, ProjectVersion.project_id == project_id
            )
        )
    ).scalar_one_or_none()
    if v is None:
        raise EmergeError(ErrorCode.NOT_FOUND, status_code=404)
    p.active_version_id = v.id
    await session.commit()
    await session.refresh(v)
    return ProjectVersionOut.model_validate(v)


@router.get("/versions", response_model=list[ProjectVersionOut])
async def list_versions(
    project_id: int,
    workspace_id: int = Depends(current_workspace_id),
    session: AsyncSession = Depends(get_session),
):
    await _get_project(session, project_id, workspace_id)
    rows = (
        await session.execute(
            select(ProjectVersion)
            .where(ProjectVersion.project_id == project_id)
            .order_by(ProjectVersion.version_number.desc())
        )
    ).scalars().all()
    return [ProjectVersionOut.model_validate(r) for r in rows]
