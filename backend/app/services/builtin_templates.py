from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.template import Template
from app.models.user import User
from app.settings import settings

BUILTINS: list[dict] = [
    {
        "name": "china_vat",
        "description": "Chinese VAT invoices (普通增值税发票 / 专用增值税发票)",
        "global_notes": "All amounts in CNY (RMB). Dates in YYYY-MM-DD.",
        "schema_json": [
            {"name": "invoice_code", "type": "string", "required": True, "description": "发票代码 — 12 digits"},
            {"name": "invoice_number", "type": "string", "required": True, "description": "发票号码 — 8 digits"},
            {"name": "issue_date", "type": "string", "required": True, "description": "开票日期 in YYYY-MM-DD"},
            {"name": "buyer_name", "type": "string", "required": True, "description": "购买方名称"},
            {"name": "seller_name", "type": "string", "required": True, "description": "销售方名称"},
            {"name": "total_amount", "type": "number", "required": True, "description": "价税合计 in CNY"},
            {"name": "tax_amount", "type": "number", "required": False, "description": "税额 in CNY"},
        ],
    },
    {
        "name": "us_invoice",
        "description": "Generic US invoices",
        "global_notes": "All amounts in USD unless explicit currency stated. Dates in MM/DD/YYYY.",
        "schema_json": [
            {"name": "invoice_number", "type": "string", "required": True, "description": "Invoice number / id"},
            {"name": "issue_date", "type": "string", "required": True, "description": "Issue date in YYYY-MM-DD"},
            {"name": "vendor_name", "type": "string", "required": True, "description": "Vendor / supplier name"},
            {"name": "bill_to_name", "type": "string", "required": True, "description": "Bill-to party"},
            {"name": "total_amount", "type": "number", "required": True, "description": "Grand total in USD"},
            {"name": "currency", "type": "string", "required": True, "description": "ISO 4217 code", "enum": ["USD", "CAD", "EUR", "GBP"]},
        ],
    },
    {
        "name": "japan_receipt",
        "description": "Japanese receipts (領収書)",
        "global_notes": "All amounts in JPY (no decimals). Dates may appear as 令和 era — convert to Gregorian.",
        "schema_json": [
            {"name": "shop_name", "type": "string", "required": True, "description": "店名 — look near the logo / 店舗 marker"},
            {"name": "issue_date", "type": "string", "required": True, "description": "発行日 in YYYY-MM-DD (Gregorian)"},
            {"name": "total_amount", "type": "integer", "required": True, "description": "合計金額 (税込) in JPY"},
            {
                "name": "line_items",
                "type": "array",
                "required": False,
                "description": "Each purchased item",
                "child_fields": [
                    {"name": "name", "type": "string", "required": True, "description": "商品名"},
                    {"name": "qty", "type": "integer", "required": False, "description": "数量"},
                    {"name": "unit_price", "type": "integer", "required": False, "description": "単価 in JPY"},
                ],
            },
        ],
    },
    {
        "name": "de_rechnung",
        "description": "German invoices (Rechnung)",
        "global_notes": "Amounts in EUR. Decimal comma in source; emit decimal point.",
        "schema_json": [
            {"name": "rechnungsnummer", "type": "string", "required": True, "description": "Rechnungsnummer"},
            {"name": "rechnungsdatum", "type": "string", "required": True, "description": "Rechnungsdatum YYYY-MM-DD"},
            {"name": "lieferant", "type": "string", "required": True, "description": "Lieferant / Anbieter"},
            {"name": "kunde", "type": "string", "required": True, "description": "Kunde / Empfänger"},
            {"name": "gesamtbetrag", "type": "number", "required": True, "description": "Gesamtbetrag in EUR"},
            {"name": "ust_anteil", "type": "number", "required": False, "description": "USt.-Anteil"},
        ],
    },
    {
        "name": "custom_blank",
        "description": "Empty starting point — define your own schema.",
        "global_notes": "",
        "schema_json": [],
    },
]


async def seed_builtin_templates(session: AsyncSession) -> None:
    """Idempotent: inserts any missing builtin Templates.

    The created_by FK requires a user; if the DB has no users yet (very first
    container start), seeding uses 0 as a placeholder — SQLite accepts this
    without strict FK enforcement, which is the default for aiosqlite.
    """
    user = (
        await session.execute(select(User).order_by(User.id).limit(1))
    ).scalar_one_or_none()
    creator_id = user.id if user else 0
    recommended_model = settings.default_model_gemini
    for spec in BUILTINS:
        existing = (
            await session.execute(
                select(Template).where(
                    Template.workspace_id.is_(None), Template.name == spec["name"]
                )
            )
        ).scalar_one_or_none()
        if existing is not None:
            continue
        session.add(
            Template(
                workspace_id=None,
                name=spec["name"],
                description=spec["description"],
                version=1,
                schema_json=spec["schema_json"],
                global_notes=spec["global_notes"],
                recommended_model_id=recommended_model,
                created_by=creator_id,
                builtin=True,
            )
        )
    await session.commit()
