import pytest

from app.models.template import Template
from app.models.user import User
from app.models.workspace import Workspace


@pytest.mark.asyncio
async def test_template_persists(db_session):
    user = User(email="tp@tp.com", password_hash="x")
    db_session.add(user)
    await db_session.flush()
    ws = Workspace(name="W", owner_id=user.id)
    db_session.add(ws)
    await db_session.flush()

    t = Template(
        workspace_id=ws.id,
        name="japan_receipts",
        description="japan receipts",
        version=1,
        schema_json=[{"name": "shop_name", "type": "string", "description": "店名"}],
        global_notes="all in JPY",
        recommended_model_id="claude-opus-4-7",
        created_by=user.id,
        builtin=False,
    )
    db_session.add(t)
    await db_session.commit()
    assert t.id is not None


@pytest.mark.asyncio
async def test_builtin_template_has_null_workspace(db_session):
    """Builtins are visible to every workspace; workspace_id is NULL."""
    user = User(email="bi@bi.com", password_hash="x")
    db_session.add(user)
    await db_session.flush()
    t = Template(
        workspace_id=None,
        name="china_vat",
        description="builtin",
        version=1,
        schema_json=[],
        global_notes="",
        recommended_model_id="m",
        created_by=user.id,
        builtin=True,
    )
    db_session.add(t)
    await db_session.commit()
    assert t.workspace_id is None
