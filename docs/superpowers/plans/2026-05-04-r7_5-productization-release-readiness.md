# R7.5 — Productization & Release Readiness Implementation Plan

> **For Superpowers / Claude Code / Codex:** Implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking and are intentionally plain Markdown so both Claude Code and Codex agents can consume them.
>
> **Required pre-read:** before implementation, read:
> - `CLAUDE.md` — project hard rules and current milestone map
> - `docs/superpowers/specs/2026-05-02-overall-design.md` — updated canonical product/system spec, especially §1.0, §3.1–3.2, §4.5, §7, §8.1, §9, §12

**Goal:** Add the minimal productization layer required before R8 UI: `project_type=extraction`, release-safe public API serving `published_version_id`, contract diff, rollback, and product-facing API Readiness.

**Architecture:** R7 shipped templates, API keys, initial publish, and public `/extract/{api_code}`. The original R7 semantics treated `Project.active_version_id` as the version served by public API. R7.5 changes that without introducing a full Lab/Prod artefact split: `active_version_id` remains the Lab/editor pointer; new `published_version_id` is the public API pointer. Publishing explicitly sets `published_version_id`; editing and AutoResearch never change production by accident. API Readiness wraps the existing score/calibration/review primitives into a product-facing summary.

**Tech Stack:** Existing backend stack only: FastAPI + async SQLAlchemy 2.x + aiosqlite + alembic + pydantic v2 + pytest. No frontend code in this slice.

**Depends on:** R7 implemented in the current repo. Current code paths to inspect first:
- `backend/app/models/project.py`
- `backend/app/schemas/project.py`
- `backend/app/schemas/api_key.py`
- `backend/app/api/routes/publish.py`
- `backend/app/api/routes/public.py`
- `backend/app/api/routes/scores.py`
- `backend/app/engine/extract.py`
- `backend/tests/test_publish_routes.py`
- `backend/tests/test_public_extract.py`

**Non-goals / red lines:**
- Do **not** implement MatchingProject / VerificationProject. Only reserve `Project.project_type = "extraction"` now.
- Do **not** add a full Lab/Prod environment model, deployment workflow, approval workflow, or artefact registry.
- Do **not** add image few-shot, bbox, saved named views, project clone, or model comparison.
- AutoResearch still never promotes automatically. It may create candidate ProjectVersions; humans explicitly activate for Lab and separately publish for API.

---

## File Structure

```text
backend/app/
├── models/
│   ├── project.py                    # add project_type + published_version_id
│   └── prediction.py                 # add optional per_field_evidence JSON
├── schemas/
│   ├── project.py                    # expose project_type + published_version_id
│   ├── api_key.py                    # PublishIn adds project_version_id; RollbackIn
│   ├── feedback.py                   # full + partial feedback request schemas if not already present
│   ├── contract_diff.py              # ContractDiffOut / ContractDiffItem
│   └── readiness.py                  # APIReadinessOut and nested models
├── services/
│   ├── contract_diff.py              # schema snapshot diff rules
│   └── readiness.py                  # build product-facing readiness summary
├── engine/
│   └── extract.py                    # optional project_version_id override
├── api/routes/
│   ├── publish.py                    # publish / rollback / contract-diff endpoints
│   ├── public.py                     # public extract reads published_version_id
│   └── scores.py                     # mount readiness endpoint or delegate to service
└── alembic/versions/
    └── 0014_release_readiness.py      # project_type + published_version_id
```

Tests:

```text
backend/tests/
├── test_project_release_fields.py
├── test_publish_routes.py             # extend existing tests
├── test_public_extract.py             # extend existing tests
├── test_field_evidence.py             # field-level evidence without bbox
├── test_contract_diff.py
├── test_readiness_routes.py
└── test_public_feedback.py            # full + partial feedback contract
```

---

## Task 0: Baseline inspection and current test snapshot

**Objective:** Confirm the current repo state before changing R7 semantics.

**Files:** no code changes.

- [ ] **Step 1: Inspect current code paths**

Run:

```bash
cd backend
uv run pytest tests/test_publish_routes.py tests/test_public_extract.py -v
```

Expected before R7.5: tests pass under old live-active semantics.

- [ ] **Step 2: Record the semantic gap in notes / commit message**

Expected current behavior:
- `Project` has `active_version_id`, `api_code`, `api_published_at`.
- No `published_version_id`.
- `public.py` resolves project by `api_code` and calls `extract_document(...)`.
- `extract_document(...)` uses `project.active_version_id`.

No commit for Task 0 unless files were touched accidentally.

---

## Task 1: Add Project release fields

**Objective:** Add forward-compatible `project_type` and release pointer `published_version_id`.

**Files:**
- Modify: `backend/app/models/project.py`
- Modify: `backend/app/schemas/project.py`
- Create: `backend/alembic/versions/0014_release_readiness.py`
- Create: `backend/tests/test_project_release_fields.py`

### Step 1: Write failing model/schema tests

Add `backend/tests/test_project_release_fields.py`:

```python
import pytest
from pydantic import ValidationError

from app.models.project import Project
from app.schemas.project import ProjectIn, ProjectOut


@pytest.mark.asyncio
async def test_project_defaults_to_extraction_and_unpublished(db_session):
    p = Project(workspace_id=1, name="P", created_by=1)
    db_session.add(p)
    await db_session.flush()

    assert p.project_type == "extraction"
    assert p.published_version_id is None


def test_project_in_accepts_only_extraction():
    assert ProjectIn(name="P").project_type == "extraction"
    assert ProjectIn(name="P", project_type="extraction").project_type == "extraction"
    with pytest.raises(ValidationError):
        ProjectIn(name="P", project_type="matching")


def test_project_out_exposes_release_fields():
    p = Project(
        id=1,
        workspace_id=2,
        name="P",
        created_by=3,
        project_type="extraction",
        active_version_id=10,
        published_version_id=9,
    )
    out = ProjectOut.model_validate(p)
    assert out.project_type == "extraction"
    assert out.active_version_id == 10
    assert out.published_version_id == 9
```

Run:

```bash
uv run pytest tests/test_project_release_fields.py -v
```

Expected: FAIL because fields/schemas do not exist yet.

### Step 2: Implement model fields

In `backend/app/models/project.py`:

```python
project_type: Mapped[str] = mapped_column(
    String(32), nullable=False, default="extraction", server_default="extraction"
)
published_version_id: Mapped[int | None] = mapped_column(nullable=True)
```

Notes:
- Match the current lightweight style of `active_version_id` unless the existing migrations already made it a real FK.
- If adding an FK is straightforward without circular migration trouble, use `ForeignKey("project_versions.id")`; otherwise keep the same style as `active_version_id` and enforce same-project validation in service/route code.

### Step 3: Implement schemas

In `backend/app/schemas/project.py`:

```python
from typing import Literal

class ProjectIn(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    template_id: int | None = None
    project_type: Literal["extraction"] = "extraction"

class ProjectOut(BaseModel):
    ...
    project_type: str = "extraction"
    published_version_id: int | None = None
```

### Step 4: Add migration

Create `backend/alembic/versions/0014_release_readiness.py` with upgrade/downgrade:

- Add `projects.project_type` string column, non-null, default `extraction`.
- Add `projects.published_version_id` nullable integer column.
- Add `predictions.per_field_evidence` nullable JSON column if the existing `Prediction` model does not already have an equivalent field-level evidence store. This stores page / quote / rationale only; no bbox, coordinates, or visual regions.
- SQLite-compatible migration required.

Run:

```bash
uv run alembic upgrade head
uv run pytest tests/test_project_release_fields.py -v
```

Expected: PASS.

### Step 5: Commit

```bash
git add backend/app/models/project.py backend/app/schemas/project.py backend/alembic/versions/0014_release_readiness.py backend/tests/test_project_release_fields.py
git commit -m "feat(backend): add project type and published version pointer"
```

---

## Task 2: Change publish semantics to set published_version_id

**Objective:** Publishing explicitly selects the ProjectVersion served by public API.

**Files:**
- Modify: `backend/app/schemas/api_key.py`
- Modify: `backend/app/api/routes/publish.py`
- Modify: `backend/tests/test_publish_routes.py`

### Step 1: Write failing route tests

Extend `backend/tests/test_publish_routes.py` with cases:

```python
@pytest.mark.asyncio
async def test_publish_sets_published_version_to_active_by_default(client, auth_headers, locked_project_version):
    project, version = locked_project_version
    res = await client.post(
        f"/api/v1/projects/{project.id}/publish",
        json={"api_code": "japan-receipts"},
        headers=auth_headers,
    )
    assert res.status_code == 200
    body = res.json()
    assert body["published_version_id"] == version.id
    assert body["active_version_id"] == version.id
    assert body["api_code"] == "japan-receipts"
    assert body["api_published_at"] is not None


@pytest.mark.asyncio
async def test_publish_can_target_locked_non_active_version(client, auth_headers, project_with_two_versions):
    project, old_locked, new_active = project_with_two_versions
    res = await client.post(
        f"/api/v1/projects/{project.id}/publish",
        json={"api_code": "japan-receipts", "project_version_id": old_locked.id},
        headers=auth_headers,
    )
    assert res.status_code == 200
    body = res.json()
    assert body["active_version_id"] == new_active.id
    assert body["published_version_id"] == old_locked.id


@pytest.mark.asyncio
async def test_publish_rejects_unlocked_target_version(client, auth_headers, project_with_unlocked_version):
    project, unlocked = project_with_unlocked_version
    res = await client.post(
        f"/api/v1/projects/{project.id}/publish",
        json={"api_code": "japan-receipts", "project_version_id": unlocked.id},
        headers=auth_headers,
    )
    assert res.status_code == 409
```

Use existing fixtures where possible; if fixtures do not exist, create small local helpers inside the test file following current test style.

Run:

```bash
uv run pytest tests/test_publish_routes.py -v
```

Expected: FAIL.

### Step 2: Update schemas

In `backend/app/schemas/api_key.py`:

```python
class PublishIn(BaseModel):
    api_code: str
    project_version_id: int | None = None
    ...

class RollbackIn(BaseModel):
    project_version_id: int
```

### Step 3: Update publish route

In `backend/app/api/routes/publish.py`:

- Resolve project as today.
- Determine target version:
  - `target_id = payload.project_version_id or p.active_version_id`
  - if missing: 409 `Project has no active version.`
- Load `ProjectVersion` by target id.
- Validate `v.project_id == p.id`.
- Validate `v.locked`.
- Validate `api_code` uniqueness as today.
- Set:

```python
p.api_code = payload.api_code
p.published_version_id = v.id
p.api_published_at = datetime.now(tz=timezone.utc)
```

Return `ProjectOut`.

### Step 4: Add rollback endpoint

Add:

```text
POST /api/v1/projects/{project_id}/rollback
body: { project_version_id }
```

Rules:
- Project must be published (`api_published_at is not None`) or return 409.
- Target version must belong to project.
- Target version must be locked.
- Set only `published_version_id`; do not change `active_version_id`.
- Return `ProjectOut`.

Add tests:

```python
@pytest.mark.asyncio
async def test_rollback_changes_published_not_active(client, auth_headers, published_project_with_two_versions):
    project, old_locked, new_active = published_project_with_two_versions
    res = await client.post(
        f"/api/v1/projects/{project.id}/rollback",
        json={"project_version_id": old_locked.id},
        headers=auth_headers,
    )
    assert res.status_code == 200
    body = res.json()
    assert body["published_version_id"] == old_locked.id
    assert body["active_version_id"] == new_active.id
```

### Step 5: Run tests

```bash
uv run pytest tests/test_publish_routes.py tests/test_project_release_fields.py -v
```

Expected: PASS.

### Step 6: Commit

```bash
git add backend/app/schemas/api_key.py backend/app/api/routes/publish.py backend/tests/test_publish_routes.py
git commit -m "feat(api): publish explicit project version with rollback"
```

---

## Task 3: Public extract must serve published_version_id

**Objective:** Public API uses the published version even when Lab active version changes.

**Files:**
- Modify: `backend/app/engine/extract.py`
- Modify: `backend/app/api/routes/public.py`
- Modify: `backend/tests/test_public_extract.py`

### Step 1: Write failing public API tests

Add / extend tests:

```python
@pytest.mark.asyncio
async def test_public_extract_uses_published_version_not_active(
    client, db_session, provider_fake, published_project_with_two_versions_and_key
):
    project, published_version, active_version, api_key = published_project_with_two_versions_and_key
    assert project.published_version_id == published_version.id
    assert project.active_version_id == active_version.id

    res = await client.post(
        f"/extract/{project.api_code}",
        headers={"X-Api-Key": api_key},
        files={"file": ("receipt.pdf", b"fake", "application/pdf")},
    )
    assert res.status_code == 200
    assert res.json()["project_version"] == published_version.id


@pytest.mark.asyncio
async def test_public_extract_forbidden_when_published_pointer_missing(client, published_project_without_pointer):
    project, api_key = published_project_without_pointer
    res = await client.post(
        f"/extract/{project.api_code}",
        headers={"X-Api-Key": api_key},
        files={"file": ("receipt.pdf", b"fake", "application/pdf")},
    )
    assert res.status_code == 403
```

Run:

```bash
uv run pytest tests/test_public_extract.py -v
```

Expected: FAIL under old active-version behavior.

### Step 2: Add version override to extraction engine

In `backend/app/engine/extract.py`, change signature:

```python
async def extract_document(
    document_id: int,
    *,
    session: AsyncSession,
    provider: Provider,
    project_version_id: int | None = None,
) -> Prediction:
```

Version resolution:

```python
version_id = project_version_id or p.active_version_id
if version_id is None:
    raise ValueError(f"project {p.id} has no active version")
v = (await session.execute(select(ProjectVersion).where(ProjectVersion.id == version_id))).scalar_one()
if v.project_id != p.id:
    raise ValueError(f"version {v.id} does not belong to project {p.id}")
```

Internal extraction callers omit `project_version_id` and keep using active Lab version.

### Step 3: Update public route

In `backend/app/api/routes/public.py`:

- `_resolve_project` should require both:
  - `api_published_at is not None`
  - `published_version_id is not None`
- Public extract calls:

```python
pred = await extract_document(
    doc.id,
    session=session,
    provider=provider,
    project_version_id=project.published_version_id,
)
```

Return `project_version=pred.project_version_id`.

### Step 4: Run tests

```bash
uv run pytest tests/test_public_extract.py tests/test_publish_routes.py -v
```

Expected: PASS.

### Step 5: Commit

```bash
git add backend/app/engine/extract.py backend/app/api/routes/public.py backend/tests/test_public_extract.py
git commit -m "feat(api): serve public extraction from published version"
```

---

## Task 3.5: Field-level evidence foundation

**Objective:** Store field-level evidence so Review Inbox / Description Workbench can explain why a field value was produced without adding bbox annotation.

**Files:**
- Modify: `backend/app/models/prediction.py`
- Modify: `backend/app/engine/extract.py`
- Modify: `backend/alembic/versions/0014_release_readiness.py` if Task 1 has not been committed yet; otherwise create the next migration
- Create: `backend/tests/test_field_evidence.py`

### Step 1: Write failing tests

Create `backend/tests/test_field_evidence.py`:

```python
import pytest

from app.models.prediction import Prediction


@pytest.mark.asyncio
async def test_prediction_can_store_field_level_evidence(db_session):
    p = Prediction(
        document_id=1,
        project_version_id=2,
        model_id="test-model",
        prompt_hash="abc",
        output=[{"total": 1234}],
        per_field_confidence={"0": {"total": "up"}},
        per_field_evidence={
            "0": {
                "total": {
                    "page": 1,
                    "quote": "Total ¥1,234",
                    "rationale": "Used the tax-included total line",
                }
            }
        },
        status="success",
    )
    db_session.add(p)
    await db_session.flush()
    await db_session.refresh(p)

    assert p.per_field_evidence["0"]["total"]["quote"] == "Total ¥1,234"
```

Run:

```bash
uv run pytest tests/test_field_evidence.py -v
```

Expected: FAIL if `per_field_evidence` does not exist yet.

### Step 2: Implement storage

In `backend/app/models/prediction.py`, add nullable JSON storage matching project conventions:

```python
per_field_evidence: Mapped[dict | None] = mapped_column(JSON, nullable=True)
```

Evidence shape:

```json
{
  "0": {
    "total": {
      "page": 1,
      "quote": "Total ¥1,234",
      "rationale": "Used the tax-included total line",
      "source_text_hash": "optional"
    }
  }
}
```

Rules:
- Store page / quote / rationale / optional source text hash.
- Do **not** store bbox, coordinates, polygons, visual regions, or OCR spans.
- If the provider does not return evidence yet, default to `{}` or `None`; do not block extraction.

### Step 3: Thread evidence through extraction if available

In `backend/app/engine/extract.py`, when provider output includes field evidence, persist it into `Prediction.per_field_evidence`. If provider output does not include it, keep `None`.

Do not invent fake quotes. Field-level evidence should be model-provided or derived from existing text/OCR cache only when available.

### Step 4: Run tests

```bash
uv run pytest tests/test_field_evidence.py tests/test_public_extract.py -v
```

Expected: PASS.

### Step 5: Commit

```bash
git add backend/app/models/prediction.py backend/app/engine/extract.py backend/alembic/versions backend/tests/test_field_evidence.py
git commit -m "feat(backend): store field-level extraction evidence"
```

---

## Task 4: Contract diff service and endpoint

**Objective:** Provide a backend contract diff for API Console before activating a version.

**Files:**
- Create: `backend/app/schemas/contract_diff.py`
- Create: `backend/app/services/contract_diff.py`
- Modify: `backend/app/api/routes/publish.py`
- Create: `backend/tests/test_contract_diff.py`

### Step 1: Write failing service tests

Create `backend/tests/test_contract_diff.py`:

```python
from app.services.contract_diff import diff_schema_snapshots


def test_contract_diff_detects_removed_field_as_breaking():
    old = [{"name": "total_amount", "type": "number", "required": True, "description": "total"}]
    new = []
    out = diff_schema_snapshots(old, new)
    assert any(i.kind == "field_removed" and i.severity == "breaking" for i in out.items)


def test_contract_diff_detects_optional_field_added_as_non_breaking():
    old = []
    new = [{"name": "currency", "type": "string", "required": False, "description": "ISO code"}]
    out = diff_schema_snapshots(old, new)
    assert any(i.kind == "optional_field_added" and i.severity == "non_breaking" for i in out.items)


def test_contract_diff_detects_type_change_as_breaking():
    old = [{"name": "date", "type": "string", "required": True, "description": "date"}]
    new = [{"name": "date", "type": "date", "required": True, "description": "date"}]
    out = diff_schema_snapshots(old, new)
    assert any(i.kind == "type_changed" and i.severity == "breaking" for i in out.items)


def test_contract_diff_detects_enum_narrowing_as_breaking():
    old = [{"name": "currency", "type": "string", "required": True, "description": "", "enum": ["JPY", "USD", "EUR"]}]
    new = [{"name": "currency", "type": "string", "required": True, "description": "", "enum": ["JPY", "USD"]}]
    out = diff_schema_snapshots(old, new)
    assert any(i.kind == "enum_narrowed" and i.severity == "breaking" for i in out.items)
```

Run:

```bash
uv run pytest tests/test_contract_diff.py -v
```

Expected: FAIL.

### Step 2: Implement schemas

`backend/app/schemas/contract_diff.py`:

```python
from typing import Any, Literal
from pydantic import BaseModel


class ContractDiffItem(BaseModel):
    kind: str
    severity: Literal["breaking", "non_breaking"]
    field_name: str | None = None
    before: Any = None
    after: Any = None
    message: str


class ContractDiffOut(BaseModel):
    from_version_id: int | None = None
    to_version_id: int | None = None
    has_breaking_changes: bool
    items: list[ContractDiffItem]
```

### Step 3: Implement service

`backend/app/services/contract_diff.py`:

- Build `old_by_name` and `new_by_name` from schema snapshot lists.
- Compare by field `name`.
- Rules:
  - removed field → `field_removed`, breaking
  - added required field → `required_field_added`, breaking
  - added optional field → `optional_field_added`, non_breaking
  - type changed → `type_changed`, breaking
  - required false→true → `required_tightened`, breaking
  - required true→false → `required_loosened`, non_breaking
  - enum narrowed → `enum_narrowed`, breaking
  - enum widened → `enum_widened`, non_breaking
  - description/global text-only changes are non-breaking only if represented at field level; global_notes diff can be handled in endpoint or ignored for v1.

### Step 4: Add endpoint

In `backend/app/api/routes/publish.py` add:

```text
GET /api/v1/projects/{project_id}/contract-diff?from_version_id=<id>&to_version_id=<id>
```

Rules:
- Both versions must belong to project.
- If `from_version_id` omitted, default to `project.published_version_id`.
- If `to_version_id` omitted, default to `project.active_version_id`.
- If `from_version_id` is still missing because project has never published, return diff from empty schema to target.
- Return `ContractDiffOut`.

Add route tests for default behavior.

### Step 5: Run tests

```bash
uv run pytest tests/test_contract_diff.py tests/test_publish_routes.py -v
```

Expected: PASS.

### Step 6: Commit

```bash
git add backend/app/schemas/contract_diff.py backend/app/services/contract_diff.py backend/app/api/routes/publish.py backend/tests/test_contract_diff.py backend/tests/test_publish_routes.py
git commit -m "feat(api): add project version contract diff"
```

---

## Task 5: API Readiness endpoint

**Objective:** Expose product-facing readiness without presenting empty counterexamples as 100% certainty.

**Files:**
- Create: `backend/app/schemas/readiness.py`
- Create: `backend/app/services/readiness.py`
- Modify: `backend/app/api/routes/scores.py`
- Create: `backend/tests/test_readiness_routes.py`

### Step 1: Write failing tests

Create tests for three product-critical cases:

```python
@pytest.mark.asyncio
async def test_readiness_reports_no_production_feedback_not_100_percent(client, auth_headers, project_without_counterexamples):
    project = project_without_counterexamples
    res = await client.get(f"/api/v1/projects/{project.id}/readiness", headers=auth_headers)
    assert res.status_code == 200
    body = res.json()
    assert body["regression_health"]["counterexamples_total"] == 0
    assert body["regression_health"]["status"] == "no_production_feedback"
    assert "no_production_feedback" in body["warnings"]


@pytest.mark.asyncio
async def test_readiness_counts_human_review_coverage(client, auth_headers, project_with_saved_annotations):
    project = project_with_saved_annotations
    res = await client.get(f"/api/v1/projects/{project.id}/readiness", headers=auth_headers)
    assert res.status_code == 200
    coverage = res.json()["evidence_coverage"]
    assert coverage["reviewed_docs"] >= 1
    assert coverage["reviewed_entities"] >= 1
    assert coverage["reviewed_fields"] >= 1


@pytest.mark.asyncio
async def test_readiness_blocks_publish_without_active_version(client, auth_headers, project_without_active_version):
    project = project_without_active_version
    res = await client.get(f"/api/v1/projects/{project.id}/readiness", headers=auth_headers)
    assert res.status_code == 200
    assert "no_active_version" in res.json()["publish_blockers"]
```

Run:

```bash
uv run pytest tests/test_readiness_routes.py -v
```

Expected: FAIL.

### Step 2: Define schemas

`backend/app/schemas/readiness.py`:

```python
from pydantic import BaseModel


class QualityEstimateOut(BaseModel):
    score: float
    judge_component: float
    judge_precision: float
    ci_low: float
    ci_high: float
    observation_count: int
    vibe_check_size: int


class EvidenceCoverageOut(BaseModel):
    reviewed_docs: int
    reviewed_entities: int
    reviewed_fields: int
    field_evidence_fields: int
    field_evidence_coverage_ratio: float


class SchemaMaturityOut(BaseModel):
    status: str  # draft | stabilizing | lock_candidate | locked
    reviewed_docs: int
    reviewed_entities: int
    recent_schema_breaking_changes: int
    message: str


class RegressionHealthOut(BaseModel):
    counterexamples_total: int
    counterexample_component: float | None
    status: str  # no_production_feedback | passing | failing | unknown


class RiskyFieldOut(BaseModel):
    field_name: str
    count: int


class APIReadinessOut(BaseModel):
    quality_estimate: QualityEstimateOut
    evidence_coverage: EvidenceCoverageOut
    schema_maturity: SchemaMaturityOut
    regression_health: RegressionHealthOut
    risky_fields: list[RiskyFieldOut]
    publish_blockers: list[str]
    warnings: list[str]
```

### Step 3: Implement service

`backend/app/services/readiness.py` should:

- Reuse `recompute_project_score(...)` from `app.engine.recompute`.
- Reuse calibration helpers from `app.engine.score`.
- Count human-reviewed annotations:
  - `Annotation.role == "none"`
  - `Annotation.status == "saved"`
  - distinct document ids → `reviewed_docs`
  - sum `len(annotation.output)` → `reviewed_entities`
  - count scalar fields recursively in `annotation.output` → `reviewed_fields`
  - count fields with `Prediction.per_field_evidence` when available → `field_evidence_fields` and `field_evidence_coverage_ratio`
- Compute schema maturity:
  - `draft` if reviewed docs < 2 or reviewed fields are sparse
  - `stabilizing` if reviewed docs/entities are growing but recent corrections still introduce schema-breaking changes
  - `lock_candidate` only when reviewed docs >= 3, reviewed entities >= 10, recent schema-breaking changes are 0, and field evidence coverage is not empty
  - `locked` only when the ProjectVersion is explicitly locked
  - Do not unlock publish from a naive "2 docs look similar" heuristic
- Count counterexamples:
  - `Annotation.role == "counterexample"`
  - `Annotation.status == "saved"`
- Risky fields:
  - latest vibe-check predictions
  - any `per_field_confidence` verdict in `down` / `uncertain`
  - sort by count desc, cap 10
- Publish blockers:
  - `no_active_version` if project has no active version
  - `active_version_unlocked` if active version exists but `locked` is false
  - `empty_schema` if active version schema snapshot is empty
  - `schema_not_lock_candidate` if schema maturity is still `draft` and user is trying to publish to production
- Warnings:
  - `no_production_feedback` if counterexamples total = 0
  - `low_evidence` if reviewed docs < 3 or observation count < 10
  - `low_field_evidence` if field-level evidence coverage is empty or very low
  - `schema_still_stabilizing` if maturity is `draft` or `stabilizing`
  - `risky_fields_present` if risky fields non-empty

Important product rule:
- If counterexamples total = 0, `regression_health.status = "no_production_feedback"` and `counterexample_component = None` or keep raw component separately. Do **not** present it as passing.

### Step 4: Add route

In `backend/app/api/routes/scores.py` add:

```text
GET /api/v1/projects/{project_id}/readiness
```

It should call the readiness service and return `APIReadinessOut`.

### Step 5: Run tests

```bash
uv run pytest tests/test_readiness_routes.py tests/test_score_routes.py tests/test_calibration_beta.py -v
```

Expected: PASS.

### Step 6: Commit

```bash
git add backend/app/schemas/readiness.py backend/app/services/readiness.py backend/app/api/routes/scores.py backend/tests/test_readiness_routes.py
git commit -m "feat(api): add API readiness summary"
```

---

## Task 5.5: Partial production feedback contract

**Objective:** Let API consumers submit small field-level corrections instead of forcing them to resend a full `correct_output` blob.

**Files:**
- Create/modify: `backend/app/schemas/feedback.py` or existing public-route schemas
- Modify: `backend/app/api/routes/public.py`
- Create/modify: `backend/tests/test_public_feedback.py`

### Step 1: Write failing tests

Add tests for both accepted feedback shapes:

```python
@pytest.mark.asyncio
async def test_public_feedback_accepts_partial_field_corrections(client, published_project_with_prediction_and_key):
    project, prediction, api_key = published_project_with_prediction_and_key
    res = await client.post(
        f"/extract/{project.api_code}/feedback",
        headers={"X-Api-Key": api_key},
        json={
            "request_id": prediction.id,
            "corrections": [
                {
                    "entity_index": 0,
                    "field_path": "total",
                    "correct_value": 1234,
                    "comment": "model picked subtotal",
                }
            ],
        },
    )
    assert res.status_code in (200, 201)
    assert res.json()["status"] in ("accepted", "created")


@pytest.mark.asyncio
async def test_public_feedback_still_accepts_full_correct_output(client, published_project_with_prediction_and_key):
    project, prediction, api_key = published_project_with_prediction_and_key
    res = await client.post(
        f"/extract/{project.api_code}/feedback",
        headers={"X-Api-Key": api_key},
        json={"request_id": prediction.id, "correct_output": [{"total": 1234}]},
    )
    assert res.status_code in (200, 201)
```

Run:

```bash
uv run pytest tests/test_public_feedback.py -v
```

Expected: FAIL until schemas/route accept partial corrections.

### Step 2: Define feedback schemas

```python
from typing import Any
from pydantic import BaseModel, model_validator


class FeedbackCorrectionIn(BaseModel):
    entity_index: int = 0
    field_path: str
    correct_value: Any
    comment: str | None = None


class FeedbackIn(BaseModel):
    request_id: int
    correct_output: Any | None = None
    corrections: list[FeedbackCorrectionIn] | None = None

    @model_validator(mode="after")
    def require_full_or_partial(self):
        if self.correct_output is None and not self.corrections:
            raise ValueError("feedback requires correct_output or corrections")
        return self
```

### Step 3: Implement route behavior

In `POST /extract/{api_code}/feedback`:
- Keep existing full-output behavior.
- For partial corrections:
  - load the referenced `Prediction.output`;
  - apply corrections by `entity_index + field_path` to produce a merged corrected output;
  - store a counterexample / annotation using the merged output;
  - also preserve the raw corrections in metadata if the current model supports metadata JSON.
- Validate `request_id` belongs to the same project/api_code.
- Do not require clients to know full internal schema.

### Step 4: Run tests

```bash
uv run pytest tests/test_public_feedback.py tests/test_public_extract.py tests/test_readiness_routes.py -v
```

Expected: PASS.

### Step 5: Commit

```bash
git add backend/app/schemas/feedback.py backend/app/api/routes/public.py backend/tests/test_public_feedback.py
git commit -m "feat(api): accept partial extraction feedback"
```

---

## Task 6: Update public API and publish tests for old semantics removal

**Objective:** Ensure no test or code path still assumes public API live-reads `active_version_id`.

**Files:**
- Search/modify tests under `backend/tests/`
- Optional: update route docstrings/comments in `backend/app/api/routes/public.py`

### Step 1: Search for stale language

Use ripgrep or Hermes search equivalent:

```bash
cd ..
rg "active_version_id.*public|public.*active_version|live read|version-pin|published API reads" backend docs CLAUDE.md
```

Expected: only historical plan references or explicitly superseded R7 plan. Runtime code and CLAUDE.md must not say public reads active.

### Step 2: Update tests/comments

- Any public API test expecting active-version behavior must be rewritten to published-version behavior.
- Comments in `public.py` should say public resolves project by api_code and serves `published_version_id`.

### Step 3: Run focused backend tests

```bash
cd backend
uv run pytest \
  tests/test_project_release_fields.py \
  tests/test_publish_routes.py \
  tests/test_public_extract.py \
  tests/test_field_evidence.py \
  tests/test_contract_diff.py \
  tests/test_readiness_routes.py \
  tests/test_public_feedback.py \
  -v
```

Expected: PASS.

### Step 4: Commit

```bash
git add backend tests CLAUDE.md docs/superpowers/specs/2026-05-02-overall-design.md docs/superpowers/plans/2026-05-04-r7_5-productization-release-readiness.md
git commit -m "docs: align release readiness semantics"
```

If docs were already committed separately, commit only changed code/tests.

---

## Task 7: Full backend verification

**Objective:** Verify R7.5 did not regress R1–R7.

**Files:** no planned code changes.

### Step 1: Run migrations from scratch if practical

```bash
cd backend
rm -f data/test-emerge.db
uv run alembic upgrade head
```

If the project uses test DB fixtures instead of this file, follow existing test setup and do not delete non-test data.

### Step 2: Run full backend tests

```bash
uv run pytest -v
```

Expected: PASS.

### Step 3: Manual smoke checklist

Using tests or local server, verify:

- Create project → `project_type == "extraction"`.
- Publish locked version A → public extract returns `project_version == A`.
- Activate version B in Lab → public extract still returns A.
- Publish / activate B for API → public extract returns B.
- Rollback to A → public extract returns A.
- Readiness with no counterexamples warns `no_production_feedback`.
- Readiness exposes schema maturity and does not treat a naive two-document match as publish-ready.
- Prediction can store field-level evidence with page / quote / rationale and no bbox coordinates.
- Public feedback accepts both full `correct_output` and partial `corrections`.
- Contract diff flags deleted/type-changed/required-tightened fields as breaking.

### Step 4: Commit final verification changes if any

```bash
git status --short
git add <changed-files>
git commit -m "test: verify release readiness flow"
```

Only commit if files changed.

---

## Handoff notes for R8

R8 must consume the new R7.5 semantics and the updated overall spec. Do not carry forward the older extraction-only / confidence-badge UX.

R8 product requirements:

- **Onboarding = Docs + NL hybrid**, not NL-first:
  - user uploads/chooses sample documents first;
  - optional NL goal text explains what API should return;
  - system proposes fields from docs + NL, then asks user to confirm/edit.
- Project page is not just Data Manager. It must include **Review Inbox**:
  - risky fields;
  - low evidence fields;
  - production feedback items;
  - suggested next review actions.
- Project page header should display **API Readiness**, not a naked confidence score.
- Publish UI should become **API Console**:
  - current `published_version_id`
  - current Lab `active_version_id`
  - readiness summary
  - contract diff before Activate for API
  - rollback / unpublish controls
  - API key management
  - snippets / feedback example
- Project creation should expose project type architecture but only enable Extract API:
  - Extract fields from documents — enabled
  - Match documents against each other — disabled / future
  - Verify documents against rules — disabled / future
- Studio correction flow should support **edit-and-teach** inline proposals: when the user corrects a field, suggest a description/rule update and show which future extractions it affects.
- Every editable field should expose field-level evidence from R7.5 when available: page, quote, rationale; still no bbox UI in v1.
- Schema editor should become a **Description Workbench** with IDE-grade assistance:
  - lint weak descriptions;
  - show missing examples / enum drift / contradictions;
  - run a field description against sample docs;
  - preview schema/version diff before saving.
- Public feedback UX should show partial feedback examples, not only full `correct_output` replacement.
- Terminology should be productized:
  - use API Readiness / Review Inbox / API Console / Description Workbench;
  - avoid exposing internal terms such as confidence unlock, labeling queue, schema heuristic, active-live API, or raw JSON manager.
- If backend support is not fully present, R8 may represent correction-to-teaching as a proposal panel backed by existing schema edit/version APIs.

## Why this is a new plan, not a rewrite of R7

R7 is already implemented or partially implemented in the current repo. Rewriting the old R7 plan would make history ambiguous and confuse Claude Code about what exists. R7.5 is intentionally a **post-R7 semantic correction**: it preserves R7 assets and adds the product safety layer before UI work hardens the old behavior.
