from fastapi import Depends, Header
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decode_access_token
from app.db import get_session
from app.errors import EmergeError, ErrorCode
from app.models.user import User
from app.models.workspace import WorkspaceMembership


async def current_user(
    authorization: str | None = Header(default=None),
    session: AsyncSession = Depends(get_session),
) -> User:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise EmergeError(ErrorCode.UNAUTHORIZED, status_code=401)
    token = authorization.split(" ", 1)[1].strip()
    payload = decode_access_token(token)
    try:
        user_id = int(payload["sub"])
    except (KeyError, ValueError) as e:
        # Signature verified but `sub` is missing or non-numeric — treat as
        # auth failure (401) rather than letting the cast bubble up to a 500.
        raise EmergeError(ErrorCode.UNAUTHORIZED, status_code=401) from e
    user = (
        await session.execute(select(User).where(User.id == user_id))
    ).scalar_one_or_none()
    if user is None:
        raise EmergeError(ErrorCode.UNAUTHORIZED, status_code=401)
    return user


async def current_workspace_id(
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> int:
    """Resolve the user's single workspace. v1 assumes one membership per user."""
    rows = (
        await session.execute(
            select(WorkspaceMembership.workspace_id).where(WorkspaceMembership.user_id == user.id)
        )
    ).scalars().all()
    if not rows:
        raise EmergeError(ErrorCode.FORBIDDEN, status_code=403)
    return rows[0]
