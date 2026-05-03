import pytest
from sqlalchemy import select

from app.models.template import Template


@pytest.mark.asyncio
async def test_five_builtins_present(db_session):
    rows = (
        await db_session.execute(select(Template).where(Template.builtin.is_(True)))
    ).scalars().all()
    names = {r.name for r in rows}
    assert names >= {"china_vat", "us_invoice", "japan_receipt", "de_rechnung", "custom_blank"}


@pytest.mark.asyncio
async def test_custom_blank_has_empty_schema(db_session):
    row = (
        await db_session.execute(select(Template).where(Template.name == "custom_blank"))
    ).scalar_one()
    assert row.schema_json == []
    assert row.global_notes == ""


@pytest.mark.asyncio
async def test_japan_receipt_has_shop_name_field(db_session):
    row = (
        await db_session.execute(select(Template).where(Template.name == "japan_receipt"))
    ).scalar_one()
    names = {f["name"] for f in row.schema_json}
    assert "shop_name" in names


@pytest.mark.asyncio
async def test_seed_is_idempotent(db_session):
    """Re-running the seed must not produce duplicates."""
    from app.services.builtin_templates import seed_builtin_templates

    before = (
        await db_session.execute(select(Template).where(Template.builtin.is_(True)))
    ).scalars().all()
    await seed_builtin_templates(db_session)
    after = (
        await db_session.execute(select(Template).where(Template.builtin.is_(True)))
    ).scalars().all()
    assert len(after) == len(before)
