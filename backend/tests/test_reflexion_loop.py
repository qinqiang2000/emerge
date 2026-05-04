import pytest

from app.services.autoresearch.actions import EditFieldDescriptionAction
from app.services.autoresearch.reflexion import (
    ReflexionResult,
    ReflexionTurn,
    run_reflexion_loop,
)
from app.services.autoresearch.researcher import DiagnosisResult, FakeResearcherProvider
from app.schemas.schema_field import FieldType, SchemaField


def _baseline_schema():
    return [SchemaField(name="x", type=FieldType.STRING, description="raw description")]


@pytest.mark.asyncio
async def test_threshold_met_terminates_immediately():
    """Score is already above threshold → 0 turns."""
    researcher = FakeResearcherProvider(canned=[])
    scorer = lambda schema, notes: 0.95  # noqa: E731

    result = await run_reflexion_loop(
        schema=_baseline_schema(),
        global_notes="",
        researcher=researcher,
        scorer=scorer,
        threshold=0.9,
        max_turn=10,
    )
    assert result.termination_reason == "threshold_met"
    assert result.turn_count == 0


@pytest.mark.asyncio
async def test_max_turn_terminates_after_n_turns():
    diag = DiagnosisResult(
        diagnosis="d",
        actions=[EditFieldDescriptionAction(field_name="x", new_text="d")],
    )
    researcher = FakeResearcherProvider(canned=[diag] * 5)
    score_seq = iter([0.5, 0.5, 0.5, 0.5, 0.5, 0.5])
    scorer = lambda *_: next(score_seq)  # noqa: E731

    result = await run_reflexion_loop(
        schema=_baseline_schema(),
        global_notes="",
        researcher=researcher,
        scorer=scorer,
        threshold=0.9,
        max_turn=5,
        no_improve_window=10,
    )
    assert result.turn_count == 5
    assert result.termination_reason == "max_turn"


@pytest.mark.asyncio
async def test_three_turns_no_improvement_early_stops():
    diag = DiagnosisResult(
        diagnosis="d",
        actions=[EditFieldDescriptionAction(field_name="x", new_text="d")],
    )
    researcher = FakeResearcherProvider(canned=[diag] * 10)
    # initial 0.5; turns 1/2/3/4 no improvement
    score_seq = iter([0.5, 0.5, 0.5, 0.5, 0.5])
    scorer = lambda *_: next(score_seq)  # noqa: E731

    result = await run_reflexion_loop(
        schema=_baseline_schema(),
        global_notes="",
        researcher=researcher,
        scorer=scorer,
        threshold=0.9,
        max_turn=10,
    )
    assert result.termination_reason == "no_improvement"
    assert result.turn_count == 3


@pytest.mark.asyncio
async def test_returns_best_state_seen_when_early_stopped():
    """If turn 1 was best, result.schema reflects that."""
    diags = [
        DiagnosisResult(
            diagnosis="d",
            actions=[EditFieldDescriptionAction(field_name="x", new_text=f"text_{i}")],
        )
        for i in range(10)
    ]
    researcher = FakeResearcherProvider(canned=diags)
    score_seq = iter([0.5, 0.85, 0.5, 0.5, 0.5])
    scorer = lambda *_: next(score_seq)  # noqa: E731

    result = await run_reflexion_loop(
        schema=_baseline_schema(),
        global_notes="",
        researcher=researcher,
        scorer=scorer,
        threshold=0.9,
        max_turn=10,
    )
    # best score 0.85 was at turn 1 with text_0
    assert next(f for f in result.schema if f.name == "x").description == "text_0"
    assert result.best_score == 0.85
    assert result.termination_reason == "no_improvement"


@pytest.mark.asyncio
async def test_action_failure_logs_and_continues():
    bad_action = EditFieldDescriptionAction(field_name="UNKNOWN", new_text="x")
    good_action = EditFieldDescriptionAction(field_name="x", new_text="y")
    researcher = FakeResearcherProvider(
        canned=[
            DiagnosisResult(diagnosis="d1", actions=[bad_action]),
            DiagnosisResult(diagnosis="d2", actions=[good_action]),
        ]
    )
    score_seq = iter([0.5, 0.6, 0.95])
    scorer = lambda *_: next(score_seq)  # noqa: E731

    result = await run_reflexion_loop(
        schema=_baseline_schema(),
        global_notes="",
        researcher=researcher,
        scorer=scorer,
        threshold=0.9,
        max_turn=5,
    )
    # turn 0 had failed action; turn 1 succeeded; threshold met after turn 1
    assert result.termination_reason == "threshold_met"
    assert any(t.failed_actions for t in result.turns)
