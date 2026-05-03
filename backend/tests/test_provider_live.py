import os

import pytest

from app.engine.prompt import compose_extraction_prompt
from app.engine.providers import get_provider
from app.schemas.schema_field import FieldType, SchemaField

LIVE = os.environ.get("EMERGE_RUN_LIVE_PROVIDER_TESTS") == "1"


@pytest.mark.skipif(not LIVE, reason="live provider tests opt-in")
@pytest.mark.asyncio
async def test_openai_basic_extract():
    with open("tests/fixtures/sample_receipt.png", "rb") as fh:
        body = fh.read()
    p = get_provider("openai")
    req = compose_extraction_prompt(
        fields=[
            SchemaField(name="shop_name", type=FieldType.STRING, description="店名"),
            SchemaField(name="total_amount", type=FieldType.NUMBER, description="金額"),
        ],
        global_notes="",
        model_id="gpt-4o-2024-08-06",
    )
    result = await p.extract(req, file_bytes=body, mime_type="image/png")
    assert isinstance(result.output, list)
    assert len(result.output) >= 1
