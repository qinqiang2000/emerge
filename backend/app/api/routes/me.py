from fastapi import APIRouter, Depends
from pydantic import BaseModel, EmailStr

from app.core.deps import current_user, current_workspace_id
from app.models.user import User

router = APIRouter(tags=["me"])


class MeOut(BaseModel):
    id: int
    email: EmailStr
    workspace_id: int


@router.get("/me", response_model=MeOut)
async def me(
    user: User = Depends(current_user),
    workspace_id: int = Depends(current_workspace_id),
) -> MeOut:
    return MeOut(id=user.id, email=user.email, workspace_id=workspace_id)
