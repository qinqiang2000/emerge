# R5 — Confidence Loop & Calibration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Compute, calibrate, and surface a 2-signal confidence score (LLM-as-judge + counterexample regression) per Document and per Project, with a Bayesian-calibrated judge precision and a human review queue. After R5: every Prediction can be judged on demand; per-Project score is visible and recomputed eagerly on the four trigger events; the UI has the data it needs to render the three review buckets.

**Architecture:**
- **Pure scoring functions, side-effectful service.** `compute_score(judge_component, ce_score, weight)` and the Beta-posterior helpers are pure — testable without DB. The orchestrator (`run_judge_for_project`, `recompute_project_score`) handles I/O.
- **Judge is just another `Provider`.** Reuse the R3 `Provider` protocol; `JudgeProvider` wraps the same SDK call but with a different prompt + a `judge_response_schema` (per-field verdict matrix). FakeJudgeProvider drives tests.
- **Calibration table is keyed `(project, judge_model_version)`** so swapping the judge model resets the prior. Beta posterior is computed *on read* from raw counts (`alpha = 8 + tp`, `beta = 2 + fp`). No background recompute; storage is the counts only.
- **Vibe-check set is a query view, not a stored set.** A SQL helper returns Predictions whose `document_id` has no later `Annotation(role='none', status='saved')`. This satisfies spec §4.1 precisely.
- **Score is recomputed eagerly** on the four trigger events from spec §4.1: new Annotation saved, new Prediction generated, new judge run, new feedback API call. We add hooks in those code paths to call `recompute_project_score`.

**Tech Stack:** R1+R2+R3+R4 stack. New: `scipy>=1.13.0` for Beta inverse-CDF (95% CI), but only if cheap — otherwise hand-roll using the closed-form normal approximation (mean ± 1.96·sqrt(α·β / ((α+β)²·(α+β+1)))). Plan defaults to scipy because the dep is small and CI display is per-spec.

**Spec sections covered:** §4.1 (formula, vibe-check definition, eager-recompute triggers), §4.2 (3 review groups), §4.3 (Beta calibration with `Beta(8,2)` prior; precision side updates `α/β`; recall side feeds spot-check intensity but not score), §4.4 (no $ budget; only `max_turn` and `early_stop_no_improvement` bound — applies to R6 but the principle is shared).

**Depends on:** R4 (Annotation save path; counterexample list); R3 (Prediction write; ProjectVersion).

---

## File Structure

```
backend/app/
├── models/
│   └── judge_calibration.py       # JudgeCalibration table
├── schemas/
│   └── score.py                   # ProjectScoreOut, DocumentScoreOut, ReviewBucketOut
├── engine/
│   ├── judge.py                   # FakeJudgeProvider, JudgeProvider, run_judge
│   ├── score.py                   # pure score formulas; calibration math
│   ├── regression.py              # counterexample_regression_score(...)
│   └── recompute.py               # recompute_project_score (orchestrator)
├── api/routes/
│   └── scores.py                  # GET /projects/{pid}/score, /review-queue, /calibration
└── alembic/versions/
    └── 0009_judge_calibration.py
```

Tests:

```
backend/tests/
├── test_score_formula.py
├── test_calibration_beta.py
├── test_regression_score.py
├── test_judge_runner.py
├── test_recompute.py
└── test_score_routes.py
```

---

## Task 1: JudgeCalibration model + migration

**Files:**
- Create: `backend/app/models/judge_calibration.py`
- Modify: `backend/app/models/__init__.py`
- Create: `backend/alembic/versions/0009_judge_calibration.py`
- Create: `backend/tests/test_calibration_model.py`

`tp/fp/fn/tn` are integer counts; `alpha/beta` are derived on read. We do not store them — invariant (`alpha = 8 + tp` etc.) is enforced in code, not DB.

- [ ] **Step 1: Write the failing test**

```python
import pytest

from app.models.judge_calibration import JudgeCalibration
from app.models.project import Project
from app.models.user import User
from app.models.workspace import Workspace


@pytest.mark.asyncio
async def test_calibration_persists(db_session):
    user = User(email="cal@cal.com", password_hash="x")
    db_session.add(user)
    await db_session.flush()
    ws = Workspace(name="W", owner_id=user.id)
    db_session.add(ws)
    await db_session.flush()
    p = Project(workspace_id=ws.id, name="P", created_by=user.id)
    db_session.add(p)
    await db_session.flush()

    c = JudgeCalibration(
        project_id=p.id, judge_model_version="claude-opus-4-7", tp=0, fp=0, fn=0, tn=0
    )
    db_session.add(c)
    await db_session.commit()
    assert c.id is not None


@pytest.mark.asyncio
async def test_unique_per_project_judge(db_session):
    user = User(email="cal2@cal.com", password_hash="x")
    db_session.add(user)
    await db_session.flush()
    ws = Workspace(name="W", owner_id=user.id)
    db_session.add(ws)
    await db_session.flush()
    p = Project(workspace_id=ws.id, name="P", created_by=user.id)
    db_session.add(p)
    await db_session.flush()
    db_session.add(JudgeCalibration(project_id=p.id, judge_model_version="m"))
    await db_session.commit()
    db_session.add(JudgeCalibration(project_id=p.id, judge_model_version="m"))
    with pytest.raises(Exception):
        await db_session.commit()
```

- [ ] **Step 2: Run — expect ImportError**

- [ ] **Step 3: Implement `app/models/judge_calibration.py`**

```python
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class JudgeCalibration(Base, TimestampMixin):
    __tablename__ = "judge_calibrations"
    __table_args__ = (
        UniqueConstraint(
            "project_id", "judge_model_version", name="uq_calibration_project_judge"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id"), nullable=False, index=True
    )
    judge_model_version: Mapped[str] = mapped_column(String(128), nullable=False)
    tp: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    fp: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    fn: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    tn: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    observation_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
```

Re-export.

- [ ] **Step 4: Run test to verify it passes**

- [ ] **Step 5: Generate + apply migration**

```bash
cd backend && uv run alembic revision --autogenerate -m "judge calibration table"
uv run alembic upgrade head
```

- [ ] **Step 6: Commit**

```bash
git add backend/app/models/judge_calibration.py backend/app/models/__init__.py backend/alembic/versions/0009_judge_calibration.py backend/tests/test_calibration_model.py
git commit -m "feat(backend): add JudgeCalibration model + 0009 migration"
```

---

## Task 2: Score formula + calibration math (pure)

**Files:**
- Create: `backend/app/engine/score.py`
- Create: `backend/tests/test_score_formula.py`
- Create: `backend/tests/test_calibration_beta.py`
- Add `scipy>=1.13.0` to `pyproject.toml`

`compute_judge_component`, `compute_score`, `beta_posterior(tp, fp)`, `precision_point_estimate(α, β)`, `precision_ci_95(α, β)` — all pure. Lookup tables for verdict-pair → weight from spec §4.1.

- [ ] **Step 1: Add `scipy>=1.13.0` to deps**, run `uv sync --extra dev`.

- [ ] **Step 2: Write the failing tests**

`test_score_formula.py`:

```python
from app.engine.score import (
    JudgeVerdict,
    HumanVerdict,
    compute_judge_component,
    compute_score,
    verdict_pair_weight,
)


def test_pair_weights_match_spec():
    # spec §4.1 table
    assert verdict_pair_weight(JudgeVerdict.UP, HumanVerdict.UP) == 1.0
    assert verdict_pair_weight(JudgeVerdict.UP, HumanVerdict.DOWN) == 0.0
    assert verdict_pair_weight(JudgeVerdict.UP, HumanVerdict.NOT_SEEN, calibrated=0.82) == 0.82
    assert verdict_pair_weight(JudgeVerdict.DOWN, HumanVerdict.FIXED) == 1.0
    assert verdict_pair_weight(JudgeVerdict.DOWN, HumanVerdict.SKIPPED) == 0.0
    assert verdict_pair_weight(JudgeVerdict.DOWN, HumanVerdict.DOWN) == 0.0
    assert verdict_pair_weight(JudgeVerdict.UNCERTAIN, HumanVerdict.FIXED) == 1.0


def test_judge_component_average():
    pairs = [
        (JudgeVerdict.UP, HumanVerdict.UP),
        (JudgeVerdict.UP, HumanVerdict.UP),
        (JudgeVerdict.DOWN, HumanVerdict.SKIPPED),
        (JudgeVerdict.DOWN, HumanVerdict.FIXED),
    ]
    out = compute_judge_component(pairs, judge_precision_calibrated=0.8)
    assert out == (1.0 + 1.0 + 0.0 + 1.0) / 4


def test_judge_component_uses_calibrated_when_human_unseen():
    pairs = [(JudgeVerdict.UP, HumanVerdict.NOT_SEEN)]
    assert compute_judge_component(pairs, judge_precision_calibrated=0.7) == 0.7


def test_compute_score_default_weights():
    assert compute_score(judge_component=1.0, ce_score=1.0) == 1.0
    assert compute_score(judge_component=0.5, ce_score=0.5) == 0.5
    assert compute_score(judge_component=0.8, ce_score=0.4) == pytest.approx(0.7 * 0.8 + 0.3 * 0.4)


def test_compute_score_returns_one_when_ce_pool_empty_marker():
    """When ce_score is exactly None it means pool is empty → use 1.0 (spec §4.1)."""
    assert compute_score(judge_component=0.6, ce_score=None) == pytest.approx(0.7 * 0.6 + 0.3 * 1.0)


def test_compute_score_custom_weights():
    assert compute_score(
        judge_component=1.0, ce_score=0.0, judge_weight=0.5, ce_weight=0.5
    ) == 0.5


import pytest  # for approx
```

`test_calibration_beta.py`:

```python
from app.engine.score import (
    PRIOR_ALPHA,
    PRIOR_BETA,
    beta_posterior,
    precision_ci_95,
    precision_point_estimate,
)


def test_default_prior_is_8_2():
    assert (PRIOR_ALPHA, PRIOR_BETA) == (8, 2)


def test_posterior_uses_only_tp_fp():
    a, b = beta_posterior(tp=5, fp=3)
    assert a == 8 + 5
    assert b == 2 + 3


def test_point_estimate_at_prior_is_eighty_percent():
    a, b = beta_posterior(tp=0, fp=0)
    assert precision_point_estimate(a, b) == pytest.approx(0.80, abs=1e-6)


def test_ci_collapses_with_data():
    wide_lo, wide_hi = precision_ci_95(*beta_posterior(0, 0))
    narrow_lo, narrow_hi = precision_ci_95(*beta_posterior(50, 5))
    assert (wide_hi - wide_lo) > (narrow_hi - narrow_lo)


def test_ci_inside_zero_one():
    lo, hi = precision_ci_95(*beta_posterior(10, 5))
    assert 0 <= lo <= hi <= 1


import pytest
```

- [ ] **Step 3: Run — expect ImportError**

- [ ] **Step 4: Implement `app/engine/score.py`**

```python
from enum import Enum

from scipy import stats

PRIOR_ALPHA = 8
PRIOR_BETA = 2

DEFAULT_JUDGE_WEIGHT = 0.7
DEFAULT_CE_WEIGHT = 0.3


class JudgeVerdict(str, Enum):
    UP = "up"
    DOWN = "down"
    UNCERTAIN = "uncertain"


class HumanVerdict(str, Enum):
    UP = "up"
    DOWN = "down"
    FIXED = "fixed"      # human corrected the value
    SKIPPED = "skipped"  # human shown but did nothing
    NOT_SEEN = "not_seen"  # human has not been shown this field


def verdict_pair_weight(
    judge: JudgeVerdict, human: HumanVerdict, *, calibrated: float = 0.8
) -> float:
    """Spec §4.1 verdict pair → weight table."""
    if judge is JudgeVerdict.UP and human is HumanVerdict.UP:
        return 1.0
    if judge is JudgeVerdict.UP and human is HumanVerdict.DOWN:
        return 0.0
    if judge is JudgeVerdict.UP and human is HumanVerdict.NOT_SEEN:
        return calibrated
    if judge in (JudgeVerdict.DOWN, JudgeVerdict.UNCERTAIN) and human is HumanVerdict.FIXED:
        return 1.0
    if judge in (JudgeVerdict.DOWN, JudgeVerdict.UNCERTAIN) and human is HumanVerdict.SKIPPED:
        return 0.0
    if judge in (JudgeVerdict.DOWN, JudgeVerdict.UNCERTAIN) and human is HumanVerdict.DOWN:
        return 0.0
    if judge is JudgeVerdict.UP and human is HumanVerdict.FIXED:
        return 1.0  # judge said up, human still fixed → benefit of the doubt: weight 1
    return 0.0  # any other combination is treated as 0


def compute_judge_component(
    pairs: list[tuple[JudgeVerdict, HumanVerdict]],
    *,
    judge_precision_calibrated: float,
) -> float:
    if not pairs:
        return 1.0  # no fields → trivially perfect
    total = 0.0
    for j, h in pairs:
        total += verdict_pair_weight(j, h, calibrated=judge_precision_calibrated)
    return total / len(pairs)


def compute_score(
    *,
    judge_component: float,
    ce_score: float | None,
    judge_weight: float = DEFAULT_JUDGE_WEIGHT,
    ce_weight: float = DEFAULT_CE_WEIGHT,
) -> float:
    """`ce_score=None` denotes empty counterexample pool → treated as 1.0 per spec."""
    ce = 1.0 if ce_score is None else ce_score
    return judge_weight * judge_component + ce_weight * ce


def beta_posterior(*, tp: int, fp: int) -> tuple[float, float]:
    return PRIOR_ALPHA + tp, PRIOR_BETA + fp


def precision_point_estimate(alpha: float, beta: float) -> float:
    return alpha / (alpha + beta)


def precision_ci_95(alpha: float, beta: float) -> tuple[float, float]:
    lo = stats.beta.ppf(0.025, alpha, beta)
    hi = stats.beta.ppf(0.975, alpha, beta)
    return float(lo), float(hi)
```

- [ ] **Step 5: Run tests to verify they pass**

Expected: `6 + 5 = 11 passed`.

- [ ] **Step 6: Commit**

```bash
git add backend/app/engine/score.py backend/pyproject.toml backend/tests/test_score_formula.py backend/tests/test_calibration_beta.py
git commit -m "feat(engine): pure score + Beta calibration helpers"
```

---

## Task 3: Counterexample regression scorer

**Files:**
- Create: `backend/app/engine/regression.py`
- Create: `backend/tests/test_regression_score.py`

Spec §4.1: `structurally_matches(pred.output, ce.output)` — array length identical; per-entity field set identical; per-field equivalence rules (numbers ±0.01; strings normalized to NFC + lowercased + trimmed; enums strict; nested arrays recurse). Pure function; takes two `list[dict]` values and returns bool.

The regression *scorer* iterates the saved counterexamples and re-runs prediction. Re-running prediction is delegated to a callable so tests use `FakeProvider`.

- [ ] **Step 1: Write the failing tests**

```python
import pytest

from app.engine.regression import (
    counterexample_regression_score,
    structurally_matches,
)


def test_match_identical_arrays():
    assert structurally_matches([{"a": 1}], [{"a": 1}]) is True


def test_mismatch_array_length():
    assert structurally_matches([{"a": 1}], [{"a": 1}, {"a": 2}]) is False


def test_match_with_number_tolerance():
    assert structurally_matches([{"x": 1.001}], [{"x": 1.0}]) is True
    assert structurally_matches([{"x": 1.5}], [{"x": 1.0}]) is False


def test_string_normalization():
    assert structurally_matches([{"s": "  Hello "}], [{"s": "hello"}]) is True


def test_field_set_difference():
    assert structurally_matches([{"a": 1}], [{"a": 1, "b": 2}]) is False


def test_nested_array_recursion():
    a = [{"items": [{"qty": 2}, {"qty": 3}]}]
    b = [{"items": [{"qty": 2.0}, {"qty": 3.0}]}]
    assert structurally_matches(a, b) is True


@pytest.mark.asyncio
async def test_regression_score_empty_pool_is_one():
    score = await counterexample_regression_score(counterexamples=[], rerun=lambda doc_id: [])
    assert score == 1.0


@pytest.mark.asyncio
async def test_regression_score_partial_hit():
    examples = [
        {"document_id": 1, "expected": [{"a": 1}]},
        {"document_id": 2, "expected": [{"a": 2}]},
        {"document_id": 3, "expected": [{"a": 3}]},
    ]
    scoring = {1: [{"a": 1}], 2: [{"a": 99}], 3: [{"a": 3}]}

    async def rerun(doc_id):
        return scoring[doc_id]

    score = await counterexample_regression_score(
        counterexamples=examples, rerun=rerun
    )
    assert score == pytest.approx(2 / 3)
```

- [ ] **Step 2: Run — expect ImportError**

- [ ] **Step 3: Implement `app/engine/regression.py`**

```python
import unicodedata
from collections.abc import Awaitable, Callable
from typing import Any

_NUMERIC_TOL = 1e-2


def _norm_string(s: str) -> str:
    return unicodedata.normalize("NFC", s).strip().lower()


def _values_equivalent(a: Any, b: Any) -> bool:
    if isinstance(a, bool) or isinstance(b, bool):
        return a is b
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return abs(float(a) - float(b)) <= _NUMERIC_TOL
    if isinstance(a, str) and isinstance(b, str):
        return _norm_string(a) == _norm_string(b)
    if isinstance(a, list) and isinstance(b, list):
        return structurally_matches(a, b) if all(isinstance(x, dict) for x in a + b) else _list_eq(a, b)
    if isinstance(a, dict) and isinstance(b, dict):
        return _dict_eq(a, b)
    return a == b


def _list_eq(a: list, b: list) -> bool:
    if len(a) != len(b):
        return False
    return all(_values_equivalent(x, y) for x, y in zip(a, b))


def _dict_eq(a: dict, b: dict) -> bool:
    if set(a.keys()) != set(b.keys()):
        return False
    return all(_values_equivalent(a[k], b[k]) for k in a)


def structurally_matches(pred: list[dict], expected: list[dict]) -> bool:
    if len(pred) != len(expected):
        return False
    return all(_dict_eq(p, e) for p, e in zip(pred, expected))


async def counterexample_regression_score(
    *,
    counterexamples: list[dict],
    rerun: Callable[[int], Awaitable[list[dict]]],
) -> float:
    """`counterexamples` items: {document_id, expected: list[dict]}.
    `rerun(doc_id)` is awaitable returning the re-predicted output to compare against.
    """
    if not counterexamples:
        return 1.0
    hits = 0
    for ce in counterexamples:
        actual = await rerun(ce["document_id"])
        if structurally_matches(actual, ce["expected"]):
            hits += 1
    return hits / len(counterexamples)
```

- [ ] **Step 4: Run test to verify it passes**

Expected: `8 passed`.

- [ ] **Step 5: Commit**

```bash
git add backend/app/engine/regression.py backend/tests/test_regression_score.py
git commit -m "feat(engine): structural match + counterexample regression scorer"
```

---

## Task 4: Judge runner

**Files:**
- Create: `backend/app/engine/judge.py`
- Create: `backend/tests/test_judge_runner.py`

`run_judge(prediction, document, schema, judge_provider) -> per_field_confidence` writes the per-field verdict matrix back into `Prediction.per_field_confidence`. Real `JudgeProvider` wraps an LLM call returning a JSON object `{ entity_idx: { field_name: verdict } }`. `FakeJudgeProvider` returns canned verdicts.

The judge prompt asks the model to act as auditor. We compose the prompt similarly to extraction: a system frame describing the auditor role, the schema as reference, the predicted JSON, and the document image. Output: a JSON object matching the verdict schema.

- [ ] **Step 1: Write the failing test**

```python
import pytest

from app.engine.judge import FakeJudgeProvider, run_judge
from app.engine.score import JudgeVerdict
from app.models.document import Document
from app.models.prediction import Prediction, PredictionStatus
from app.models.project import Project
from app.models.project_version import ProjectVersion, VersionSource
from app.models.user import User
from app.models.workspace import Workspace
from app.schemas.schema_field import FieldType, SchemaField


async def _scaffold(db_session) -> tuple[Project, ProjectVersion, Document, Prediction]:
    user = User(email="j@j.com", password_hash="x")
    db_session.add(user)
    await db_session.flush()
    ws = Workspace(name="W", owner_id=user.id)
    db_session.add(ws)
    await db_session.flush()
    p = Project(workspace_id=ws.id, name="P", created_by=user.id)
    db_session.add(p)
    await db_session.flush()
    fields = [SchemaField(name="shop_name", type=FieldType.STRING, description="d")]
    v = ProjectVersion(
        project_id=p.id,
        version_number=0,
        schema_snapshot=[f.model_dump() for f in fields],
        global_notes_snapshot="",
        model_id_snapshot="m",
        counterexample_ids=[],
        source=VersionSource.INITIAL.value,
        source_metadata={},
        created_by=user.id,
    )
    db_session.add(v)
    await db_session.flush()
    p.active_version_id = v.id
    d = Document(
        project_id=p.id,
        filename="x",
        file_path="/tmp/x",
        mime_type="application/pdf",
        page_count=1,
        byte_size=1,
        uploaded_by=user.id,
    )
    db_session.add(d)
    await db_session.flush()
    pred = Prediction(
        document_id=d.id,
        project_version_id=v.id,
        model_id="m",
        prompt_hash="h",
        output=[{"shop_name": "ABC"}],
        per_field_confidence={},
        status=PredictionStatus.SUCCESS.value,
    )
    db_session.add(pred)
    await db_session.commit()
    return p, v, d, pred


@pytest.mark.asyncio
async def test_run_judge_writes_per_field_confidence(db_session, tmp_path):
    p, v, d, pred = await _scaffold(db_session)
    fp = tmp_path / "x"
    fp.write_bytes(b"PDF")
    d.file_path = str(fp)
    await db_session.commit()

    fake = FakeJudgeProvider(canned=[{"0": {"shop_name": "up"}}])
    await run_judge(pred.id, session=db_session, judge=fake)
    await db_session.refresh(pred)
    assert pred.per_field_confidence == {"0": {"shop_name": "up"}}


@pytest.mark.asyncio
async def test_run_judge_failure_records_empty(db_session, tmp_path):
    p, v, d, pred = await _scaffold(db_session)
    fp = tmp_path / "x"
    fp.write_bytes(b"PDF")
    d.file_path = str(fp)
    await db_session.commit()

    fake = FakeJudgeProvider(canned=[RuntimeError("judge boom")])
    await run_judge(pred.id, session=db_session, judge=fake)
    await db_session.refresh(pred)
    # judge failure is non-fatal — confidence stays {}; UI shows "judge unavailable"
    assert pred.per_field_confidence == {}
```

- [ ] **Step 2: Run — expect ImportError**

- [ ] **Step 3: Implement `app/engine/judge.py`**

```python
import json
import logging
from collections import deque
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import Document
from app.models.prediction import Prediction
from app.models.project_version import ProjectVersion

log = logging.getLogger(__name__)


class JudgeProvider(Protocol):
    async def judge(
        self, *, system: str, predicted_output: list[dict], file_bytes: bytes, mime_type: str
    ) -> dict[str, dict[str, str]]:
        ...


JUDGE_SYSTEM_FRAME = """\
You are an evaluation auditor for emerge. You will see (a) the document image/PDF, (b) the
schema describing each expected field, (c) the predicted JSON. For each entity index and each
field present in the prediction, return a verdict:
- "up"        → the field value is correct given the document
- "down"      → the field value is wrong
- "uncertain" → you cannot confidently decide
Return ONLY a JSON object of shape: { "<entity_idx>": { "<field_name>": "up|down|uncertain" } }.
Do not include fields that are absent from the prediction.\
"""


def _judge_prompt(version: ProjectVersion, output: list[dict]) -> str:
    return (
        JUDGE_SYSTEM_FRAME
        + "\n\nSchema fields:\n"
        + json.dumps(version.schema_snapshot, ensure_ascii=False, indent=2)
        + "\n\nPredicted output:\n"
        + json.dumps(output, ensure_ascii=False, indent=2)
    )


class FakeJudgeProvider:
    def __init__(self, *, canned: list):
        self._queue = deque(canned)

    async def judge(self, *, system, predicted_output, file_bytes, mime_type):
        if not self._queue:
            raise RuntimeError("FakeJudgeProvider out of canned responses")
        nxt = self._queue.popleft()
        if isinstance(nxt, BaseException):
            raise nxt
        return nxt


async def run_judge(
    prediction_id: int,
    *,
    session: AsyncSession,
    judge: JudgeProvider,
) -> Prediction:
    pred = (
        await session.execute(select(Prediction).where(Prediction.id == prediction_id))
    ).scalar_one()
    doc = (await session.execute(select(Document).where(Document.id == pred.document_id))).scalar_one()
    version = (
        await session.execute(
            select(ProjectVersion).where(ProjectVersion.id == pred.project_version_id)
        )
    ).scalar_one()

    system = _judge_prompt(version, pred.output)
    try:
        with open(doc.file_path, "rb") as fh:
            body = fh.read()
        verdicts = await judge.judge(
            system=system,
            predicted_output=pred.output,
            file_bytes=body,
            mime_type=doc.mime_type,
        )
        pred.per_field_confidence = verdicts
    except Exception:
        log.exception("judge failed for prediction %d", pred.id)
        pred.per_field_confidence = {}
    await session.commit()
    await session.refresh(pred)
    return pred
```

- [ ] **Step 4: Run tests to verify they pass**

- [ ] **Step 5: Commit**

```bash
git add backend/app/engine/judge.py backend/tests/test_judge_runner.py
git commit -m "feat(engine): judge runner + FakeJudgeProvider"
```

---

## Task 5: Vibe-check view + recompute orchestrator

**Files:**
- Create: `backend/app/engine/recompute.py`
- Create: `backend/tests/test_recompute.py`

Vibe-check set per spec §4.1: `Document` whose latest `Prediction` is **not** covered by a later saved `Annotation(role='none')`.

`recompute_project_score(project_id, session) -> ProjectScoreResult` returns `{ score, judge_component, ce_component, observation_count, vibe_check_size }`. Does **not** call the judge — assumes judge has already been run on relevant predictions, so `per_field_confidence` is populated. Uses fake-able rerun callable for counterexample regression so unit tests don't need the full extraction pipeline.

- [ ] **Step 1: Write the failing tests**

```python
import pytest

from app.engine.recompute import vibe_check_predictions_query, recompute_project_score
from app.engine.score import HumanVerdict, JudgeVerdict
from app.models.annotation import Annotation, AnnotationRole, AnnotationStatus
from app.models.document import Document
from app.models.prediction import Prediction, PredictionStatus
from app.models.project import Project
from app.models.project_version import ProjectVersion, VersionSource
from app.models.user import User
from app.models.workspace import Workspace


async def _setup_with_two_docs(db_session) -> tuple[int, int, list[int]]:
    user = User(email="rc@rc.com", password_hash="x")
    db_session.add(user)
    await db_session.flush()
    ws = Workspace(name="W", owner_id=user.id)
    db_session.add(ws)
    await db_session.flush()
    p = Project(workspace_id=ws.id, name="P", created_by=user.id)
    db_session.add(p)
    await db_session.flush()
    v = ProjectVersion(
        project_id=p.id,
        version_number=0,
        schema_snapshot=[],
        global_notes_snapshot="",
        model_id_snapshot="m",
        counterexample_ids=[],
        source=VersionSource.INITIAL.value,
        source_metadata={},
        created_by=user.id,
    )
    db_session.add(v)
    await db_session.flush()
    p.active_version_id = v.id
    docs: list[int] = []
    for n in ("a", "b"):
        d = Document(
            project_id=p.id,
            filename=n,
            file_path=f"/tmp/{n}",
            mime_type="application/pdf",
            page_count=1,
            byte_size=1,
            uploaded_by=user.id,
        )
        db_session.add(d)
        await db_session.flush()
        docs.append(d.id)
    await db_session.commit()
    return user.id, p.id, docs


@pytest.mark.asyncio
async def test_vibe_check_excludes_documents_with_saved_annotation(db_session):
    uid, pid, docs = await _setup_with_two_docs(db_session)
    # both docs have a prediction
    for did in docs:
        db_session.add(
            Prediction(
                document_id=did,
                project_version_id=None,
                model_id="m",
                prompt_hash="h",
                output=[{"a": 1}],
                per_field_confidence={"0": {"a": "up"}},
                status=PredictionStatus.SUCCESS.value,
            )
        )
    await db_session.commit()
    # second doc has saved annotation (covers prediction → excludes from vibe-check)
    db_session.add(
        Annotation(
            document_id=docs[1],
            output=[{"a": 1}],
            role=AnnotationRole.NONE.value,
            status=AnnotationStatus.SAVED.value,
            created_by=uid,
            last_modified_by=uid,
        )
    )
    await db_session.commit()

    vibe_doc_ids = [
        row[0]
        for row in (await db_session.execute(vibe_check_predictions_query(pid))).all()
    ]
    # only doc[0] in vibe-check
    assert set(vibe_doc_ids) == {docs[0]}


@pytest.mark.asyncio
async def test_recompute_score_with_one_judge_up_and_no_counterexamples(db_session):
    uid, pid, docs = await _setup_with_two_docs(db_session)
    db_session.add(
        Prediction(
            document_id=docs[0],
            project_version_id=None,
            model_id="m",
            prompt_hash="h",
            output=[{"a": 1}],
            per_field_confidence={"0": {"a": "up"}},
            status=PredictionStatus.SUCCESS.value,
        )
    )
    await db_session.commit()

    async def rerun(doc_id):
        return []  # ce pool empty so unused

    result = await recompute_project_score(project_id=pid, session=db_session, rerun=rerun)
    # judge says up, human not seen, calibrated 0.8 (prior) → judge_component = 0.8
    # ce empty → ce contributes 1.0; total = 0.7*0.8 + 0.3*1.0 = 0.86
    assert result.score == pytest.approx(0.7 * 0.8 + 0.3 * 1.0, abs=1e-3)
```

- [ ] **Step 2: Run — expect ImportError**

- [ ] **Step 3: Implement `app/engine/recompute.py`**

```python
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from sqlalchemy import Select, and_, exists, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.engine.regression import counterexample_regression_score
from app.engine.score import (
    HumanVerdict,
    JudgeVerdict,
    beta_posterior,
    compute_judge_component,
    compute_score,
    precision_point_estimate,
)
from app.models.annotation import Annotation, AnnotationRole, AnnotationStatus
from app.models.document import Document
from app.models.judge_calibration import JudgeCalibration
from app.models.prediction import Prediction


def vibe_check_predictions_query(project_id: int) -> Select:
    """Returns SQL: doc_id of Documents in project whose latest Prediction is NOT covered by
    a later saved Annotation(role='none'). Implemented as: Documents with at least one
    Prediction AND no saved role=none Annotation.
    """
    has_saved_none = exists().where(
        and_(
            Annotation.document_id == Document.id,
            Annotation.role == AnnotationRole.NONE.value,
            Annotation.status == AnnotationStatus.SAVED.value,
        )
    )
    has_prediction = exists().where(Prediction.document_id == Document.id)
    return select(Document.id).where(
        Document.project_id == project_id, has_prediction, ~has_saved_none
    )


@dataclass
class ProjectScoreResult:
    score: float
    judge_component: float
    ce_component: float
    observation_count: int
    vibe_check_size: int


async def recompute_project_score(
    *,
    project_id: int,
    session: AsyncSession,
    rerun: Callable[[int], Awaitable[list[dict]]],
    judge_model_version: str = "claude-opus-4-7",
) -> ProjectScoreResult:
    # 1. find vibe-check docs and their latest predictions
    doc_ids = (
        await session.execute(vibe_check_predictions_query(project_id))
    ).scalars().all()
    pairs: list[tuple[JudgeVerdict, HumanVerdict]] = []
    for did in doc_ids:
        latest = (
            await session.execute(
                select(Prediction)
                .where(Prediction.document_id == did)
                .order_by(Prediction.id.desc())
                .limit(1)
            )
        ).scalar_one()
        for ent_idx, fields in (latest.per_field_confidence or {}).items():
            for fname, verdict_str in fields.items():
                try:
                    j = JudgeVerdict(verdict_str)
                except ValueError:
                    continue
                pairs.append((j, HumanVerdict.NOT_SEEN))

    # 2. calibration → judge_precision_calibrated
    cal = (
        await session.execute(
            select(JudgeCalibration).where(
                JudgeCalibration.project_id == project_id,
                JudgeCalibration.judge_model_version == judge_model_version,
            )
        )
    ).scalar_one_or_none()
    tp = cal.tp if cal else 0
    fp = cal.fp if cal else 0
    a, b = beta_posterior(tp=tp, fp=fp)
    calibrated = precision_point_estimate(a, b)

    # 3. judge component
    judge_component = compute_judge_component(pairs, judge_precision_calibrated=calibrated)

    # 4. counterexample regression
    ce_rows = (
        await session.execute(
            select(Annotation, Document.id)
            .join(Document, Document.id == Annotation.document_id)
            .where(
                Document.project_id == project_id,
                Annotation.role == AnnotationRole.COUNTEREXAMPLE.value,
                Annotation.status == AnnotationStatus.SAVED.value,
            )
        )
    ).all()
    ce_score: float | None
    if not ce_rows:
        ce_score = None
        ce_component_for_return = 1.0
    else:
        items = [{"document_id": d_id, "expected": ann.output} for ann, d_id in ce_rows]
        ce_score = await counterexample_regression_score(counterexamples=items, rerun=rerun)
        ce_component_for_return = ce_score

    # 5. compose
    score = compute_score(judge_component=judge_component, ce_score=ce_score)
    return ProjectScoreResult(
        score=score,
        judge_component=judge_component,
        ce_component=ce_component_for_return,
        observation_count=len(pairs),
        vibe_check_size=len(doc_ids),
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Expected: `2 passed`.

- [ ] **Step 5: Commit**

```bash
git add backend/app/engine/recompute.py backend/tests/test_recompute.py
git commit -m "feat(engine): vibe-check query + recompute_project_score orchestrator"
```

---

## Task 6: Calibration update on (judge, human) verdict pair

**Files:**
- Modify: `backend/app/engine/recompute.py` (add `record_human_verdict_pair`)
- Modify: `backend/app/api/routes/annotations.py` (call `record_human_verdict_pair` on annotation save)
- Create: `backend/tests/test_calibration_update.py`

When a user saves an Annotation that *fixes a field* (i.e. the corrected output differs from the latest prediction's output), update calibration: judge said `up` + human said `down/fixed` → `fp += 1`. Judge said `down` + human still fixed it → no calibration impact (`fn += 1` is recall side, not displayed score).

We treat field-level diff from `parent_prediction.output` to `annotation.output` as the human verdict signal. Pure helper: `derive_pairs_from_correction(prediction, annotation, schema)`.

- [ ] **Step 1: Write the failing tests**

```python
import pytest
from sqlalchemy import select

from app.engine.recompute import record_human_verdict_pair
from app.engine.score import JudgeVerdict
from app.models.judge_calibration import JudgeCalibration


@pytest.mark.asyncio
async def test_record_pair_increments_fp_when_judge_up_human_down(db_session):
    # seed calibration row
    from app.models.project import Project
    from app.models.user import User
    from app.models.workspace import Workspace

    user = User(email="cu@cu.com", password_hash="x")
    db_session.add(user)
    await db_session.flush()
    ws = Workspace(name="W", owner_id=user.id)
    db_session.add(ws)
    await db_session.flush()
    p = Project(workspace_id=ws.id, name="P", created_by=user.id)
    db_session.add(p)
    await db_session.commit()

    await record_human_verdict_pair(
        session=db_session,
        project_id=p.id,
        judge_model_version="m",
        judge_verdict=JudgeVerdict.UP,
        human_fixed=True,
    )
    await record_human_verdict_pair(
        session=db_session,
        project_id=p.id,
        judge_model_version="m",
        judge_verdict=JudgeVerdict.UP,
        human_fixed=False,
    )

    cal = (
        await db_session.execute(
            select(JudgeCalibration).where(JudgeCalibration.project_id == p.id)
        )
    ).scalar_one()
    assert cal.tp == 1
    assert cal.fp == 1
    assert cal.observation_count == 2
```

- [ ] **Step 2: Run — expect ImportError on `record_human_verdict_pair`**

- [ ] **Step 3: Append to `app/engine/recompute.py`**

```python
async def record_human_verdict_pair(
    *,
    session: AsyncSession,
    project_id: int,
    judge_model_version: str,
    judge_verdict: JudgeVerdict,
    human_fixed: bool,
) -> JudgeCalibration:
    """Update calibration counts.
    - judge=up, human did not fix → tp += 1
    - judge=up, human fixed → fp += 1
    - judge=down/uncertain, human fixed → fn += 1
    - judge=down/uncertain, human did not fix → tn += 1
    """
    cal = (
        await session.execute(
            select(JudgeCalibration).where(
                JudgeCalibration.project_id == project_id,
                JudgeCalibration.judge_model_version == judge_model_version,
            )
        )
    ).scalar_one_or_none()
    if cal is None:
        cal = JudgeCalibration(
            project_id=project_id, judge_model_version=judge_model_version
        )
        session.add(cal)
        await session.flush()

    if judge_verdict is JudgeVerdict.UP and not human_fixed:
        cal.tp += 1
    elif judge_verdict is JudgeVerdict.UP and human_fixed:
        cal.fp += 1
    elif judge_verdict in (JudgeVerdict.DOWN, JudgeVerdict.UNCERTAIN) and human_fixed:
        cal.fn += 1
    else:
        cal.tn += 1
    cal.observation_count += 1
    await session.commit()
    await session.refresh(cal)
    return cal
```

- [ ] **Step 4: Run test to verify it passes**

- [ ] **Step 5: Wire into annotation save (call site only)**

Modify `app/api/routes/annotations.py`'s `create_annotation`. After `save_correction`, derive verdict pairs from the diff between `parent_prediction.output` and `payload.output`, and call `record_human_verdict_pair` per field. To keep logic simple in v1, treat *any difference* on a field as `human_fixed=True`; identical = `human_fixed=False`. If `parent_prediction_id` is None, skip calibration update.

```python
# inside create_annotation, after save_correction
from app.engine.recompute import record_human_verdict_pair
from app.engine.score import JudgeVerdict
from app.models.prediction import Prediction
from app.settings import settings  # for default judge model version

if payload.parent_prediction_id is not None:
    parent = (
        await session.execute(
            select(Prediction).where(Prediction.id == payload.parent_prediction_id)
        )
    ).scalar_one_or_none()
    if parent is not None:
        # iterate over judge verdicts already in parent.per_field_confidence
        for ent_idx_str, field_verdicts in (parent.per_field_confidence or {}).items():
            try:
                ent_idx = int(ent_idx_str)
            except ValueError:
                continue
            old_entity = parent.output[ent_idx] if ent_idx < len(parent.output) else {}
            new_entity = payload.output[ent_idx] if ent_idx < len(payload.output) else {}
            for fname, verdict_str in field_verdicts.items():
                try:
                    j = JudgeVerdict(verdict_str)
                except ValueError:
                    continue
                human_fixed = old_entity.get(fname) != new_entity.get(fname)
                await record_human_verdict_pair(
                    session=session,
                    project_id=project_id,
                    judge_model_version="claude-opus-4-7",
                    judge_verdict=j,
                    human_fixed=human_fixed,
                )
```

- [ ] **Step 6: Add a regression test for the wiring**

In `backend/tests/test_calibration_update.py`, append:

```python
import io


@pytest.mark.asyncio
async def test_annotation_save_updates_calibration(client, db_session, tmp_path, monkeypatch):
    monkeypatch.setattr("app.services.storage.settings.storage_root", str(tmp_path))
    await client.post("/api/v1/auth/register", json={"email": "ua@ua.com", "password": "hunter22"})
    tok = (
        await client.post("/api/v1/auth/login", json={"email": "ua@ua.com", "password": "hunter22"})
    ).json()["access_token"]
    h = {"Authorization": f"Bearer {tok}"}
    pid = (await client.post("/api/v1/projects", json={"name": "P"}, headers=h)).json()["id"]
    did = (
        await client.post(
            f"/api/v1/projects/{pid}/documents",
            files=[("files", ("a.pdf", io.BytesIO(b"A"), "application/pdf"))],
            headers=h,
        )
    ).json()[0]["id"]

    # seed a Prediction with a judge-up verdict on shop_name=ABC
    from app.models.prediction import Prediction, PredictionStatus

    pred = Prediction(
        document_id=did,
        model_id="m",
        prompt_hash="h",
        output=[{"shop_name": "ABC"}],
        per_field_confidence={"0": {"shop_name": "up"}},
        status=PredictionStatus.SUCCESS.value,
    )
    db_session.add(pred)
    await db_session.commit()

    # user fixes shop_name → judge was up, human fixed → fp += 1
    await client.post(
        f"/api/v1/projects/{pid}/documents/{did}/annotations",
        json={"output": [{"shop_name": "DEF"}], "parent_prediction_id": pred.id},
        headers=h,
    )

    cal = (
        await db_session.execute(select(JudgeCalibration).where(JudgeCalibration.project_id == pid))
    ).scalar_one()
    assert cal.fp == 1
    assert cal.tp == 0
```

- [ ] **Step 7: Run test to verify it passes**

- [ ] **Step 8: Commit**

```bash
git add backend/app/engine/recompute.py backend/app/api/routes/annotations.py backend/tests/test_calibration_update.py
git commit -m "feat(engine): record (judge,human) verdict pair on correction save"
```

---

## Task 7: Score routes — score, calibration, review queue

**Files:**
- Create: `backend/app/schemas/score.py`
- Create: `backend/app/api/routes/scores.py`
- Modify: `backend/app/api/v1.py` (mount)
- Create: `backend/tests/test_score_routes.py`

Endpoints:
- `GET /api/v1/projects/{pid}/score` → `{ score, judge_component, ce_component, observation_count, vibe_check_size }`
- `GET /api/v1/projects/{pid}/calibration` → `{ tp, fp, fn, tn, point_estimate, ci_low, ci_high, observation_count }`
- `GET /api/v1/projects/{pid}/review-queue` → 3 buckets: required_review, spot_check, all
- `POST /api/v1/projects/{pid}/judge` → triggers `run_judge` for vibe-check predictions; uses provider dep so tests substitute `FakeJudgeProvider`

The `score` endpoint takes a `rerun` callable internally — for the vibe-check / counterexample regression, we use the live `Provider` from R3 by default, but expose a hook so tests inject a fake.

- [ ] **Step 1: Write failing tests**

```python
import io

import pytest


async def _auth_and_project(client) -> tuple[dict, int]:
    await client.post("/api/v1/auth/register", json={"email": "s@s.com", "password": "hunter22"})
    tok = (
        await client.post("/api/v1/auth/login", json={"email": "s@s.com", "password": "hunter22"})
    ).json()["access_token"]
    h = {"Authorization": f"Bearer {tok}"}
    pid = (await client.post("/api/v1/projects", json={"name": "P"}, headers=h)).json()["id"]
    return h, pid


@pytest.mark.asyncio
async def test_get_score_empty_project_is_one(client):
    h, pid = await _auth_and_project(client)
    resp = await client.get(f"/api/v1/projects/{pid}/score", headers=h)
    body = resp.json()
    assert body["score"] == 1.0  # no vibe-check, empty CE pool → trivially 1.0


@pytest.mark.asyncio
async def test_get_calibration_returns_prior_for_empty(client):
    h, pid = await _auth_and_project(client)
    resp = await client.get(f"/api/v1/projects/{pid}/calibration", headers=h)
    body = resp.json()
    assert body["point_estimate"] == pytest.approx(0.80, abs=1e-3)
    assert 0 <= body["ci_low"] <= body["ci_high"] <= 1


@pytest.mark.asyncio
async def test_review_queue_three_buckets(client, db_session, tmp_path, monkeypatch):
    monkeypatch.setattr("app.services.storage.settings.storage_root", str(tmp_path))
    h, pid = await _auth_and_project(client)
    # upload 3 docs, fake-extract them with mixed verdicts
    files = [("files", (f"{n}.pdf", io.BytesIO(b"X"), "application/pdf")) for n in "abc"]
    docs = (
        await client.post(f"/api/v1/projects/{pid}/documents", files=files, headers=h)
    ).json()

    from app.models.prediction import Prediction, PredictionStatus

    for d, conf in zip(
        docs,
        [
            {"0": {"a": "up"}},  # full up → spot-check candidate
            {"0": {"a": "up", "b": "down"}},  # has down → required review
            {"0": {"a": "uncertain"}},  # has uncertain → required review
        ],
    ):
        db_session.add(
            Prediction(
                document_id=d["id"],
                model_id="m",
                prompt_hash="h",
                output=[{"a": 1}],
                per_field_confidence=conf,
                status=PredictionStatus.SUCCESS.value,
            )
        )
    await db_session.commit()

    resp = await client.get(f"/api/v1/projects/{pid}/review-queue", headers=h)
    body = resp.json()
    assert len(body["required_review"]) == 2
    # spot_check is sampled (default 2 from the 👍-only set, but here we have 1)
    assert len(body["spot_check"]) <= 2
    assert {d["id"] for d in body["all"]} >= {d["id"] for d in body["required_review"]}
```

- [ ] **Step 2: Run — expect 404**

- [ ] **Step 3: Implement `app/schemas/score.py`**

```python
from pydantic import BaseModel


class ProjectScoreOut(BaseModel):
    score: float
    judge_component: float
    ce_component: float
    observation_count: int
    vibe_check_size: int


class CalibrationOut(BaseModel):
    tp: int
    fp: int
    fn: int
    tn: int
    point_estimate: float
    ci_low: float
    ci_high: float
    observation_count: int


class ReviewItemOut(BaseModel):
    id: int
    filename: str
    flagged_fields: list[str]


class ReviewQueueOut(BaseModel):
    required_review: list[ReviewItemOut]
    spot_check: list[ReviewItemOut]
    all: list[ReviewItemOut]
```

- [ ] **Step 4: Implement `app/api/routes/scores.py`**

```python
import random

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import current_workspace_id
from app.db import get_session
from app.engine.recompute import recompute_project_score, vibe_check_predictions_query
from app.engine.score import (
    beta_posterior,
    precision_ci_95,
    precision_point_estimate,
)
from app.errors import EmergeError, ErrorCode
from app.models.document import Document
from app.models.judge_calibration import JudgeCalibration
from app.models.prediction import Prediction
from app.models.project import Project
from app.schemas.score import (
    CalibrationOut,
    ProjectScoreOut,
    ReviewItemOut,
    ReviewQueueOut,
)

router = APIRouter(prefix="/projects/{project_id}", tags=["scores"])


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


async def _empty_rerun(_doc_id):
    # placeholder: in production this would call the active provider; in tests it's overridden
    return []


@router.get("/score", response_model=ProjectScoreOut)
async def get_score(
    project_id: int,
    workspace_id: int = Depends(current_workspace_id),
    session: AsyncSession = Depends(get_session),
):
    await _project_or_404(session, project_id, workspace_id)
    result = await recompute_project_score(
        project_id=project_id, session=session, rerun=_empty_rerun
    )
    return ProjectScoreOut(
        score=result.score,
        judge_component=result.judge_component,
        ce_component=result.ce_component,
        observation_count=result.observation_count,
        vibe_check_size=result.vibe_check_size,
    )


@router.get("/calibration", response_model=CalibrationOut)
async def get_calibration(
    project_id: int,
    workspace_id: int = Depends(current_workspace_id),
    session: AsyncSession = Depends(get_session),
):
    await _project_or_404(session, project_id, workspace_id)
    cal = (
        await session.execute(
            select(JudgeCalibration).where(JudgeCalibration.project_id == project_id)
        )
    ).scalar_one_or_none()
    tp, fp, fn, tn = (cal.tp, cal.fp, cal.fn, cal.tn) if cal else (0, 0, 0, 0)
    obs = cal.observation_count if cal else 0
    a, b = beta_posterior(tp=tp, fp=fp)
    point = precision_point_estimate(a, b)
    lo, hi = precision_ci_95(a, b)
    return CalibrationOut(
        tp=tp, fp=fp, fn=fn, tn=tn,
        point_estimate=point, ci_low=lo, ci_high=hi,
        observation_count=obs,
    )


@router.get("/review-queue", response_model=ReviewQueueOut)
async def get_review_queue(
    project_id: int,
    workspace_id: int = Depends(current_workspace_id),
    session: AsyncSession = Depends(get_session),
):
    await _project_or_404(session, project_id, workspace_id)
    doc_ids = (
        await session.execute(vibe_check_predictions_query(project_id))
    ).scalars().all()
    required: list[ReviewItemOut] = []
    up_only: list[ReviewItemOut] = []
    all_items: list[ReviewItemOut] = []
    for did in doc_ids:
        pred = (
            await session.execute(
                select(Prediction)
                .where(Prediction.document_id == did)
                .order_by(Prediction.id.desc())
                .limit(1)
            )
        ).scalar_one()
        doc = (
            await session.execute(select(Document).where(Document.id == did))
        ).scalar_one()
        flagged: list[str] = []
        for fields in (pred.per_field_confidence or {}).values():
            for fname, verdict in fields.items():
                if verdict in ("down", "uncertain"):
                    flagged.append(fname)
        item = ReviewItemOut(
            id=did, filename=doc.filename, flagged_fields=sorted(set(flagged))[:3]
        )
        all_items.append(item)
        if flagged:
            required.append(item)
        else:
            up_only.append(item)
    rng = random.Random(project_id)  # deterministic per project
    spot_check = rng.sample(up_only, k=min(2, len(up_only)))
    return ReviewQueueOut(required_review=required, spot_check=spot_check, all=all_items)
```

- [ ] **Step 5: Mount router**

```python
from app.api.routes import scores

api_v1.include_router(scores.router)
```

- [ ] **Step 6: Run test to verify it passes**

Expected: `3 passed`.

- [ ] **Step 7: Commit**

```bash
git add backend/app/schemas/score.py backend/app/api/routes/scores.py backend/app/api/v1.py backend/tests/test_score_routes.py
git commit -m "feat(api): score / calibration / review-queue endpoints"
```

---

## Task 8: Judge trigger endpoint

**Files:**
- Modify: `backend/app/api/routes/scores.py` (append `POST /judge`)
- Modify: `backend/tests/test_score_routes.py` (append test)

Triggers `run_judge` over all vibe-check predictions. Uses `judge_provider_dep` (a new dep that returns `FakeJudgeProvider` when overridden in tests, real `JudgeProvider` in prod).

- [ ] **Step 1: Add provider dep and tests**

In `app/engine/judge.py`:

```python
def get_judge_provider() -> JudgeProvider:
    """FastAPI dep. Default returns a stub; configure real one in production wiring."""
    raise NotImplementedError("configure judge provider via dependency_overrides or settings")
```

In `app/api/routes/scores.py`, append:

```python
from app.engine.judge import JudgeProvider, get_judge_provider, run_judge


@router.post("/judge")
async def trigger_judge(
    project_id: int,
    workspace_id: int = Depends(current_workspace_id),
    judge: JudgeProvider = Depends(get_judge_provider),
    session: AsyncSession = Depends(get_session),
):
    await _project_or_404(session, project_id, workspace_id)
    doc_ids = (
        await session.execute(vibe_check_predictions_query(project_id))
    ).scalars().all()
    judged: list[int] = []
    for did in doc_ids:
        pred = (
            await session.execute(
                select(Prediction)
                .where(Prediction.document_id == did)
                .order_by(Prediction.id.desc())
                .limit(1)
            )
        ).scalar_one()
        await run_judge(pred.id, session=session, judge=judge)
        judged.append(pred.id)
    return {"judged_predictions": judged}
```

- [ ] **Step 2: Append failing test in `test_score_routes.py`**

```python
@pytest.mark.asyncio
async def test_trigger_judge_writes_per_field_confidence(client, db_session, tmp_path, monkeypatch, app):
    monkeypatch.setattr("app.services.storage.settings.storage_root", str(tmp_path))
    h, pid = await _auth_and_project(client)
    fp = tmp_path / "x.pdf"
    fp.write_bytes(b"X")
    files = [("files", ("a.pdf", io.BytesIO(b"X"), "application/pdf"))]
    did = (
        await client.post(f"/api/v1/projects/{pid}/documents", files=files, headers=h)
    ).json()[0]["id"]

    # seed a prediction (no judge yet)
    from app.models.document import Document as D
    from app.models.prediction import Prediction, PredictionStatus

    d = (await db_session.execute(select(D).where(D.id == did))).scalar_one()
    d.file_path = str(fp)
    pred = Prediction(
        document_id=did,
        model_id="m",
        prompt_hash="h",
        output=[{"a": 1}],
        per_field_confidence={},
        status=PredictionStatus.SUCCESS.value,
    )
    db_session.add(pred)
    await db_session.commit()

    from app.engine.judge import FakeJudgeProvider, get_judge_provider

    fake = FakeJudgeProvider(canned=[{"0": {"a": "up"}}])
    app.dependency_overrides[get_judge_provider] = lambda: fake

    resp = await client.post(f"/api/v1/projects/{pid}/judge", headers=h)
    assert resp.status_code == 200
    await db_session.refresh(pred)
    assert pred.per_field_confidence == {"0": {"a": "up"}}
```

- [ ] **Step 3: Run test to verify it passes**

- [ ] **Step 4: Run full suite**

Run: `cd backend && uv run pytest -v`
Expected: every R1+R2+R3+R4+R5 test passes.

- [ ] **Step 5: Commit**

```bash
git add backend/app/api/routes/scores.py backend/app/engine/judge.py backend/tests/test_score_routes.py
git commit -m "feat(api): judge trigger endpoint over vibe-check predictions"
```

---

## R5 exit criteria

End-to-end:

1. Upload + extract a doc (R3) → `POST /judge` writes `per_field_confidence` for the latest prediction.
2. `GET /score` returns `{score, judge_component, ce_component, observation_count, vibe_check_size}`; the maths matches spec §4.1 for the trivial case.
3. `GET /calibration` shows `point_estimate=0.80` for an empty project (prior).
4. Save a correction that fixes a previously judge=up field → `GET /calibration` shows `fp=1, point_estimate < 0.80`.
5. `GET /review-queue` returns 3 buckets and excludes documents covered by saved Annotations.
6. Adding a counterexample row → re-running `GET /score` weights ce_component into the total via the rerun callable.

Run `cd backend && uv run pytest -v` — all tests R1+R2+R3+R4+R5 pass.

R6 reads `recompute_project_score` and `vibe_check_predictions_query` to drive the AutoResearch Reflexion loop's diagnosis and termination conditions. R7 plumbs the public feedback endpoint to call `save_counterexample` and trigger `recompute_project_score`. R8 surfaces `/score`, `/calibration`, `/review-queue` in the Project page header and Studio sidebar.
