from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.db import get_session
from app.errors import EmergeError, ErrorCode
from app.models.user import User
from app.models.workspace import Workspace, WorkspaceMembership, WorkspaceRole
from app.schemas.auth import RegisterIn
from app.schemas.user import UserOut

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def register(payload: RegisterIn, session: AsyncSession = Depends(get_session)) -> UserOut:
    existing = (
        await session.execute(select(User).where(User.email == payload.email))
    ).scalar_one_or_none()
    if existing:
        raise EmergeError(ErrorCode.CONFLICT, status_code=409)

    user = User(email=payload.email, password_hash=hash_password(payload.password))
    session.add(user)
    await session.flush()

    ws = Workspace(name=f"{payload.email}'s workspace", owner_id=user.id)
    session.add(ws)
    await session.flush()

    session.add(
        WorkspaceMembership(workspace_id=ws.id, user_id=user.id, role=WorkspaceRole.OWNER.value)
    )
    await session.commit()
    await session.refresh(user)
    return UserOut.model_validate(user)
