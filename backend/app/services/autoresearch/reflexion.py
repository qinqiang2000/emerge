import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from app.schemas.schema_field import SchemaField
from app.services.autoresearch.actions import apply_action
from app.services.autoresearch.researcher import ResearcherProvider, ResearcherState

log = logging.getLogger(__name__)


@dataclass
class ReflexionTurn:
    turn: int
    diagnosis: str
    actions_applied: list[dict]
    failed_actions: list[dict]
    score_before: float
    score_after: float


@dataclass
class ReflexionResult:
    schema: list[SchemaField]
    global_notes: str
    turns: list[ReflexionTurn]
    turn_count: int
    best_score: float
    termination_reason: str  # threshold_met | max_turn | no_improvement | error


Scorer = Callable[[list[SchemaField], str], float | Awaitable[float]]


async def _maybe_await(v):
    if hasattr(v, "__await__"):
        return await v
    return v


async def run_reflexion_loop(
    *,
    schema: list[SchemaField],
    global_notes: str,
    researcher: ResearcherProvider,
    scorer: Scorer,
    threshold: float,
    max_turn: int,
    no_improve_window: int = 3,
) -> ReflexionResult:
    current_schema = list(schema)
    current_notes = global_notes
    initial_score = float(await _maybe_await(scorer(current_schema, current_notes)))
    if initial_score >= threshold:
        return ReflexionResult(
            schema=current_schema,
            global_notes=current_notes,
            turns=[],
            turn_count=0,
            best_score=initial_score,
            termination_reason="threshold_met",
        )

    best_score = initial_score
    best_schema = list(current_schema)
    best_notes = current_notes
    turns: list[ReflexionTurn] = []
    no_improve_count = 0
    last_score = initial_score

    for turn_idx in range(max_turn):
        state = ResearcherState(
            schema=list(current_schema),
            global_notes=current_notes,
            judge_results={},
            counterexample_summary={},
            turn_history=[t.__dict__ for t in turns],
        )
        try:
            diag = await researcher.diagnose_and_act(state)
        except Exception:
            log.exception("researcher failed at turn %d", turn_idx)
            return ReflexionResult(
                schema=best_schema,
                global_notes=best_notes,
                turns=turns,
                turn_count=turn_idx,
                best_score=best_score,
                termination_reason="error",
            )

        applied: list[dict] = []
        failed: list[dict] = []
        next_schema = list(current_schema)
        next_notes = current_notes
        for action in diag.actions:
            try:
                next_schema, next_notes = apply_action(next_schema, next_notes, action)
                applied.append(action.model_dump())
            except Exception as e:
                failed.append({"action": action.model_dump(), "error": str(e)})

        new_score = float(await _maybe_await(scorer(next_schema, next_notes)))
        turns.append(
            ReflexionTurn(
                turn=turn_idx,
                diagnosis=diag.diagnosis,
                actions_applied=applied,
                failed_actions=failed,
                score_before=last_score,
                score_after=new_score,
            )
        )

        if new_score > best_score:
            best_score = new_score
            best_schema = list(next_schema)
            best_notes = next_notes
            no_improve_count = 0
        else:
            no_improve_count += 1

        if new_score >= last_score:
            current_schema = next_schema
            current_notes = next_notes
        last_score = new_score

        if new_score >= threshold:
            return ReflexionResult(
                schema=best_schema,
                global_notes=best_notes,
                turns=turns,
                turn_count=turn_idx + 1,
                best_score=best_score,
                termination_reason="threshold_met",
            )
        if no_improve_count >= no_improve_window:
            return ReflexionResult(
                schema=best_schema,
                global_notes=best_notes,
                turns=turns,
                turn_count=turn_idx + 1,
                best_score=best_score,
                termination_reason="no_improvement",
            )

    return ReflexionResult(
        schema=best_schema,
        global_notes=best_notes,
        turns=turns,
        turn_count=max_turn,
        best_score=best_score,
        termination_reason="max_turn",
    )
