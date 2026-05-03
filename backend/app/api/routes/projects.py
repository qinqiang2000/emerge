from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import current_user, current_workspace_id
from app.db import get_session
from app.errors import EmergeError, ErrorCode
from app.models.project import Project
from app.models.project_version import ProjectVersion, VersionSource
from app.models.user import User
from app.schemas.project import ProjectIn, ProjectOut
from app.settings import settings

router = APIRouter(prefix="/projects", tags=["projects"])


@router.post("", response_model=ProjectOut, status_code=status.HTTP_201_CREATED)
async def create_project(
    payload: ProjectIn,
    user: User = Depends(current_user),
    workspace_id: int = Depends(current_workspace_id),
    session: AsyncSession = Depends(get_session),
) -> ProjectOut:
    p = Project(workspace_id=workspace_id, name=payload.name, created_by=user.id)
    session.add(p)
    await session.flush()

    # v0 model_id is env-driven so it lines up with the configured provider.
    # NOTE on thinking config: gemini-2.5 uses thinking_budget (int);
    # gemini-3+ uses thinking_level (str low/medium/high). Provider doesn't
    # pass either today; revisit when adding thinking support.
    v0_model = (
        settings.default_model_gemini
        if settings.default_provider == "gemini"
        else settings.default_model_openai
    )
    v = ProjectVersion(
        project_id=p.id,
        version_number=0,
        schema_snapshot=[],
        global_notes_snapshot="",
        model_id_snapshot=v0_model,
        counterexample_ids=[],
        source=VersionSource.INITIAL.value,
        source_metadata={"reason": "project_created"},
        created_by=user.id,
    )
    session.add(v)
    await session.flush()
    p.active_version_id = v.id
    await session.commit()
    await session.refresh(p)
    return ProjectOut.model_validate(p)


@router.get("", response_model=list[ProjectOut])
async def list_projects(
    workspace_id: int = Depends(current_workspace_id),
    session: AsyncSession = Depends(get_session),
) -> list[ProjectOut]:
    rows = (
        await session.execute(
            select(Project).where(Project.workspace_id == workspace_id).order_by(Project.id.desc())
        )
    ).scalars().all()
    return [ProjectOut.model_validate(p) for p in rows]


@router.get("/{project_id}", response_model=ProjectOut)
async def get_project(
    project_id: int,
    workspace_id: int = Depends(current_workspace_id),
    session: AsyncSession = Depends(get_session),
) -> ProjectOut:
    p = (
        await session.execute(
            select(Project).where(
                Project.id == project_id, Project.workspace_id == workspace_id
            )
        )
    ).scalar_one_or_none()
    if p is None:
        raise EmergeError(ErrorCode.NOT_FOUND, status_code=404)
    return ProjectOut.model_validate(p)
