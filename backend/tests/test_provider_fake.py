import pytest

from app.engine.prompt import compose_extraction_prompt
from app.engine.providers.fake import FakeProvider
from app.schemas.schema_field import FieldType, SchemaField


@pytest.mark.asyncio
async def test_fake_provider_returns_queued_output():
    fake = FakeProvider(canned=[[{"x": "hello"}]])
    req = compose_extraction_prompt(
        fields=[SchemaField(name="x", type=FieldType.STRING, description="d")],
        global_notes="",
        model_id="any",
    )
    result = await fake.extract(req, file_bytes=b"PDF", mime_type="application/pdf")
    assert result.output == [{"x": "hello"}]
    assert result.tokens_used == 0
    assert result.latency_ms == 0


@pytest.mark.asyncio
async def test_fake_provider_can_simulate_failure():
    fake = FakeProvider(canned=[RuntimeError("boom")])
    req = compose_extraction_prompt(
        fields=[SchemaField(name="x", type=FieldType.STRING, description="d")],
        global_notes="",
        model_id="any",
    )
    with pytest.raises(RuntimeError):
        await fake.extract(req, file_bytes=b"PDF", mime_type="application/pdf")
