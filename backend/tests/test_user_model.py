import pytest

from app.models.user import User


@pytest.mark.asyncio
async def test_user_can_be_inserted_and_queried(db_session):
    user = User(email="alice@example.com", password_hash="x")
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    assert user.id is not None
    assert user.created_at is not None


@pytest.mark.asyncio
async def test_user_email_is_unique(db_session):
    db_session.add(User(email="a@a.com", password_hash="x"))
    await db_session.commit()
    db_session.add(User(email="a@a.com", password_hash="y"))
    with pytest.raises(Exception):
        await db_session.commit()
