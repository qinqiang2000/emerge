import pytest

from app.services.autoresearch.actions import EditFieldDescriptionAction
from app.services.autoresearch.researcher import (
    DiagnosisResult,
    FakeResearcherProvider,
    ResearcherState,
)
from app.schemas.schema_field import FieldType, SchemaField


@pytest.mark.asyncio
async def test_fake_returns_queued_response():
    fake = FakeResearcherProvider(
        canned=[
            DiagnosisResult(
                diagnosis="shop_name often wrong on receipts with logo header",
                actions=[
                    EditFieldDescriptionAction(
                        field_name="shop_name", new_text="店名 — look near logo header"
                    )
                ],
            )
        ]
    )
    state = ResearcherState(
        schema=[SchemaField(name="shop_name", type=FieldType.STRING, description="店名")],
        global_notes="",
        judge_results={"down_count": 5},
        counterexample_summary={"misses": 2},
        turn_history=[],
    )
    result = await fake.diagnose_and_act(state)
    assert "logo" in result.diagnosis
    assert isinstance(result.actions[0], EditFieldDescriptionAction)
