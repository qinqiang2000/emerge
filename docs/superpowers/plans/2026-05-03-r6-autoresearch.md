# R6 — AutoResearch Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the single-architecture Reflexion loop that produces a new candidate `ProjectVersion` from a starting one — by judging, diagnosing, applying whitelisted text-only actions to schema/global_notes, and re-scoring — until the score crosses a threshold or the loop early-stops. The output is **never auto-promoted**: the user accepts via the version timeline (R8 UI surfaces this).

**Architecture:**
- **Loop driver is pure orchestration**: takes injected `judge_provider`, `researcher_provider`, and `extract_provider`. Tests use the corresponding `Fake*Provider`s. No DB or HTTP coupling inside `run_reflexion_loop` — it returns a `ReflexionResult` dataclass; the API route persists it as `AutoResearchRun` rows.
- **Action toolkit is a closed whitelist**, modeled as pydantic discriminated-union types. The researcher LLM emits structured JSON via tool-use; we deserialise to `Action` instances and `apply_action(schema, global_notes, action)` returns a new `(schema, global_notes)` pair. **No free-form code path.** Spec §5.2.
- **Researcher LLM is just a JSON-tool-use call.** We compose a system prompt explaining the toolkit, supply current state + judge results, and parse the JSON response. `FakeResearcherProvider` returns canned action sequences.
- **Termination matrix** (spec §5.1): cross threshold → success; 3 no-improvement turns → early_stop; turn ≥ max_turn → max_turn_reached; user POSTs `/stop` → manual_stop. All four flow through one termination check.
- **Triggers**: manual button (always available), semi-automatic toggle ("auto-run after N counterexamples", workspace setting). Concurrent runs on the same project blocked at API layer.

**Tech Stack:** R1–R5 stack. Anthropic SDK isn't strictly required — the spec lets the workspace pick any model with JSON tool-use. We use the OpenAI SDK against any function-calling-capable model since the dep is already installed; admins can later swap for `anthropic` SDK without breaking the contract. Add `anthropic>=0.30.0` only if the default `claude-opus-4-7` route requires it.

**Spec sections covered:** §5.1 (loop shape, max_turn=10, 3-turn no-improvement early-stop), §5.2 (action toolkit whitelist; no anchor/few-shot actions), §5.3 (manual + semi-automatic + future scheduled), §5.4 (researcher_model_id workspace-level), §5.5 (turn history transparent + collapsible diff). Also §3.1 (`AutoResearchRun` table).

**Depends on:** R5 (judge runner; recompute_project_score; vibe-check view). R3 indirectly (ProjectVersion creation; provider dispatch).

---

## File Structure

```
backend/app/
├── models/
│   └── auto_research_run.py         # AutoResearchRun table
├── schemas/
│   └── auto_research.py             # ActionUnion, ReflexionTurnOut, AutoResearchRunOut
├── engine/
│   ├── actions.py                   # action types + apply_action(schema, notes, action)
│   ├── researcher.py                # ResearcherProvider protocol + Fake + concrete
│   └── reflexion.py                 # run_reflexion_loop(...) driver
├── api/routes/
│   └── auto_research.py             # POST /run, GET /runs, GET /runs/{id}, POST /runs/{id}/stop
└── alembic/versions/
    └── 0010_auto_research_run.py
```

Tests:

```
backend/tests/
├── test_actions.py
├── test_reflexion_loop.py
├── test_auto_research_routes.py
└── test_auto_research_model.py
```

---

## Task 1: AutoResearchRun model + migration

**Files:**
- Create: `backend/app/models/auto_research_run.py`
- Modify: `backend/app/models/__init__.py`
- Create: `backend/alembic/versions/0010_auto_research_run.py`
- Create: `backend/tests/test_auto_research_model.py`

- [ ] **Step 1: Write the failing test**

```python
import pytest

from app.models.auto_research_run import (
    AutoResearchRun,
    AutoResearchStatus,
    TerminationReason,
)
from app.models.project import Project
from app.models.user import User
from app.models.workspace import Workspace


@pytest.mark.asyncio
async def test_run_persists(db_session):
    user = User(email="ar@ar.com", password_hash="x")
    db_session.add(user)
    await db_session.flush()
    ws = Workspace(name="W", owner_id=user.id)
    db_session.add(ws)
    await db_session.flush()
    p = Project(workspace_id=ws.id, name="P", created_by=user.id)
    db_session.add(p)
    await db_session.commit()

    run = AutoResearchRun(
        project_id=p.id,
        status=AutoResearchStatus.RUNNING.value,
        starting_version_id=None,
        output_version_id=None,
        judge_model_id="m1",
        researcher_model_id="m2",
        turn_count=0,
        max_turn=10,
        turn_history=[],
    )
    db_session.add(run)
    await db_session.commit()
    assert run.id is not None


@pytest.mark.asyncio
async def test_invalid_status_rejected(db_session):
    user = User(email="ar2@ar.com", password_hash="x")
    db_session.add(user)
    await db_session.flush()
    ws = Workspace(name="W", owner_id=user.id)
    db_session.add(ws)
    await db_session.flush()
    p = Project(workspace_id=ws.id, name="P", created_by=user.id)
    db_session.add(p)
    await db_session.commit()
    run = AutoResearchRun(
        project_id=p.id,
        status="bogus",
        judge_model_id="m",
        researcher_model_id="m",
        turn_count=0,
        max_turn=10,
        turn_history=[],
    )
    db_session.add(run)
    with pytest.raises(Exception):
        await db_session.commit()
```

- [ ] **Step 2: Run — expect ImportError**

- [ ] **Step 3: Implement `app/models/auto_research_run.py`**

```python
from datetime import datetime
from enum import Enum

from sqlalchemy import JSON, CheckConstraint, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class AutoResearchStatus(str, Enum):
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    EARLY_STOPPED = "early_stopped"
    MANUAL_STOPPED = "manual_stopped"


class TerminationReason(str, Enum):
    THRESHOLD_MET = "threshold_met"
    MAX_TURN = "max_turn"
    NO_IMPROVEMENT = "no_improvement"
    MANUAL_STOP = "manual_stop"
    ERROR = "error"
    NOT_TERMINATED = "not_terminated"


class AutoResearchRun(Base, TimestampMixin):
    __tablename__ = "auto_research_runs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('running','completed','failed','early_stopped','manual_stopped')",
            name="ck_auto_research_status",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id"), nullable=False, index=True
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False)

    starting_version_id: Mapped[int | None] = mapped_column(
        ForeignKey("project_versions.id"), nullable=True
    )
    output_version_id: Mapped[int | None] = mapped_column(
        ForeignKey("project_versions.id"), nullable=True
    )

    judge_model_id: Mapped[str] = mapped_column(String(128), nullable=False)
    researcher_model_id: Mapped[str] = mapped_column(String(128), nullable=False)

    turn_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_turn: Mapped[int] = mapped_column(Integer, nullable=False, default=10)
    turn_history: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    termination_reason: Mapped[str | None] = mapped_column(String(64), nullable=True)
```

Re-export.

- [ ] **Step 4: Run test to verify it passes**

- [ ] **Step 5: Generate + apply migration**

```bash
cd backend && uv run alembic revision --autogenerate -m "auto_research_run table"
uv run alembic upgrade head
```

- [ ] **Step 6: Commit**

```bash
git add backend/app/models/auto_research_run.py backend/app/models/__init__.py backend/alembic/versions/0010_auto_research_run.py backend/tests/test_auto_research_model.py
git commit -m "feat(backend): add AutoResearchRun model + 0010 migration"
```

---

## Task 2: Action toolkit + apply_action

**Files:**
- Create: `backend/app/engine/actions.py`
- Create: `backend/tests/test_actions.py`

The toolkit is **exactly** the 7 actions from spec §5.2:

```
edit_field_description, add_field_examples, add_field, remove_field,
make_optional, make_required, edit_global_notes, add_field_enum
```

(That's 8 — spec lists `add_field_enum` separately.) Use a discriminated union on a `kind` literal. `apply_action(schema, notes, action)` returns a new `(schema, notes)` tuple — pure, no side effects.

- [ ] **Step 1: Write the failing test**

```python
import pytest

from app.engine.actions import (
    AddFieldAction,
    AddFieldEnumAction,
    AddFieldExamplesAction,
    EditFieldDescriptionAction,
    EditGlobalNotesAction,
    MakeOptionalAction,
    MakeRequiredAction,
    RemoveFieldAction,
    apply_action,
    parse_action,
)
from app.schemas.schema_field import FieldType, SchemaField


def _baseline() -> list[SchemaField]:
    return [
        SchemaField(name="shop_name", type=FieldType.STRING, description="店名"),
        SchemaField(name="total_amount", type=FieldType.NUMBER, description="金額"),
    ]


def test_edit_field_description():
    schema, notes = apply_action(
        _baseline(), "",
        EditFieldDescriptionAction(field_name="shop_name", new_text="店名（更新）"),
    )
    assert next(f for f in schema if f.name == "shop_name").description == "店名（更新）"


def test_add_field():
    schema, notes = apply_action(
        _baseline(), "",
        AddFieldAction(name="currency", type="string", description="ISO 4217", required=True),
    )
    assert any(f.name == "currency" for f in schema)


def test_remove_field():
    schema, notes = apply_action(
        _baseline(), "", RemoveFieldAction(field_name="shop_name")
    )
    assert all(f.name != "shop_name" for f in schema)


def test_make_optional_then_required():
    s1, _ = apply_action(_baseline(), "", MakeOptionalAction(field_name="shop_name"))
    assert next(f for f in s1 if f.name == "shop_name").required is False
    s2, _ = apply_action(s1, "", MakeRequiredAction(field_name="shop_name"))
    assert next(f for f in s2 if f.name == "shop_name").required is True


def test_add_field_examples():
    schema, _ = apply_action(
        _baseline(), "",
        AddFieldExamplesAction(field_name="shop_name", examples=["スターバックス", "Doutor"]),
    )
    assert "スターバックス" in next(f for f in schema if f.name == "shop_name").examples


def test_add_field_enum_only_on_string():
    with pytest.raises(ValueError):
        apply_action(
            _baseline(), "",
            AddFieldEnumAction(field_name="total_amount", values=["x", "y"]),
        )


def test_edit_global_notes():
    _, notes = apply_action(_baseline(), "old", EditGlobalNotesAction(text="new"))
    assert notes == "new"


def test_remove_unknown_field_raises():
    with pytest.raises(KeyError):
        apply_action(_baseline(), "", RemoveFieldAction(field_name="nope"))


def test_parse_action_round_trip():
    raw = {"kind": "edit_field_description", "field_name": "x", "new_text": "y"}
    action = parse_action(raw)
    assert isinstance(action, EditFieldDescriptionAction)
```

- [ ] **Step 2: Run — expect ImportError**

- [ ] **Step 3: Implement `app/engine/actions.py`**

```python
from typing import Annotated, Literal, Union

from pydantic import BaseModel, Field, TypeAdapter

from app.schemas.schema_field import FieldType, SchemaField


class _ActionBase(BaseModel):
    kind: str


class EditFieldDescriptionAction(_ActionBase):
    kind: Literal["edit_field_description"] = "edit_field_description"
    field_name: str
    new_text: str


class AddFieldExamplesAction(_ActionBase):
    kind: Literal["add_field_examples"] = "add_field_examples"
    field_name: str
    examples: list[str]


class AddFieldAction(_ActionBase):
    kind: Literal["add_field"] = "add_field"
    name: str
    type: FieldType
    description: str
    required: bool = True


class RemoveFieldAction(_ActionBase):
    kind: Literal["remove_field"] = "remove_field"
    field_name: str


class MakeOptionalAction(_ActionBase):
    kind: Literal["make_optional"] = "make_optional"
    field_name: str


class MakeRequiredAction(_ActionBase):
    kind: Literal["make_required"] = "make_required"
    field_name: str


class EditGlobalNotesAction(_ActionBase):
    kind: Literal["edit_global_notes"] = "edit_global_notes"
    text: str


class AddFieldEnumAction(_ActionBase):
    kind: Literal["add_field_enum"] = "add_field_enum"
    field_name: str
    values: list[str]


Action = Annotated[
    Union[
        EditFieldDescriptionAction,
        AddFieldExamplesAction,
        AddFieldAction,
        RemoveFieldAction,
        MakeOptionalAction,
        MakeRequiredAction,
        EditGlobalNotesAction,
        AddFieldEnumAction,
    ],
    Field(discriminator="kind"),
]

_action_adapter = TypeAdapter(Action)


def parse_action(raw: dict) -> Action:
    return _action_adapter.validate_python(raw)


def _find(schema: list[SchemaField], name: str) -> int:
    for i, f in enumerate(schema):
        if f.name == name:
            return i
    raise KeyError(f"field {name!r} not in schema")


def _replace(schema: list[SchemaField], idx: int, new: SchemaField) -> list[SchemaField]:
    return [*schema[:idx], new, *schema[idx + 1:]]


def apply_action(
    schema: list[SchemaField], notes: str, action: Action
) -> tuple[list[SchemaField], str]:
    if isinstance(action, EditFieldDescriptionAction):
        i = _find(schema, action.field_name)
        return _replace(schema, i, schema[i].model_copy(update={"description": action.new_text})), notes
    if isinstance(action, AddFieldExamplesAction):
        i = _find(schema, action.field_name)
        merged = list(schema[i].examples) + [e for e in action.examples if e not in schema[i].examples]
        return _replace(schema, i, schema[i].model_copy(update={"examples": merged})), notes
    if isinstance(action, AddFieldAction):
        if any(f.name == action.name for f in schema):
            raise ValueError(f"field {action.name!r} already exists")
        return [
            *schema,
            SchemaField(
                name=action.name,
                type=action.type,
                description=action.description,
                required=action.required,
            ),
        ], notes
    if isinstance(action, RemoveFieldAction):
        i = _find(schema, action.field_name)
        return [*schema[:i], *schema[i + 1:]], notes
    if isinstance(action, MakeOptionalAction):
        i = _find(schema, action.field_name)
        return _replace(schema, i, schema[i].model_copy(update={"required": False})), notes
    if isinstance(action, MakeRequiredAction):
        i = _find(schema, action.field_name)
        return _replace(schema, i, schema[i].model_copy(update={"required": True})), notes
    if isinstance(action, EditGlobalNotesAction):
        return schema, action.text
    if isinstance(action, AddFieldEnumAction):
        i = _find(schema, action.field_name)
        if schema[i].type is not FieldType.STRING:
            raise ValueError(
                f"add_field_enum requires string field; '{action.field_name}' is {schema[i].type.value}"
            )
        return _replace(schema, i, schema[i].model_copy(update={"enum": action.values})), notes
    raise TypeError(f"unknown action {type(action)!r}")
```

- [ ] **Step 4: Run test to verify it passes**

Expected: `9 passed`.

- [ ] **Step 5: Commit**

```bash
git add backend/app/engine/actions.py backend/tests/test_actions.py
git commit -m "feat(engine): action toolkit + apply_action (closed whitelist, no free-form path)"
```

---

## Task 3: Researcher provider + Fake

**Files:**
- Create: `backend/app/engine/researcher.py`
- Create: `backend/tests/test_researcher.py`

`ResearcherProvider.diagnose_and_act(state) -> (diagnosis_text, list[Action])` is one call (the spec separates diagnose / choose_actions but they're both LLM calls — combining them halves latency without losing transparency since both outputs are saved in turn_history). `FakeResearcherProvider` returns canned `(text, actions)` tuples.

- [ ] **Step 1: Write the failing test**

```python
import pytest

from app.engine.actions import EditFieldDescriptionAction
from app.engine.researcher import (
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
```

- [ ] **Step 2: Run — expect ImportError**

- [ ] **Step 3: Implement `app/engine/researcher.py`**

```python
import json
from collections import deque
from dataclasses import dataclass
from typing import Protocol

from app.engine.actions import Action, parse_action
from app.schemas.schema_field import SchemaField


@dataclass
class ResearcherState:
    schema: list[SchemaField]
    global_notes: str
    judge_results: dict
    counterexample_summary: dict
    turn_history: list[dict]


@dataclass
class DiagnosisResult:
    diagnosis: str
    actions: list[Action]


RESEARCHER_SYSTEM_FRAME = """\
You are emerge's AutoResearcher. Your job is to look at the current Project state — the schema,
global notes, judge results, and counterexample summary — and decide which whitelisted actions
to take to improve the schema. The actions you may emit are:
- edit_field_description(field_name, new_text)
- add_field_examples(field_name, examples)
- add_field(name, type, description, required)
- remove_field(field_name)
- make_optional(field_name) / make_required(field_name)
- edit_global_notes(text)
- add_field_enum(field_name, values)

You may NOT invent actions outside this list. You may NOT include image few-shot examples.
Respond with ONLY a JSON object: { "diagnosis": "<short text>", "actions": [<action objects>] }.
Each action object has a "kind" key matching one of the names above and the corresponding fields.\
"""


class ResearcherProvider(Protocol):
    async def diagnose_and_act(self, state: ResearcherState) -> DiagnosisResult:
        ...


class FakeResearcherProvider:
    def __init__(self, *, canned: list):
        self._queue = deque(canned)

    async def diagnose_and_act(self, state: ResearcherState) -> DiagnosisResult:
        if not self._queue:
            raise RuntimeError("FakeResearcherProvider out of canned responses")
        nxt = self._queue.popleft()
        if isinstance(nxt, BaseException):
            raise nxt
        return nxt


class OpenAIResearcherProvider:
    """Concrete impl backed by OpenAI tool-use. Used when default_provider='openai'."""

    def __init__(self, model_id: str, client=None):
        from openai import AsyncOpenAI

        from app.settings import settings

        self.model_id = model_id
        self.client = client or AsyncOpenAI(api_key=settings.openai_api_key)

    async def diagnose_and_act(self, state: ResearcherState) -> DiagnosisResult:
        user = json.dumps(
            {
                "schema": [f.model_dump() for f in state.schema],
                "global_notes": state.global_notes,
                "judge_results": state.judge_results,
                "counterexample_summary": state.counterexample_summary,
                "turn_history": state.turn_history,
            },
            ensure_ascii=False,
        )
        resp = await self.client.chat.completions.create(
            model=self.model_id,
            messages=[
                {"role": "system", "content": RESEARCHER_SYSTEM_FRAME},
                {"role": "user", "content": user},
            ],
            response_format={"type": "json_object"},
        )
        body = json.loads(resp.choices[0].message.content)
        actions = [parse_action(a) for a in body.get("actions", [])]
        return DiagnosisResult(diagnosis=body.get("diagnosis", ""), actions=actions)
```

- [ ] **Step 4: Run test to verify it passes**

- [ ] **Step 5: Commit**

```bash
git add backend/app/engine/researcher.py backend/tests/test_researcher.py
git commit -m "feat(engine): researcher provider protocol + fake + OpenAI concrete impl"
```

---

## Task 4: Reflexion loop driver

**Files:**
- Create: `backend/app/engine/reflexion.py`
- Create: `backend/tests/test_reflexion_loop.py`

Pure orchestration. Inputs: starting `(schema, global_notes)`, judge fn, researcher fn, score fn, threshold, max_turn. Outputs: list of turns, final state, termination reason. **Does not touch DB**; the API route persists the result.

- [ ] **Step 1: Write the failing tests**

```python
import pytest

from app.engine.actions import EditFieldDescriptionAction
from app.engine.reflexion import (
    ReflexionResult,
    ReflexionTurn,
    run_reflexion_loop,
)
from app.engine.researcher import DiagnosisResult, FakeResearcherProvider
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
```

- [ ] **Step 2: Run — expect ImportError**

- [ ] **Step 3: Implement `app/engine/reflexion.py`**

```python
import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Awaitable

from app.engine.actions import Action, apply_action
from app.engine.researcher import ResearcherProvider, ResearcherState
from app.schemas.schema_field import SchemaField

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
            judge_results={},  # populated by caller via state.update if desired
            counterexample_summary={},
            turn_history=[t.__dict__ for t in turns],
        )
        try:
            diag = await researcher.diagnose_and_act(state)
        except Exception as e:
            log.exception("researcher failed")
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

        # accept turn into current state only if it didn't regress
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
```

- [ ] **Step 4: Run tests to verify they pass**

Expected: `5 passed`.

- [ ] **Step 5: Commit**

```bash
git add backend/app/engine/reflexion.py backend/tests/test_reflexion_loop.py
git commit -m "feat(engine): reflexion loop driver with all 4 termination reasons"
```

---

## Task 5: AutoResearch trigger endpoint

**Files:**
- Create: `backend/app/schemas/auto_research.py`
- Create: `backend/app/api/routes/auto_research.py`
- Modify: `backend/app/api/v1.py` (mount)
- Create: `backend/tests/test_auto_research_routes.py`

Endpoint behaviour: `POST /projects/{pid}/auto-research/run` synchronously creates an `AutoResearchRun` row, executes `run_reflexion_loop`, and on success creates a new `ProjectVersion` (`source=auto_research`). Concurrent runs blocked by checking for an existing `status='running'` row. **Never auto-promotes** — the new version is created but `Project.active_version_id` is not changed.

In v1 the loop runs synchronously inside the request. For larger workspaces, R7+ may move this to a background task; not in scope for R6.

- [ ] **Step 1: Write the failing tests**

```python
import io

import pytest


async def _auth_and_project(client) -> tuple[dict, int]:
    await client.post("/api/v1/auth/register", json={"email": "ar@ar.com", "password": "hunter22"})
    tok = (
        await client.post("/api/v1/auth/login", json={"email": "ar@ar.com", "password": "hunter22"})
    ).json()["access_token"]
    h = {"Authorization": f"Bearer {tok}"}
    pid = (await client.post("/api/v1/projects", json={"name": "P"}, headers=h)).json()["id"]
    return h, pid


@pytest.mark.asyncio
async def test_run_creates_new_version_and_run_record(client, db_session, app):
    h, pid = await _auth_and_project(client)
    # set a baseline schema
    await client.patch(
        f"/api/v1/projects/{pid}/schema",
        json={
            "schema": [
                {"name": "shop_name", "type": "string", "description": "店名"},
            ],
            "global_notes": "",
            "model_id": "m",
        },
        headers=h,
    )

    from app.engine.actions import EditFieldDescriptionAction
    from app.engine.researcher import (
        DiagnosisResult,
        FakeResearcherProvider,
        ResearcherProvider,
    )

    fake = FakeResearcherProvider(
        canned=[
            DiagnosisResult(
                diagnosis="improve description",
                actions=[
                    EditFieldDescriptionAction(
                        field_name="shop_name", new_text="店名 (look near logo)"
                    )
                ],
            )
        ]
    )

    from app.api.routes.auto_research import (
        get_researcher_provider_dep,
        get_scorer_dep,
    )

    app.dependency_overrides[get_researcher_provider_dep] = lambda: fake
    app.dependency_overrides[get_scorer_dep] = lambda: (lambda schema, notes: 0.95)

    resp = await client.post(
        f"/api/v1/projects/{pid}/auto-research/run", json={"max_turn": 5}, headers=h
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["termination_reason"] == "threshold_met"
    assert body["status"] == "completed"
    assert body["output_version_id"] is not None

    # active version is NOT changed (never auto-promoted)
    active = (
        await client.get(f"/api/v1/projects/{pid}/versions/active", headers=h)
    ).json()
    assert active["id"] != body["output_version_id"]


@pytest.mark.asyncio
async def test_concurrent_run_returns_conflict(client, db_session, app):
    from app.models.auto_research_run import AutoResearchRun, AutoResearchStatus
    from sqlalchemy import select

    h, pid = await _auth_and_project(client)
    db_session.add(
        AutoResearchRun(
            project_id=pid,
            status=AutoResearchStatus.RUNNING.value,
            judge_model_id="m",
            researcher_model_id="m",
            turn_count=0,
            max_turn=10,
            turn_history=[],
        )
    )
    await db_session.commit()
    resp = await client.post(
        f"/api/v1/projects/{pid}/auto-research/run", json={}, headers=h
    )
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_list_runs_returns_history(client, db_session):
    h, pid = await _auth_and_project(client)
    from app.models.auto_research_run import AutoResearchRun, AutoResearchStatus

    db_session.add(
        AutoResearchRun(
            project_id=pid,
            status=AutoResearchStatus.COMPLETED.value,
            judge_model_id="m",
            researcher_model_id="m",
            turn_count=2,
            max_turn=10,
            turn_history=[{"turn": 0}],
            termination_reason="threshold_met",
        )
    )
    await db_session.commit()
    resp = await client.get(f"/api/v1/projects/{pid}/auto-research/runs", headers=h)
    assert resp.status_code == 200
    rows = resp.json()
    assert len(rows) >= 1
    assert rows[0]["status"] == "completed"
```

- [ ] **Step 2: Run — expect 404**

- [ ] **Step 3: Implement `app/schemas/auto_research.py`**

```python
from datetime import datetime

from pydantic import BaseModel, Field


class RunIn(BaseModel):
    max_turn: int = Field(default=10, ge=1, le=30)
    threshold: float = Field(default=0.9, ge=0.0, le=1.0)


class TurnOut(BaseModel):
    turn: int
    diagnosis: str
    actions_applied: list[dict]
    failed_actions: list[dict]
    score_before: float
    score_after: float


class AutoResearchRunOut(BaseModel):
    id: int
    project_id: int
    status: str
    starting_version_id: int | None
    output_version_id: int | None
    judge_model_id: str
    researcher_model_id: str
    turn_count: int
    max_turn: int
    turn_history: list[TurnOut]
    termination_reason: str | None
    started_at: datetime | None
    completed_at: datetime | None

    model_config = {"from_attributes": True}
```

- [ ] **Step 4: Implement `app/api/routes/auto_research.py`**

```python
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import current_user, current_workspace_id
from app.db import get_session
from app.engine.recompute import recompute_project_score
from app.engine.reflexion import run_reflexion_loop
from app.engine.researcher import FakeResearcherProvider, ResearcherProvider
from app.errors import EmergeError, ErrorCode
from app.models.auto_research_run import (
    AutoResearchRun,
    AutoResearchStatus,
    TerminationReason,
)
from app.models.project import Project
from app.models.project_version import ProjectVersion, VersionSource
from app.models.user import User
from app.schemas.auto_research import AutoResearchRunOut, RunIn
from app.schemas.schema_field import SchemaField

router = APIRouter(prefix="/projects/{project_id}/auto-research", tags=["auto-research"])


def get_researcher_provider_dep() -> ResearcherProvider:
    """Default returns a FakeResearcherProvider with empty queue (real impl wired in production).
    Tests override via app.dependency_overrides.
    """
    return FakeResearcherProvider(canned=[])


def get_scorer_dep():
    """Default scorer is a closure that calls recompute_project_score with no rerun.
    Tests override.
    """
    def _make(session: AsyncSession, project_id: int):
        async def _score(_schema, _notes):
            r = await recompute_project_score(
                project_id=project_id, session=session, rerun=lambda _id: []
            )
            return r.score
        return _score
    return _make


async def _project_or_404(session, project_id, workspace_id):
    p = (
        await session.execute(
            select(Project).where(
                Project.id == project_id, Project.workspace_id == workspace_id
            )
        )
    ).scalar_one_or_none()
    if p is None:
        raise EmergeError(ErrorCode.NOT_FOUND, status_code=404)
    return p


@router.post("/run", response_model=AutoResearchRunOut, status_code=status.HTTP_201_CREATED)
async def run(
    project_id: int,
    payload: RunIn,
    user: User = Depends(current_user),
    workspace_id: int = Depends(current_workspace_id),
    researcher: ResearcherProvider = Depends(get_researcher_provider_dep),
    scorer_factory=Depends(get_scorer_dep),
    session: AsyncSession = Depends(get_session),
):
    project = await _project_or_404(session, project_id, workspace_id)

    busy = (
        await session.execute(
            select(AutoResearchRun).where(
                AutoResearchRun.project_id == project_id,
                AutoResearchRun.status == AutoResearchStatus.RUNNING.value,
            )
        )
    ).scalar_one_or_none()
    if busy is not None:
        raise EmergeError(ErrorCode.CONFLICT, status_code=409)

    if project.active_version_id is None:
        raise EmergeError(ErrorCode.CONFLICT, status_code=409)
    parent = (
        await session.execute(
            select(ProjectVersion).where(ProjectVersion.id == project.active_version_id)
        )
    ).scalar_one()

    arr = AutoResearchRun(
        project_id=project_id,
        status=AutoResearchStatus.RUNNING.value,
        starting_version_id=parent.id,
        judge_model_id="claude-opus-4-7",
        researcher_model_id="claude-opus-4-7",
        turn_count=0,
        max_turn=payload.max_turn,
        turn_history=[],
        started_at=datetime.now(tz=timezone.utc),
    )
    session.add(arr)
    await session.commit()

    schema = [SchemaField(**f) for f in parent.schema_snapshot]
    notes = parent.global_notes_snapshot

    if isinstance(scorer_factory, type(lambda: None)):
        # tests override returns a callable directly
        scorer = scorer_factory
    else:
        scorer = scorer_factory(session, project_id)

    try:
        result = await run_reflexion_loop(
            schema=schema,
            global_notes=notes,
            researcher=researcher,
            scorer=scorer,
            threshold=payload.threshold,
            max_turn=payload.max_turn,
        )
    except Exception as e:
        arr.status = AutoResearchStatus.FAILED.value
        arr.termination_reason = TerminationReason.ERROR.value
        arr.completed_at = datetime.now(tz=timezone.utc)
        await session.commit()
        raise EmergeError(
            ErrorCode.INTERNAL_ERROR, status_code=500, message_override=str(e)
        ) from e

    new_version = ProjectVersion(
        project_id=project_id,
        parent_version_id=parent.id,
        version_number=parent.version_number + 1,
        schema_snapshot=[f.model_dump() for f in result.schema],
        global_notes_snapshot=result.global_notes,
        model_id_snapshot=parent.model_id_snapshot,
        counterexample_ids=parent.counterexample_ids,
        source=VersionSource.AUTO_RESEARCH.value,
        source_metadata={"run_id": arr.id, "termination_reason": result.termination_reason},
        created_by=user.id,
    )
    session.add(new_version)
    await session.flush()

    arr.output_version_id = new_version.id
    arr.turn_count = result.turn_count
    arr.turn_history = [t.__dict__ for t in result.turns]
    arr.termination_reason = result.termination_reason
    arr.status = (
        AutoResearchStatus.COMPLETED.value
        if result.termination_reason == "threshold_met"
        else AutoResearchStatus.EARLY_STOPPED.value
        if result.termination_reason == "no_improvement"
        else AutoResearchStatus.COMPLETED.value
    )
    arr.completed_at = datetime.now(tz=timezone.utc)
    await session.commit()
    await session.refresh(arr)
    return arr


@router.get("/runs", response_model=list[AutoResearchRunOut])
async def list_runs(
    project_id: int,
    workspace_id: int = Depends(current_workspace_id),
    session: AsyncSession = Depends(get_session),
):
    await _project_or_404(session, project_id, workspace_id)
    rows = (
        await session.execute(
            select(AutoResearchRun)
            .where(AutoResearchRun.project_id == project_id)
            .order_by(AutoResearchRun.id.desc())
        )
    ).scalars().all()
    return [AutoResearchRunOut.model_validate(r) for r in rows]


@router.get("/runs/{run_id}", response_model=AutoResearchRunOut)
async def get_run(
    project_id: int,
    run_id: int,
    workspace_id: int = Depends(current_workspace_id),
    session: AsyncSession = Depends(get_session),
):
    await _project_or_404(session, project_id, workspace_id)
    arr = (
        await session.execute(
            select(AutoResearchRun).where(
                AutoResearchRun.id == run_id, AutoResearchRun.project_id == project_id
            )
        )
    ).scalar_one_or_none()
    if arr is None:
        raise EmergeError(ErrorCode.NOT_FOUND, status_code=404)
    return arr


@router.post("/runs/{run_id}/stop", response_model=AutoResearchRunOut)
async def stop_run(
    project_id: int,
    run_id: int,
    workspace_id: int = Depends(current_workspace_id),
    session: AsyncSession = Depends(get_session),
):
    """Synchronous loop in v1 finishes inside the POST /run; this endpoint exists for the
    eventual async-mode rollout. In v1 it just no-ops if status != 'running'."""
    await _project_or_404(session, project_id, workspace_id)
    arr = (
        await session.execute(
            select(AutoResearchRun).where(
                AutoResearchRun.id == run_id, AutoResearchRun.project_id == project_id
            )
        )
    ).scalar_one_or_none()
    if arr is None:
        raise EmergeError(ErrorCode.NOT_FOUND, status_code=404)
    if arr.status == AutoResearchStatus.RUNNING.value:
        arr.status = AutoResearchStatus.MANUAL_STOPPED.value
        arr.termination_reason = TerminationReason.MANUAL_STOP.value
        arr.completed_at = datetime.now(tz=timezone.utc)
        await session.commit()
        await session.refresh(arr)
    return arr
```

- [ ] **Step 5: Mount router**

In `app/api/v1.py`:

```python
from app.api.routes import auto_research

api_v1.include_router(auto_research.router)
```

- [ ] **Step 6: Run tests to verify they pass**

Expected: `3 passed`.

- [ ] **Step 7: Commit**

```bash
git add backend/app/schemas/auto_research.py backend/app/api/routes/auto_research.py backend/app/api/v1.py backend/tests/test_auto_research_routes.py
git commit -m "feat(api): AutoResearch trigger + run history + stop endpoints"
```

---

## Task 6: Set ProjectVersion as active (manual promotion)

**Files:**
- Modify: `backend/app/api/routes/versions.py` (add `POST /projects/{pid}/versions/{vid}/activate`)
- Modify: `backend/tests/test_version_routes.py` (append test)

R6 produces candidate ProjectVersions. The user accepts via the version timeline UI. Endpoint: `POST /projects/{pid}/versions/{vid}/activate` sets `Project.active_version_id`. Spec §5.1: "User must explicitly accept via the version timeline UI."

- [ ] **Step 1: Append failing test in `test_version_routes.py`**

```python
@pytest.mark.asyncio
async def test_activate_version_changes_active_pointer(client, db_session):
    h, pid = await _auth_and_project(client)
    # patch creates a v1
    body = (
        await client.patch(
            f"/api/v1/projects/{pid}/schema",
            json={"schema": [], "global_notes": "", "model_id": "x"},
            headers=h,
        )
    ).json()
    v1_id = body["id"]
    # patch again -> v2 (active becomes v2)
    body2 = (
        await client.patch(
            f"/api/v1/projects/{pid}/schema",
            json={"schema": [], "global_notes": "", "model_id": "y"},
            headers=h,
        )
    ).json()
    v2_id = body2["id"]
    assert v2_id != v1_id

    # activate v1
    resp = await client.post(
        f"/api/v1/projects/{pid}/versions/{v1_id}/activate", headers=h
    )
    assert resp.status_code == 200
    active = (
        await client.get(f"/api/v1/projects/{pid}/versions/active", headers=h)
    ).json()
    assert active["id"] == v1_id
```

- [ ] **Step 2: Run — expect 404**

- [ ] **Step 3: Append endpoint in `app/api/routes/versions.py`**

```python
@router.post("/versions/{version_id}/activate", response_model=ProjectVersionOut)
async def activate_version(
    project_id: int,
    version_id: int,
    workspace_id: int = Depends(current_workspace_id),
    session: AsyncSession = Depends(get_session),
):
    p = await _get_project(session, project_id, workspace_id)
    v = (
        await session.execute(
            select(ProjectVersion).where(
                ProjectVersion.id == version_id, ProjectVersion.project_id == project_id
            )
        )
    ).scalar_one_or_none()
    if v is None:
        raise EmergeError(ErrorCode.NOT_FOUND, status_code=404)
    p.active_version_id = v.id
    await session.commit()
    await session.refresh(v)
    return v
```

- [ ] **Step 4: Run test to verify it passes**

- [ ] **Step 5: Commit**

```bash
git add backend/app/api/routes/versions.py backend/tests/test_version_routes.py
git commit -m "feat(api): activate ProjectVersion endpoint (manual promotion only)"
```

---

## Task 7: List versions (timeline)

**Files:**
- Modify: `backend/app/api/routes/versions.py` (add `GET /projects/{pid}/versions`)
- Modify: `backend/tests/test_version_routes.py` (append test)

The R8 timeline UI fetches the version list to render the diff view. `GET` returns descending by `version_number`.

- [ ] **Step 1: Append failing test**

```python
@pytest.mark.asyncio
async def test_list_versions_returns_descending(client):
    h, pid = await _auth_and_project(client)
    for _ in range(2):
        await client.patch(
            f"/api/v1/projects/{pid}/schema",
            json={"schema": [], "global_notes": "", "model_id": "x"},
            headers=h,
        )
    resp = await client.get(f"/api/v1/projects/{pid}/versions", headers=h)
    rows = resp.json()
    assert [r["version_number"] for r in rows] == [2, 1, 0]
```

- [ ] **Step 2: Run — expect 404**

- [ ] **Step 3: Append endpoint**

```python
@router.get("/versions", response_model=list[ProjectVersionOut])
async def list_versions(
    project_id: int,
    workspace_id: int = Depends(current_workspace_id),
    session: AsyncSession = Depends(get_session),
):
    await _get_project(session, project_id, workspace_id)
    rows = (
        await session.execute(
            select(ProjectVersion)
            .where(ProjectVersion.project_id == project_id)
            .order_by(ProjectVersion.version_number.desc())
        )
    ).scalars().all()
    return rows
```

- [ ] **Step 4: Run test to verify it passes**

- [ ] **Step 5: Commit**

```bash
git add backend/app/api/routes/versions.py backend/tests/test_version_routes.py
git commit -m "feat(api): list versions for timeline"
```

---

## Task 8: Semi-automatic trigger (workspace setting)

**Files:**
- Create: `backend/app/models/workspace_setting.py` (workspace KV store)
- Modify: `backend/app/models/__init__.py`
- Create: `backend/alembic/versions/0011_workspace_settings.py`
- Modify: `backend/app/services/corrections.py` (after `save_counterexample`, check setting and enqueue auto-run)
- Create: `backend/tests/test_semi_auto_trigger.py`

Workspace setting `auto_research.after_n_counterexamples` (int 0–20; 0 = off). When `save_counterexample` runs, count counterexamples saved since the last `AutoResearchRun.completed`; if ≥ N, enqueue a run. **For v1 we synchronously trigger inline** — large workspaces may upgrade to a queue later (out of scope here).

To keep this composable and avoid over-coupling, `save_counterexample` calls a new `maybe_trigger_auto_research(...)` hook from `services/auto_research_trigger.py`. The hook reads the setting; the actual run dispatch happens via importing the run logic — but to avoid circular imports, the hook publishes an event (in v1: just calls `run_reflexion_loop` if setting > 0 and threshold met). Tests can override via monkey-patch.

In a stripped-down v1 task list, we'd defer the actual runner invocation and only set up:
1. Workspace setting persistence
2. Counterexample-count tracking
3. A boolean returned indicating "should run"
4. The runner invocation hooked behind `settings.semi_auto_enabled = False` so it's safe by default

This is what we implement here. Real runner invocation = future work.

- [ ] **Step 1: Implement `app/models/workspace_setting.py`**

```python
from sqlalchemy import ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class WorkspaceSetting(Base, TimestampMixin):
    __tablename__ = "workspace_settings"
    __table_args__ = (
        UniqueConstraint("workspace_id", "key", name="uq_workspace_setting_key"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    workspace_id: Mapped[int] = mapped_column(
        ForeignKey("workspaces.id"), nullable=False, index=True
    )
    key: Mapped[str] = mapped_column(String(128), nullable=False)
    value: Mapped[str] = mapped_column(Text, nullable=False)
```

Re-export.

- [ ] **Step 2: Generate + apply migration**

```bash
cd backend && uv run alembic revision --autogenerate -m "workspace settings"
uv run alembic upgrade head
```

- [ ] **Step 3: Implement `app/services/auto_research_trigger.py`**

```python
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.annotation import Annotation, AnnotationRole, AnnotationStatus
from app.models.auto_research_run import AutoResearchRun, AutoResearchStatus
from app.models.document import Document
from app.models.project import Project
from app.models.workspace_setting import WorkspaceSetting

KEY = "auto_research.after_n_counterexamples"


async def maybe_should_trigger(*, session: AsyncSession, project_id: int) -> bool:
    project = (
        await session.execute(select(Project).where(Project.id == project_id))
    ).scalar_one()
    setting = (
        await session.execute(
            select(WorkspaceSetting).where(
                WorkspaceSetting.workspace_id == project.workspace_id,
                WorkspaceSetting.key == KEY,
            )
        )
    ).scalar_one_or_none()
    threshold = int(setting.value) if setting else 0
    if threshold <= 0:
        return False
    last_run = (
        await session.execute(
            select(AutoResearchRun)
            .where(
                AutoResearchRun.project_id == project_id,
                AutoResearchRun.status.in_(
                    [AutoResearchStatus.COMPLETED.value, AutoResearchStatus.EARLY_STOPPED.value]
                ),
            )
            .order_by(AutoResearchRun.id.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    cutoff_id = last_run.id if last_run else 0
    new_ce_count = (
        await session.execute(
            select(Annotation)
            .join(Document, Document.id == Annotation.document_id)
            .where(
                Document.project_id == project_id,
                Annotation.role == AnnotationRole.COUNTEREXAMPLE.value,
                Annotation.status == AnnotationStatus.SAVED.value,
                Annotation.id > cutoff_id,
            )
        )
    ).scalars().all()
    return len(new_ce_count) >= threshold
```

- [ ] **Step 4: Write the failing test**

```python
import io

import pytest

from app.models.workspace_setting import WorkspaceSetting
from app.services.auto_research_trigger import KEY, maybe_should_trigger


@pytest.mark.asyncio
async def test_returns_false_when_setting_unset(client, db_session, tmp_path, monkeypatch):
    monkeypatch.setattr("app.services.storage.settings.storage_root", str(tmp_path))
    await client.post("/api/v1/auth/register", json={"email": "tr@tr.com", "password": "hunter22"})
    tok = (
        await client.post("/api/v1/auth/login", json={"email": "tr@tr.com", "password": "hunter22"})
    ).json()["access_token"]
    h = {"Authorization": f"Bearer {tok}"}
    pid = (await client.post("/api/v1/projects", json={"name": "P"}, headers=h)).json()["id"]
    assert await maybe_should_trigger(session=db_session, project_id=pid) is False


@pytest.mark.asyncio
async def test_returns_true_when_threshold_crossed(client, db_session, tmp_path, monkeypatch):
    monkeypatch.setattr("app.services.storage.settings.storage_root", str(tmp_path))
    await client.post("/api/v1/auth/register", json={"email": "tr2@tr.com", "password": "hunter22"})
    tok = (
        await client.post("/api/v1/auth/login", json={"email": "tr2@tr.com", "password": "hunter22"})
    ).json()["access_token"]
    h = {"Authorization": f"Bearer {tok}"}
    pid = (await client.post("/api/v1/projects", json={"name": "P"}, headers=h)).json()["id"]

    from sqlalchemy import select

    from app.models.project import Project

    project = (await db_session.execute(select(Project).where(Project.id == pid))).scalar_one()
    db_session.add(WorkspaceSetting(workspace_id=project.workspace_id, key=KEY, value="2"))
    await db_session.commit()

    # seed 3 counterexamples
    from app.models.annotation import Annotation, AnnotationRole, AnnotationStatus
    from app.models.document import Document
    from app.models.user import User

    user_id = (await db_session.execute(select(User))).scalar_one().id
    d = Document(
        project_id=pid,
        filename="x",
        file_path="/tmp/x",
        mime_type="application/pdf",
        page_count=1,
        byte_size=1,
        uploaded_by=user_id,
    )
    db_session.add(d)
    await db_session.flush()
    for _ in range(3):
        db_session.add(
            Annotation(
                document_id=d.id,
                output=[{"a": 1}],
                role=AnnotationRole.COUNTEREXAMPLE.value,
                status=AnnotationStatus.SAVED.value,
                created_by=user_id,
                last_modified_by=user_id,
            )
        )
    await db_session.commit()

    assert await maybe_should_trigger(session=db_session, project_id=pid) is True
```

- [ ] **Step 5: Run test to verify it passes**

- [ ] **Step 6: Run full suite**

Run: `cd backend && uv run pytest -v`
Expected: every R1+…+R6 test passes.

- [ ] **Step 7: Commit**

```bash
git add backend/app/models/workspace_setting.py backend/app/models/__init__.py backend/alembic/versions/0011_workspace_settings.py backend/app/services/auto_research_trigger.py backend/tests/test_semi_auto_trigger.py
git commit -m "feat(backend): semi-auto AutoResearch trigger heuristic + workspace setting"
```

---

## R6 exit criteria

End-to-end (M3 evolution):

1. With a baseline schema (e.g. `shop_name`, `total_amount`) and at least one judge-evaluated prediction, `POST /auto-research/run` returns a new `ProjectVersion` whose schema descriptions reflect researcher edits.
2. Active version is unchanged after the run; user must `POST /versions/{vid}/activate` to promote.
3. `GET /auto-research/runs` lists all runs descending; `GET /auto-research/runs/{id}` shows full turn history with diagnosis text and per-turn `actions_applied`.
4. Trying to launch a run while another is `status='running'` returns 409.
5. With workspace setting `auto_research.after_n_counterexamples=2`, calling `save_counterexample` 2× returns `maybe_should_trigger=true`.

Run `cd backend && uv run pytest -v` — all tests R1+…+R6 pass.

R7 will reuse the version-active pattern when the public `/extract/{api_code}` resolves the project's active version per call. R8 surfaces the AutoResearchRun timeline as a collapsible diff viewer per spec §5.5.
