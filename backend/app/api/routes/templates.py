from fastapi import APIRouter, Depends
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import current_workspace_id
from app.db import get_session
from app.errors import EmergeError, ErrorCode
from app.models.template import Template
from app.schemas.template import TemplateOut

router = APIRouter(prefix="/templates", tags=["templates"])


@router.get("", response_model=list[TemplateOut])
async def list_templates(
    workspace_id: int = Depends(current_workspace_id),
    session: AsyncSession = Depends(get_session),
):
    rows = (
        await session.execute(
            select(Template)
            .where(or_(Template.workspace_id.is_(None), Template.workspace_id == workspace_id))
            .order_by(Template.builtin.desc(), Template.id.desc())
        )
    ).scalars().all()
    return [TemplateOut.from_orm_row(r) for r in rows]


@router.get("/{template_id}", response_model=TemplateOut)
async def get_template(
    template_id: int,
    workspace_id: int = Depends(current_workspace_id),
    session: AsyncSession = Depends(get_session),
):
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
    return TemplateOut.from_orm_row(row)
