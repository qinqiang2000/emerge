from fastapi import APIRouter, Depends, status
from sqlalchemy import desc, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import _project_or_404, current_user, current_workspace_id
from app.db import get_session
from app.errors import EmergeError, ErrorCode
from app.models.project_version import ProjectVersion
from app.models.template import Template
from app.models.user import User
from app.schemas.template import TemplateOut, TemplateSaveAsIn

router = APIRouter(prefix="/templates", tags=["templates"])


@router.get("", response_model=list[TemplateOut])
async def list_templates(
    workspace_id: int = Depends(current_workspace_id),
    session: AsyncSession = Depends(get_session),
) -> list[TemplateOut]:
    rows = (
        await session.execute(
            select(Template)
            .where(or_(Template.workspace_id.is_(None), Template.workspace_id == workspace_id))
            .order_by(Template.builtin.desc(), Template.id.desc())
        )
    ).scalars().all()
    return [TemplateOut.model_validate(r) for r in rows]


@router.get("/{template_id}", response_model=TemplateOut)
async def get_template(
    template_id: int,
    workspace_id: int = Depends(current_workspace_id),
    session: AsyncSession = Depends(get_session),
) -> TemplateOut:
    row = (
        await session.execute(
            select(Template).where(
                Template.id == template_id,
                or_(Template.workspace_id.is_(None), Template.workspace_id == workspace_id),
            )
        )
    ).scalar_one_or_none()
    if row is None:
        raise EmergeError(ErrorCode.NOT_FOUND, status_code=404)
    return TemplateOut.model_validate(row)


@router.post(
    "/projects/{project_id}/save-as-template",
    response_model=TemplateOut,
    status_code=status.HTTP_201_CREATED,
)
async def save_as_template(
    project_id: int,
    payload: TemplateSaveAsIn,
    user: User = Depends(current_user),
    workspace_id: int = Depends(current_workspace_id),
    session: AsyncSession = Depends(get_session),
) -> TemplateOut:
    project = await _project_or_404(session, project_id, workspace_id)
    if project.active_version_id is None:
        raise EmergeError(ErrorCode.CONFLICT, status_code=409)
    v = (
        await session.execute(
            select(ProjectVersion).where(ProjectVersion.id == project.active_version_id)
        )
    ).scalar_one()

    existing = (
        await session.execute(
            select(Template)
            .where(
                Template.workspace_id == workspace_id,
                Template.name == payload.name,
            )
            .order_by(desc(Template.version))
            .limit(1)
        )
    ).scalar_one_or_none()
    if existing is None:
        next_version = 1
    elif payload.create_new_version:
        next_version = existing.version + 1
    else:
        raise EmergeError(
            ErrorCode.CONFLICT,
            status_code=409,
            message_override=f"Template '{payload.name}' already exists; pass create_new_version=true to add v{existing.version + 1}",
        )

    tpl = Template(
        workspace_id=workspace_id,
        name=payload.name,
        description=payload.description,
        version=next_version,
        schema_json=v.schema_snapshot,
        global_notes=v.global_notes_snapshot,
        recommended_model_id=v.model_id_snapshot,
        created_by=user.id,
        builtin=False,
    )
    session.add(tpl)
    await session.commit()
    await session.refresh(tpl)
    return TemplateOut.model_validate(tpl)
