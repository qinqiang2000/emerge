from fastapi import APIRouter, Depends, status
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import current_user, current_workspace_id
from app.db import get_session
from app.errors import EmergeError, ErrorCode
from app.models.project import Project
from app.models.project_version import ProjectVersion, VersionSource
from app.models.template import Template
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
    template_id = payload.template_id
    schema_json: list = []
    global_notes = ""
    # v0 model_id is env-driven so it lines up with the configured provider.
    # NOTE on thinking config: gemini-2.5 uses thinking_budget (int);
    # gemini-3+ uses thinking_level (str low/medium/high). Provider doesn't
    # pass either today; revisit when adding thinking support.
    model_id = (
        settings.default_model_gemini
        if settings.default_provider == "gemini"
        else settings.default_model_openai
    )
    if template_id is not None:
        tpl = (
            await session.execute(
                select(Template).where(
                    Template.id == template_id,
                    or_(Template.workspace_id.is_(None), Template.workspace_id == workspace_id),
                )
            )
        ).scalar_one_or_none()
        if tpl is None:
            raise EmergeError(ErrorCode.NOT_FOUND, status_code=404)
        schema_json = tpl.schema_json
        global_notes = tpl.global_notes
        model_id = tpl.recommended_model_id

    p = Project(
        workspace_id=workspace_id,
        name=payload.name,
        created_by=user.id,
        template_id=template_id,
    )
    session.add(p)
    await session.flush()

    v = ProjectVersion(
        project_id=p.id,
        version_number=0,
        schema_snapshot=schema_json,
        global_notes_snapshot=global_notes,
        model_id_snapshot=model_id,
        counterexample_ids=[],
        source=VersionSource.INITIAL.value,
        source_metadata={"reason": "project_created", "from_template_id": template_id},
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
