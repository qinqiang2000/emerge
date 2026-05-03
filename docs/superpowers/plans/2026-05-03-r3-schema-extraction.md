# R3 — Schema & Extraction Core Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stand up the **single non-negotiable feature loop** of emerge: a user uploads documents, the platform runs zero-shot extraction with `responseSchema` enforcement, stores predictions, and offers a lock workflow once corrections stabilise the schema. After R3 a user can: upload PDFs → see structured JSON come back → edit JSON → derive a candidate schema → lock it → re-extract.

**Architecture:**
- `ProjectVersion` is the immutable snapshot of `(schema, global_notes, model_id, counterexample_ids)`. Every Project has at least one `ProjectVersion` (initial empty version created at Project creation, retroactively for R2 projects via a backfill).
- `SchemaField` is a pydantic model — single source of truth for field shape; round-trips to/from `ProjectVersion.schema_snapshot` JSON column.
- **Prompt composition is pure**: `compose_extraction_prompt(version) -> ChatRequest` is a deterministic function with no LLM call inside; testable without network.
- **Provider abstraction**: a `Provider` protocol (`extract(image_or_pdf_bytes, response_schema, system, user) -> ExtractionResult`). `OpenAIProvider` and `GeminiProvider` implement it. Tests use a `FakeProvider` that returns canned JSON.
- **Batch extraction** runs as `asyncio.gather(...)` of per-document tasks behind a single API call; v1 is in-process, no Celery (spec §13.5 — task queue decision: in-process for batches ≤ 50). SSE delivers per-document progress.
- **Schema auto-derivation**: when ≥ 2 saved Annotations exist, `derive_schema_candidate(annotations)` produces a `list[SchemaField]` whose `description` is a generic placeholder; the user fills in real descriptions.
- **No few-shot, ever**: `compose_extraction_prompt` has no path that injects example image / output pairs into the prompt. Spec §1, §10.

**Tech Stack:** R1+R2 stack, plus `openai>=1.50.0` and `google-genai>=0.3.0` SDKs (matching doc-intel-legacy). Adds `PyPDF2` for page count.

**Spec sections covered:** §1 (conceptual model), §1.2 (output contract), §2.2 (main loop step 2/3/5), §2.3 (lock heuristic), §3.1 (ProjectVersion table), §3.2 (invariants — at least one version per project; append-only), §10 (zero-shot batch via SSE).

**Depends on:** R2 (Project, Document, Prediction, Annotation tables exist).

---

## File Structure

```
backend/app/
├── models/
│   └── project_version.py         # ProjectVersion table
├── schemas/
│   ├── schema_field.py            # SchemaField (pydantic); shared by R3+R6
│   ├── project_version.py         # ProjectVersionOut, ExtractRequest
│   └── extraction.py              # ExtractionResult dataclass for providers
├── engine/
│   ├── __init__.py
│   ├── system_frame.py            # SYSTEM_FRAME constant (~150 tokens)
│   ├── prompt.py                  # compose_extraction_prompt(version) -> ChatRequest
│   ├── response_schema.py         # build_response_schema(fields) -> dict (JSON Schema)
│   ├── provider.py                # Provider protocol + ExtractionRequest dataclass
│   ├── providers/
│   │   ├── __init__.py
│   │   ├── openai_provider.py
│   │   ├── gemini_provider.py
│   │   └── fake.py                # FakeProvider for tests
│   ├── extract.py                 # extract_document(...) writes Prediction
│   └── derive_schema.py           # derive_schema_candidate(annotations) -> list[SchemaField]
├── services/
│   └── pdf.py                     # count_pdf_pages(file_path) -> int
├── api/routes/
│   ├── versions.py                # GET active version, PATCH schema, POST lock
│   └── extraction.py              # POST /projects/{id}/extract (batch + SSE)
└── alembic/versions/
    ├── 0007_project_version.py    # ProjectVersion table + FK Project.active_version_id
    └── 0008_prediction_version_fk.py  # tighten Prediction.project_version_id FK
```

Tests:

```
backend/tests/
├── test_schema_field.py
├── test_response_schema.py
├── test_prompt_composer.py
├── test_project_version_model.py
├── test_provider_fake.py
├── test_extract_document.py
├── test_derive_schema.py
├── test_lock_workflow.py
├── test_extraction_routes.py
└── test_pdf_pages.py
```

---

## Task 1: SchemaField pydantic model

**Files:**
- Create: `backend/app/schemas/schema_field.py`
- Create: `backend/tests/test_schema_field.py`

`SchemaField` is the single source of truth for schema shape across the codebase. R6 and R8 both consume it; immutable JSON shape so cross-version diffs are clean.

- [ ] **Step 1: Write the failing test**

```python
import pytest
from pydantic import ValidationError

from app.schemas.schema_field import FieldType, SchemaField


def test_basic_string_field():
    f = SchemaField(name="shop_name", type=FieldType.STRING, required=True, description="店名")
    assert f.name == "shop_name"
    assert f.examples == []


def test_array_field_must_have_child_fields():
    with pytest.raises(ValidationError):
        SchemaField(name="line_items", type=FieldType.ARRAY, description="x")


def test_array_field_with_children_ok():
    f = SchemaField(
        name="line_items",
        type=FieldType.ARRAY,
        description="x",
        child_fields=[SchemaField(name="qty", type=FieldType.NUMBER, description="quantity")],
    )
    assert f.child_fields[0].name == "qty"


def test_field_name_must_be_snake_case():
    with pytest.raises(ValidationError):
        SchemaField(name="ShopName", type=FieldType.STRING, description="bad")
    with pytest.raises(ValidationError):
        SchemaField(name="shop-name", type=FieldType.STRING, description="bad")


def test_enum_only_for_string():
    with pytest.raises(ValidationError):
        SchemaField(
            name="amount", type=FieldType.NUMBER, description="d", enum=["a", "b"]
        )
```

- [ ] **Step 2: Run — expect ImportError**

- [ ] **Step 3: Implement `app/schemas/schema_field.py`**

```python
import re
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, model_validator

_SNAKE = re.compile(r"^[a-z][a-z0-9_]*$")


class FieldType(str, Enum):
    STRING = "string"
    NUMBER = "number"
    INTEGER = "integer"
    BOOLEAN = "boolean"
    ARRAY = "array"  # array<object>; uses child_fields


class SchemaField(BaseModel):
    name: str
    type: FieldType
    required: bool = True
    description: str
    examples: list[str] = Field(default_factory=list)
    enum: list[str] | None = None
    child_fields: list["SchemaField"] = Field(default_factory=list)

    @model_validator(mode="after")
    def _validate(self) -> "SchemaField":
        if not _SNAKE.match(self.name):
            raise ValueError(
                f"name '{self.name}' must be snake_case ASCII (lowercase letters, digits, underscores)"
            )
        if self.type is FieldType.ARRAY and not self.child_fields:
            raise ValueError(f"array field '{self.name}' must declare child_fields")
        if self.type is not FieldType.ARRAY and self.child_fields:
            raise ValueError(f"non-array field '{self.name}' cannot have child_fields")
        if self.enum is not None and self.type is not FieldType.STRING:
            raise ValueError(f"enum is only allowed on string fields ('{self.name}')")
        return self


SchemaField.model_rebuild()
```

- [ ] **Step 4: Run test to verify it passes**

Expected: `5 passed`.

- [ ] **Step 5: Commit**

```bash
git add backend/app/schemas/schema_field.py backend/tests/test_schema_field.py
git commit -m "feat(backend): add SchemaField pydantic model with snake_case + enum validation"
```

---

## Task 2: ProjectVersion model + migration

**Files:**
- Create: `backend/app/models/project_version.py`
- Modify: `backend/app/models/__init__.py`
- Create: `backend/alembic/versions/0007_project_version.py`
- Create: `backend/tests/test_project_version_model.py`

This migration also tightens `Project.active_version_id` from "untyped nullable" (R2) to a real FK. SQLite limits ALTER TABLE — alembic uses batch_alter_table for the FK addition.

- [ ] **Step 1: Write the failing test**

```python
import pytest

from app.models.project import Project
from app.models.project_version import ProjectVersion, VersionSource
from app.models.user import User
from app.models.workspace import Workspace


@pytest.mark.asyncio
async def test_project_version_persists(db_session):
    user = User(email="v@v.com", password_hash="x")
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
        model_id_snapshot="claude-opus-4-7",
        counterexample_ids=[],
        source=VersionSource.INITIAL.value,
        source_metadata={},
        created_by=user.id,
    )
    db_session.add(v)
    await db_session.commit()
    await db_session.refresh(v)
    assert v.id is not None
    assert v.version_number == 0


@pytest.mark.asyncio
async def test_invalid_source_rejected(db_session):
    user = User(email="vv@v.com", password_hash="x")
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
        model_id_snapshot="x",
        counterexample_ids=[],
        source="bogus",
        source_metadata={},
        created_by=user.id,
    )
    db_session.add(v)
    with pytest.raises(Exception):
        await db_session.commit()
```

- [ ] **Step 2: Run — expect ImportError**

- [ ] **Step 3: Implement `app/models/project_version.py`**

```python
from enum import Enum

from sqlalchemy import JSON, CheckConstraint, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class VersionSource(str, Enum):
    INITIAL = "initial"
    USER_EDIT = "user_edit"
    AUTO_RESEARCH = "auto_research"


class ProjectVersion(Base, TimestampMixin):
    __tablename__ = "project_versions"
    __table_args__ = (
        CheckConstraint(
            "source IN ('initial','user_edit','auto_research')",
            name="ck_project_version_source",
        ),
        UniqueConstraint(
            "project_id", "version_number", name="uq_project_version_number"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id"), nullable=False, index=True
    )
    parent_version_id: Mapped[int | None] = mapped_column(
        ForeignKey("project_versions.id"), nullable=True
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)

    schema_snapshot: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    global_notes_snapshot: Mapped[str] = mapped_column(Text, nullable=False, default="")
    model_id_snapshot: Mapped[str] = mapped_column(String(128), nullable=False)
    counterexample_ids: Mapped[list] = mapped_column(JSON, nullable=False, default=list)

    source: Mapped[str] = mapped_column(String(32), nullable=False)
    source_metadata: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)

    locked: Mapped[bool] = mapped_column(default=False, nullable=False)

    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
```

Re-export.

- [ ] **Step 4: Run model test to verify it passes**

- [ ] **Step 5: Generate migration**

```bash
cd backend && uv run alembic revision --autogenerate -m "project version table"
# rename to 0007_project_version.py
```

The autogenerated upgrade should also add an FK from `projects.active_version_id` to `project_versions.id`. If alembic-autogenerate misses it, edit the migration to wrap in `op.batch_alter_table("projects")` and add `op.create_foreign_key(...)`. Apply and verify schema:

```bash
uv run alembic upgrade head
sqlite3 backend/data/emerge.db ".schema project_versions"
```

- [ ] **Step 6: Commit**

```bash
git add backend/app/models/project_version.py backend/app/models/__init__.py backend/alembic/versions/0007_project_version.py backend/tests/test_project_version_model.py
git commit -m "feat(backend): add ProjectVersion model + 0007 migration"
```

---

## Task 3: Auto-create initial empty ProjectVersion on Project create

**Files:**
- Modify: `backend/app/api/routes/projects.py` (after `Project` insert, also insert `ProjectVersion v0`)
- Modify: `backend/tests/test_project_routes.py` (assert version 0 exists; assert `active_version_id` is set)

- [ ] **Step 1: Append failing test**

```python
@pytest.mark.asyncio
async def test_create_project_creates_initial_version(client, db_session):
    h = await _auth(client)
    body = (await client.post("/api/v1/projects", json={"name": "P"}, headers=h)).json()
    pid = body["id"]
    assert body["active_version_id"] is not None

    from sqlalchemy import select

    from app.models.project_version import ProjectVersion

    rows = (
        await db_session.execute(
            select(ProjectVersion).where(ProjectVersion.project_id == pid)
        )
    ).scalars().all()
    assert len(rows) == 1
    assert rows[0].version_number == 0
    assert rows[0].source == "initial"
    assert rows[0].schema_snapshot == []
```

- [ ] **Step 2: Run — expect failure**

- [ ] **Step 3: Update `app/api/routes/projects.py`**

```python
from app.models.project_version import ProjectVersion, VersionSource


# inside create_project, after Project flush:
v = ProjectVersion(
    project_id=p.id,
    version_number=0,
    schema_snapshot=[],
    global_notes_snapshot="",
    model_id_snapshot="claude-opus-4-7",
    counterexample_ids=[],
    source=VersionSource.INITIAL.value,
    source_metadata={"reason": "project_created"},
    created_by=user.id,
)
session.add(v)
await session.flush()
p.active_version_id = v.id
await session.commit()
await session.refresh(p)
```

- [ ] **Step 4: Run test to verify it passes**

- [ ] **Step 5: Commit**

```bash
git add backend/app/api/routes/projects.py backend/tests/test_project_routes.py
git commit -m "feat(backend): create initial empty ProjectVersion on Project create"
```

---

## Task 4: Build responseSchema (JSON Schema) from `list[SchemaField]`

**Files:**
- Create: `backend/app/engine/__init__.py` (empty)
- Create: `backend/app/engine/response_schema.py`
- Create: `backend/tests/test_response_schema.py`

Output is the JSON Schema dict the LLM provider will pass as `response_format` (OpenAI) or `response_schema` (Gemini). **Top-level type is always `array<object>`** (spec §1.2).

- [ ] **Step 1: Write the failing test**

```python
from app.engine.response_schema import build_response_schema
from app.schemas.schema_field import FieldType, SchemaField


def test_top_level_is_array_of_object():
    schema = build_response_schema(
        [SchemaField(name="x", type=FieldType.STRING, description="d")]
    )
    assert schema["type"] == "array"
    assert schema["items"]["type"] == "object"
    assert "x" in schema["items"]["properties"]


def test_required_only_listed_when_required():
    schema = build_response_schema(
        [
            SchemaField(name="a", type=FieldType.STRING, required=True, description="d"),
            SchemaField(name="b", type=FieldType.STRING, required=False, description="d"),
        ]
    )
    assert set(schema["items"]["required"]) == {"a"}


def test_enum_passes_through():
    schema = build_response_schema(
        [
            SchemaField(
                name="ccy",
                type=FieldType.STRING,
                description="d",
                enum=["JPY", "USD"],
            )
        ]
    )
    assert schema["items"]["properties"]["ccy"]["enum"] == ["JPY", "USD"]


def test_nested_array_of_object():
    schema = build_response_schema(
        [
            SchemaField(
                name="line_items",
                type=FieldType.ARRAY,
                description="d",
                child_fields=[
                    SchemaField(name="qty", type=FieldType.INTEGER, description="d"),
                ],
            )
        ]
    )
    li = schema["items"]["properties"]["line_items"]
    assert li["type"] == "array"
    assert li["items"]["type"] == "object"
    assert "qty" in li["items"]["properties"]


def test_empty_fields_returns_array_of_object_with_no_props():
    schema = build_response_schema([])
    assert schema == {
        "type": "array",
        "items": {"type": "object", "properties": {}, "required": []},
    }
```

- [ ] **Step 2: Run — expect ImportError**

- [ ] **Step 3: Implement `app/engine/response_schema.py`**

```python
from app.schemas.schema_field import FieldType, SchemaField

_PRIMITIVE: dict[FieldType, str] = {
    FieldType.STRING: "string",
    FieldType.NUMBER: "number",
    FieldType.INTEGER: "integer",
    FieldType.BOOLEAN: "boolean",
}


def _field_to_jsonschema(f: SchemaField) -> dict:
    if f.type is FieldType.ARRAY:
        return {
            "type": "array",
            "items": _object_from_fields(f.child_fields),
            "description": f.description,
        }
    spec: dict = {"type": _PRIMITIVE[f.type], "description": f.description}
    if f.enum:
        spec["enum"] = list(f.enum)
    return spec


def _object_from_fields(fields: list[SchemaField]) -> dict:
    return {
        "type": "object",
        "properties": {f.name: _field_to_jsonschema(f) for f in fields},
        "required": [f.name for f in fields if f.required],
    }


def build_response_schema(fields: list[SchemaField]) -> dict:
    """Top-level JSON Schema dict for a multi-entity extraction response."""
    return {"type": "array", "items": _object_from_fields(fields)}
```

- [ ] **Step 4: Run test to verify it passes**

Expected: `5 passed`.

- [ ] **Step 5: Commit**

```bash
git add backend/app/engine/__init__.py backend/app/engine/response_schema.py backend/tests/test_response_schema.py
git commit -m "feat(engine): build_response_schema from SchemaField list"
```

---

## Task 5: System frame + prompt composer

**Files:**
- Create: `backend/app/engine/system_frame.py`
- Create: `backend/app/engine/prompt.py`
- Create: `backend/tests/test_prompt_composer.py`

`SYSTEM_FRAME` is the fixed boilerplate from spec §1: ~150 tokens, code-managed, user invisible. Composer joins `system_frame + per-field instructions + global_notes` and returns a `ChatRequest` dataclass that providers consume. **No few-shot path** — assert it never injects example I/O pairs.

- [ ] **Step 1: Write the failing test**

```python
from app.engine.prompt import compose_extraction_prompt
from app.engine.system_frame import SYSTEM_FRAME
from app.schemas.schema_field import FieldType, SchemaField


def test_system_frame_is_present():
    req = compose_extraction_prompt(
        fields=[SchemaField(name="x", type=FieldType.STRING, description="d")],
        global_notes="",
        model_id="claude-opus-4-7",
    )
    assert SYSTEM_FRAME in req.system


def test_each_field_description_appears_once():
    req = compose_extraction_prompt(
        fields=[
            SchemaField(name="a", type=FieldType.STRING, description="alpha"),
            SchemaField(name="b", type=FieldType.STRING, description="beta"),
        ],
        global_notes="",
        model_id="x",
    )
    assert req.system.count("alpha") == 1
    assert req.system.count("beta") == 1


def test_global_notes_appended_after_per_field():
    req = compose_extraction_prompt(
        fields=[SchemaField(name="a", type=FieldType.STRING, description="alpha")],
        global_notes="all amounts in JPY",
        model_id="x",
    )
    a_idx = req.system.find("alpha")
    g_idx = req.system.find("all amounts in JPY")
    assert g_idx > a_idx > 0


def test_examples_inlined_in_field_description():
    req = compose_extraction_prompt(
        fields=[
            SchemaField(
                name="ccy",
                type=FieldType.STRING,
                description="ISO 4217",
                examples=["JPY", "USD"],
            )
        ],
        global_notes="",
        model_id="x",
    )
    assert "JPY" in req.system and "USD" in req.system


def test_no_image_few_shot_path():
    """Spec §1: there is no path that injects example image / output pairs."""
    req = compose_extraction_prompt(
        fields=[SchemaField(name="x", type=FieldType.STRING, description="d")],
        global_notes="",
        model_id="x",
    )
    assert req.image_few_shots == []  # explicit empty; field exists for type clarity
```

- [ ] **Step 2: Run — expect ImportError**

- [ ] **Step 3: Implement `app/engine/system_frame.py`**

```python
SYSTEM_FRAME = """\
You are emerge, an extraction agent. Read the supplied document image or PDF and emit a single
JSON value matching the supplied response schema. Output contract:
- Top-level value is always an array of objects (a document may contain multiple entities).
- Object keys are snake_case English names; never abbreviate, never camelCase.
- If you are uncertain about a field's value, omit the key rather than emitting null.
- Follow the per-field instructions below strictly. If the global notes apply, follow them too.
- Do not invent fields not listed. Do not return prose or code fences — only the JSON value.\
"""
```

- [ ] **Step 4: Implement `app/engine/prompt.py`**

```python
from dataclasses import dataclass, field

from app.engine.system_frame import SYSTEM_FRAME
from app.schemas.schema_field import SchemaField


@dataclass
class ChatRequest:
    """Provider-agnostic prompt envelope. Providers translate to their SDK shapes."""

    system: str
    user_text: str
    model_id: str
    response_schema: dict
    image_few_shots: list = field(default_factory=list)  # always [] in v1 — invariant


def _format_field(idx: int, f: SchemaField) -> str:
    parts = [f"{idx}. `{f.name}` ({f.type.value}{', required' if f.required else ', optional'})"]
    parts.append(f"   description: {f.description}")
    if f.examples:
        parts.append(f"   examples: {', '.join(f.examples)}")
    if f.enum:
        parts.append(f"   enum: {', '.join(f.enum)}")
    if f.child_fields:
        parts.append("   child fields:")
        for j, cf in enumerate(f.child_fields, 1):
            parts.append(f"     {j}. `{cf.name}` ({cf.type.value}): {cf.description}")
    return "\n".join(parts)


def compose_extraction_prompt(
    *,
    fields: list[SchemaField],
    global_notes: str,
    model_id: str,
) -> ChatRequest:
    field_lines = "\n".join(_format_field(i, f) for i, f in enumerate(fields, 1))
    system = SYSTEM_FRAME
    if field_lines:
        system += "\n\nPer-field instructions:\n" + field_lines
    if global_notes.strip():
        system += "\n\nGlobal notes:\n" + global_notes.strip()
    from app.engine.response_schema import build_response_schema

    return ChatRequest(
        system=system,
        user_text="Extract structured data from the attached document.",
        model_id=model_id,
        response_schema=build_response_schema(fields),
        image_few_shots=[],
    )
```

- [ ] **Step 5: Run test to verify it passes**

Expected: `5 passed`.

- [ ] **Step 6: Commit**

```bash
git add backend/app/engine/system_frame.py backend/app/engine/prompt.py backend/tests/test_prompt_composer.py
git commit -m "feat(engine): SYSTEM_FRAME + compose_extraction_prompt (no few-shot path)"
```

---

## Task 6: Provider protocol + FakeProvider for tests

**Files:**
- Create: `backend/app/engine/provider.py`
- Create: `backend/app/engine/providers/__init__.py` (empty)
- Create: `backend/app/engine/providers/fake.py`
- Create: `backend/tests/test_provider_fake.py`

`Provider` is an abstract Protocol. `FakeProvider` is the test double that returns canned JSON on demand.

- [ ] **Step 1: Write the failing test**

```python
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
```

- [ ] **Step 2: Run — expect ImportError**

- [ ] **Step 3: Implement `app/engine/provider.py`**

```python
from dataclasses import dataclass
from typing import Protocol

from app.engine.prompt import ChatRequest


@dataclass
class ExtractionResult:
    output: list[dict]
    tokens_used: int
    latency_ms: int
    raw_response: dict | None = None
    cost_estimate: float = 0.0


class Provider(Protocol):
    async def extract(
        self,
        request: ChatRequest,
        *,
        file_bytes: bytes,
        mime_type: str,
    ) -> ExtractionResult:
        ...
```

- [ ] **Step 4: Implement `app/engine/providers/fake.py`**

```python
from collections import deque

from app.engine.prompt import ChatRequest
from app.engine.provider import ExtractionResult


class FakeProvider:
    """Test double. `canned` is a queue of either result lists or Exceptions."""

    def __init__(self, *, canned: list):
        self._queue = deque(canned)
        self.calls: list[ChatRequest] = []

    async def extract(
        self, request: ChatRequest, *, file_bytes: bytes, mime_type: str
    ) -> ExtractionResult:
        self.calls.append(request)
        if not self._queue:
            raise RuntimeError("FakeProvider out of canned responses")
        nxt = self._queue.popleft()
        if isinstance(nxt, BaseException):
            raise nxt
        return ExtractionResult(output=nxt, tokens_used=0, latency_ms=0)
```

- [ ] **Step 5: Run test to verify it passes**

- [ ] **Step 6: Commit**

```bash
git add backend/app/engine/provider.py backend/app/engine/providers/ backend/tests/test_provider_fake.py
git commit -m "feat(engine): Provider protocol + FakeProvider test double"
```

---

## Task 7: OpenAI + Gemini provider concrete impls

**Files:**
- Create: `backend/app/engine/providers/openai_provider.py`
- Create: `backend/app/engine/providers/gemini_provider.py`
- Modify: `backend/app/settings.py` (add `openai_api_key`, `google_api_key`, `default_provider`)

These are network-touching. Tests are **not** required at this layer — `Provider` protocol guarantees substitutability and `FakeProvider` covers the consumer side. Add a single live-network-skipped smoke test per provider that's gated behind `EMERGE_RUN_LIVE_PROVIDER_TESTS=1`.

- [ ] **Step 1: Add settings**

In `app/settings.py`, append:

```python
openai_api_key: str | None = None
google_api_key: str | None = None
default_provider: str = "openai"  # 'openai' | 'gemini'
default_model_openai: str = "gpt-4o-2024-08-06"
default_model_gemini: str = "gemini-2.0-flash"
```

- [ ] **Step 2: Implement `app/engine/providers/openai_provider.py`**

```python
import time

from openai import AsyncOpenAI

from app.engine.prompt import ChatRequest
from app.engine.provider import ExtractionResult
from app.settings import settings


class OpenAIProvider:
    def __init__(self, client: AsyncOpenAI | None = None):
        self.client = client or AsyncOpenAI(api_key=settings.openai_api_key)

    async def extract(
        self, request: ChatRequest, *, file_bytes: bytes, mime_type: str
    ) -> ExtractionResult:
        import base64

        b64 = base64.b64encode(file_bytes).decode()
        data_url = f"data:{mime_type};base64,{b64}"

        started = time.perf_counter()
        resp = await self.client.chat.completions.create(
            model=request.model_id,
            messages=[
                {"role": "system", "content": request.system},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": request.user_text},
                        {"type": "image_url", "image_url": {"url": data_url}},
                    ],
                },
            ],
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "emerge_extract",
                    "schema": {
                        "type": "object",
                        "properties": {"entities": request.response_schema},
                        "required": ["entities"],
                    },
                    "strict": True,
                },
            },
        )
        elapsed = int((time.perf_counter() - started) * 1000)
        import json

        wrapped = json.loads(resp.choices[0].message.content)
        return ExtractionResult(
            output=wrapped["entities"],
            tokens_used=resp.usage.total_tokens if resp.usage else 0,
            latency_ms=elapsed,
            raw_response={"id": resp.id, "model": resp.model},
        )
```

- [ ] **Step 3: Implement `app/engine/providers/gemini_provider.py`**

```python
import time

from google import genai

from app.engine.prompt import ChatRequest
from app.engine.provider import ExtractionResult
from app.settings import settings


class GeminiProvider:
    def __init__(self, client: genai.Client | None = None):
        self.client = client or genai.Client(api_key=settings.google_api_key)

    async def extract(
        self, request: ChatRequest, *, file_bytes: bytes, mime_type: str
    ) -> ExtractionResult:
        from google.genai import types

        started = time.perf_counter()
        resp = await self.client.aio.models.generate_content(
            model=request.model_id,
            contents=[
                types.Content(
                    role="user",
                    parts=[
                        types.Part.from_bytes(data=file_bytes, mime_type=mime_type),
                        types.Part.from_text(text=request.user_text),
                    ],
                )
            ],
            config=types.GenerateContentConfig(
                system_instruction=request.system,
                response_mime_type="application/json",
                response_schema=request.response_schema,
            ),
        )
        elapsed = int((time.perf_counter() - started) * 1000)
        import json

        return ExtractionResult(
            output=json.loads(resp.text),
            tokens_used=getattr(resp.usage_metadata, "total_token_count", 0) if resp.usage_metadata else 0,
            latency_ms=elapsed,
            raw_response={"model": request.model_id},
        )
```

- [ ] **Step 4: Add provider factory**

In `app/engine/providers/__init__.py`:

```python
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.engine.provider import Provider


def get_provider(name: str | None = None) -> "Provider":
    from app.engine.providers.gemini_provider import GeminiProvider
    from app.engine.providers.openai_provider import OpenAIProvider
    from app.settings import settings

    name = name or settings.default_provider
    if name == "openai":
        return OpenAIProvider()
    if name == "gemini":
        return GeminiProvider()
    raise ValueError(f"unknown provider {name!r}")
```

- [ ] **Step 5: Smoke test (manual, optional)**

Create `backend/tests/test_provider_live.py`:

```python
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
```

(Add a placeholder PNG to `tests/fixtures/sample_receipt.png` — any small image will do for smoke wiring.)

- [ ] **Step 6: Commit**

```bash
git add backend/app/engine/providers/ backend/app/settings.py backend/tests/test_provider_live.py
git commit -m "feat(engine): OpenAI + Gemini providers + factory"
```

---

## Task 8: count_pdf_pages helper

**Files:**
- Create: `backend/app/services/pdf.py`
- Create: `backend/tests/test_pdf_pages.py`
- Add `PyPDF2>=3.0.0` to `backend/pyproject.toml` deps

- [ ] **Step 1: Add `PyPDF2>=3.0.0` to deps**, run `uv sync --extra dev`.

- [ ] **Step 2: Write the failing test**

```python
import pytest

from app.services.pdf import count_pdf_pages


def test_pdf_pages_real_file(tmp_path):
    """Use a tiny generated PDF. PyPDF2 round-trips this."""
    from PyPDF2 import PdfWriter

    p = tmp_path / "x.pdf"
    w = PdfWriter()
    w.add_blank_page(width=100, height=100)
    w.add_blank_page(width=100, height=100)
    with open(p, "wb") as fh:
        w.write(fh)
    assert count_pdf_pages(str(p)) == 2


def test_unknown_file_returns_zero(tmp_path):
    p = tmp_path / "junk"
    p.write_bytes(b"not-a-pdf")
    assert count_pdf_pages(str(p)) == 0
```

- [ ] **Step 3: Implement `app/services/pdf.py`**

```python
def count_pdf_pages(file_path: str) -> int:
    try:
        from PyPDF2 import PdfReader

        return len(PdfReader(file_path).pages)
    except Exception:
        return 0
```

- [ ] **Step 4: Run test to verify it passes**

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/pdf.py backend/tests/test_pdf_pages.py backend/pyproject.toml
git commit -m "feat(backend): add count_pdf_pages helper"
```

---

## Task 9: extract_document service

**Files:**
- Create: `backend/app/engine/extract.py`
- Create: `backend/tests/test_extract_document.py`

`extract_document` orchestrates: load `Document` → load active `ProjectVersion` → compose prompt → call provider → write `Prediction` → flip `Document.status` to `extracted` (or `errored`). Provider is injected so tests use `FakeProvider`.

- [ ] **Step 1: Write the failing test**

```python
import pytest

from app.engine.extract import extract_document
from app.engine.providers.fake import FakeProvider
from app.models.document import Document, DocumentStatus
from app.models.prediction import Prediction
from app.models.project import Project
from app.models.project_version import ProjectVersion, VersionSource
from app.models.user import User
from app.models.workspace import Workspace


async def _setup(db_session, schema=None):
    user = User(email="e@e.com", password_hash="x")
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
        schema_snapshot=schema or [],
        global_notes_snapshot="",
        model_id_snapshot="any-model",
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
        filename="x.pdf",
        file_path="/tmp/x.pdf",
        mime_type="application/pdf",
        page_count=1,
        byte_size=10,
        uploaded_by=user.id,
    )
    db_session.add(d)
    await db_session.commit()
    return p, v, d


@pytest.mark.asyncio
async def test_extract_writes_prediction_and_flips_status(db_session, tmp_path):
    p, v, d = await _setup(db_session)
    fp = tmp_path / "x.pdf"
    fp.write_bytes(b"PDF")
    d.file_path = str(fp)
    await db_session.commit()

    fake = FakeProvider(canned=[[{"shop_name": "ABC"}]])
    pred = await extract_document(d.id, session=db_session, provider=fake)
    assert pred.output == [{"shop_name": "ABC"}]
    assert pred.status == "success"
    await db_session.refresh(d)
    assert d.status == DocumentStatus.EXTRACTED.value


@pytest.mark.asyncio
async def test_extract_failure_sets_errored(db_session, tmp_path):
    p, v, d = await _setup(db_session)
    fp = tmp_path / "x.pdf"
    fp.write_bytes(b"PDF")
    d.file_path = str(fp)
    await db_session.commit()

    fake = FakeProvider(canned=[RuntimeError("boom")])
    pred = await extract_document(d.id, session=db_session, provider=fake)
    assert pred.status == "failed"
    assert pred.error_message and "boom" in pred.error_message
    await db_session.refresh(d)
    assert d.status == DocumentStatus.ERRORED.value
```

- [ ] **Step 2: Run — expect ImportError**

- [ ] **Step 3: Implement `app/engine/extract.py`**

```python
import hashlib
import json
import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.engine.prompt import compose_extraction_prompt
from app.engine.provider import Provider
from app.models.document import Document, DocumentStatus
from app.models.prediction import Prediction, PredictionStatus
from app.models.project import Project
from app.models.project_version import ProjectVersion
from app.schemas.schema_field import SchemaField

log = logging.getLogger(__name__)


def _hash_prompt(system: str, response_schema: dict) -> str:
    payload = json.dumps({"s": system, "r": response_schema}, sort_keys=True).encode()
    return hashlib.sha256(payload).hexdigest()[:32]


async def extract_document(
    document_id: int,
    *,
    session: AsyncSession,
    provider: Provider,
) -> Prediction:
    d = (await session.execute(select(Document).where(Document.id == document_id))).scalar_one()
    p = (await session.execute(select(Project).where(Project.id == d.project_id))).scalar_one()
    if p.active_version_id is None:
        raise ValueError(f"project {p.id} has no active version")
    v = (
        await session.execute(
            select(ProjectVersion).where(ProjectVersion.id == p.active_version_id)
        )
    ).scalar_one()

    fields = [SchemaField(**f) for f in v.schema_snapshot]
    request = compose_extraction_prompt(
        fields=fields,
        global_notes=v.global_notes_snapshot,
        model_id=v.model_id_snapshot,
    )
    prompt_hash = _hash_prompt(request.system, request.response_schema)

    d.status = DocumentStatus.EXTRACTING.value
    await session.commit()

    try:
        with open(d.file_path, "rb") as fh:
            file_bytes = fh.read()
        result = await provider.extract(request, file_bytes=file_bytes, mime_type=d.mime_type)
        pred = Prediction(
            document_id=d.id,
            project_version_id=v.id,
            model_id=v.model_id_snapshot,
            prompt_hash=prompt_hash,
            output=result.output,
            per_field_confidence={},
            tokens_used=result.tokens_used,
            latency_ms=result.latency_ms,
            cost_estimate=result.cost_estimate,
            status=PredictionStatus.SUCCESS.value,
        )
        d.status = DocumentStatus.EXTRACTED.value
    except Exception as exc:
        log.exception("extraction failed for document %d", d.id)
        pred = Prediction(
            document_id=d.id,
            project_version_id=v.id,
            model_id=v.model_id_snapshot,
            prompt_hash=prompt_hash,
            output=[],
            per_field_confidence={},
            tokens_used=0,
            latency_ms=0,
            cost_estimate=0.0,
            status=PredictionStatus.FAILED.value,
            error_message=str(exc)[:1900],
        )
        d.status = DocumentStatus.ERRORED.value

    session.add(pred)
    await session.commit()
    await session.refresh(pred)
    return pred
```

- [ ] **Step 4: Run test to verify it passes**

Expected: `2 passed`.

- [ ] **Step 5: Commit**

```bash
git add backend/app/engine/extract.py backend/tests/test_extract_document.py
git commit -m "feat(engine): extract_document writes Prediction + flips Document.status"
```

---

## Task 10: Batch extraction endpoint with SSE progress

**Files:**
- Create: `backend/app/api/routes/extraction.py`
- Modify: `backend/app/api/v1.py` (mount)
- Create: `backend/tests/test_extraction_routes.py`

Spec §10 mandates SSE per-document progress events; failures don't abort the batch. Provider is injectable via FastAPI dep so tests substitute `FakeProvider`.

- [ ] **Step 1: Add `get_provider_dep` factory**

In `app/engine/providers/__init__.py`, append:

```python
def get_provider_dep():
    """FastAPI dependency. Returns the configured provider singleton."""
    return get_provider()
```

- [ ] **Step 2: Write the failing test**

```python
import io

import pytest


async def _auth_and_project(client) -> tuple[dict, int]:
    await client.post("/api/v1/auth/register", json={"email": "ex@ex.com", "password": "hunter22"})
    tok = (
        await client.post("/api/v1/auth/login", json={"email": "ex@ex.com", "password": "hunter22"})
    ).json()["access_token"]
    h = {"Authorization": f"Bearer {tok}"}
    pid = (await client.post("/api/v1/projects", json={"name": "P"}, headers=h)).json()["id"]
    return h, pid


@pytest.mark.asyncio
async def test_batch_extract_streams_per_document_events(client, tmp_path, monkeypatch, app):
    monkeypatch.setattr("app.services.storage.settings.storage_root", str(tmp_path))
    h, pid = await _auth_and_project(client)
    await client.post(
        f"/api/v1/projects/{pid}/documents",
        files=[
            ("files", ("a.pdf", io.BytesIO(b"AAA"), "application/pdf")),
            ("files", ("b.pdf", io.BytesIO(b"BB"), "application/pdf")),
        ],
        headers=h,
    )

    from app.engine.providers import get_provider_dep
    from app.engine.providers.fake import FakeProvider

    fake = FakeProvider(canned=[[{"x": "1"}], [{"x": "2"}]])
    app.dependency_overrides[get_provider_dep] = lambda: fake

    resp = await client.post(f"/api/v1/projects/{pid}/extract", headers=h)
    assert resp.status_code == 200
    assert "text/event-stream" in resp.headers["content-type"]
    body = resp.text
    # two `data: {...}` lines at minimum
    assert body.count("event: progress") == 2
    assert body.count("event: done") == 1
```

- [ ] **Step 3: Run — expect 404**

- [ ] **Step 4: Implement `app/api/routes/extraction.py`**

```python
import asyncio
import json

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import current_workspace_id
from app.db import SessionFactory, get_session
from app.engine.extract import extract_document
from app.engine.provider import Provider
from app.engine.providers import get_provider_dep
from app.errors import EmergeError, ErrorCode
from app.models.document import Document, DocumentStatus
from app.models.project import Project

router = APIRouter(prefix="/projects/{project_id}", tags=["extraction"])


@router.post("/extract")
async def batch_extract(
    project_id: int,
    workspace_id: int = Depends(current_workspace_id),
    provider: Provider = Depends(get_provider_dep),
    session: AsyncSession = Depends(get_session),
):
    project = (
        await session.execute(
            select(Project).where(
                Project.id == project_id, Project.workspace_id == workspace_id
            )
        )
    ).scalar_one_or_none()
    if project is None:
        raise EmergeError(ErrorCode.NOT_FOUND, status_code=404)
    doc_ids = (
        await session.execute(
            select(Document.id).where(
                Document.project_id == project_id,
                Document.status.in_(
                    [DocumentStatus.UPLOADED.value, DocumentStatus.ERRORED.value]
                ),
            )
        )
    ).scalars().all()

    async def _run_one(doc_id: int) -> tuple[int, str, str | None]:
        async with SessionFactory() as own_session:
            try:
                pred = await extract_document(doc_id, session=own_session, provider=provider)
                return doc_id, pred.status, None
            except Exception as e:
                return doc_id, "failed", str(e)[:200]

    async def _gen():
        tasks = [asyncio.create_task(_run_one(d)) for d in doc_ids]
        for coro in asyncio.as_completed(tasks):
            doc_id, status, err = await coro
            payload = {"document_id": doc_id, "status": status, "error": err}
            yield f"event: progress\ndata: {json.dumps(payload)}\n\n"
        yield "event: done\ndata: {}\n\n"

    return StreamingResponse(_gen(), media_type="text/event-stream")
```

- [ ] **Step 5: Mount router in `app/api/v1.py`**

```python
from app.api.routes import auth, documents, extraction, me, projects

api_v1.include_router(extraction.router)
```

- [ ] **Step 6: Run test to verify it passes**

Expected: `1 passed`.

- [ ] **Step 7: Commit**

```bash
git add backend/app/api/routes/extraction.py backend/app/api/v1.py backend/app/engine/providers/__init__.py backend/tests/test_extraction_routes.py
git commit -m "feat(api): batch extract endpoint with SSE per-document progress"
```

---

## Task 11: Schema auto-derivation from corrected Annotations

**Files:**
- Create: `backend/app/engine/derive_schema.py`
- Create: `backend/tests/test_derive_schema.py`

Spec §2.2 step 3: when ≥ 1 corrections exist, derive a schema candidate from the JSON shape. **Description is a generic placeholder** — the user fills it in (spec §2.4: never auto-reverse-engineer descriptions from JSON).

- [ ] **Step 1: Write the failing test**

```python
from app.engine.derive_schema import derive_schema_candidate
from app.schemas.schema_field import FieldType


def test_simple_object_round_trip():
    fields = derive_schema_candidate([[{"shop_name": "X", "total": 100, "open": True}]])
    by = {f.name: f for f in fields}
    assert by["shop_name"].type is FieldType.STRING
    assert by["total"].type is FieldType.NUMBER
    assert by["open"].type is FieldType.BOOLEAN
    assert all("refine description" in f.description for f in fields)


def test_nested_array_of_object():
    fields = derive_schema_candidate(
        [
            [
                {
                    "line_items": [
                        {"qty": 1, "name": "Coffee"},
                        {"qty": 2, "name": "Tea"},
                    ]
                }
            ]
        ]
    )
    li = next(f for f in fields if f.name == "line_items")
    assert li.type is FieldType.ARRAY
    by_child = {c.name for c in li.child_fields}
    assert by_child == {"qty", "name"}


def test_field_required_only_if_present_in_all_entities():
    fields = derive_schema_candidate(
        [
            [{"a": "x", "b": "y"}],
            [{"a": "x"}],
        ]
    )
    by = {f.name: f for f in fields}
    assert by["a"].required is True
    assert by["b"].required is False


def test_integer_inferred_when_all_numbers_are_integers():
    fields = derive_schema_candidate([[{"qty": 1}], [{"qty": 2}]])
    by = {f.name: f for f in fields}
    assert by["qty"].type is FieldType.INTEGER


def test_skips_non_snake_case_keys():
    fields = derive_schema_candidate([[{"shopName": "X", "shop_name": "Y"}]])
    names = {f.name for f in fields}
    assert "shop_name" in names
    assert "shopName" not in names
```

- [ ] **Step 2: Run — expect ImportError**

- [ ] **Step 3: Implement `app/engine/derive_schema.py`**

```python
import re

from app.schemas.schema_field import FieldType, SchemaField

_SNAKE = re.compile(r"^[a-z][a-z0-9_]*$")
_PLACEHOLDER = "value derived from document; refine description as needed"


def _infer_type(values: list) -> FieldType | None:
    types_seen = set()
    for v in values:
        if isinstance(v, bool):
            types_seen.add("boolean")
        elif isinstance(v, int):
            types_seen.add("integer")
        elif isinstance(v, float):
            types_seen.add("number")
        elif isinstance(v, str):
            types_seen.add("string")
        elif isinstance(v, list):
            types_seen.add("array")
        elif v is None:
            continue
        else:
            return None
    if not types_seen:
        return None
    if types_seen == {"integer"}:
        return FieldType.INTEGER
    if types_seen <= {"integer", "number"}:
        return FieldType.NUMBER
    if types_seen == {"string"}:
        return FieldType.STRING
    if types_seen == {"boolean"}:
        return FieldType.BOOLEAN
    if types_seen == {"array"}:
        return FieldType.ARRAY
    return FieldType.STRING


def derive_schema_candidate(annotations: list[list[dict]]) -> list[SchemaField]:
    """`annotations` is a list of saved Annotation.output values (each is array<object>)."""
    field_values: dict[str, list] = {}
    field_presence_in_entity_count: dict[str, int] = {}
    total_entities = 0
    for ann in annotations:
        for entity in ann:
            total_entities += 1
            for k, v in entity.items():
                if not _SNAKE.match(k):
                    continue
                field_values.setdefault(k, []).append(v)
                field_presence_in_entity_count[k] = field_presence_in_entity_count.get(k, 0) + 1

    out: list[SchemaField] = []
    for name, vals in field_values.items():
        ftype = _infer_type(vals)
        if ftype is None:
            continue
        required = field_presence_in_entity_count[name] == total_entities
        if ftype is FieldType.ARRAY:
            children_values: dict[str, list] = {}
            children_presence: dict[str, int] = {}
            child_entity_count = 0
            for arr in vals:
                if not isinstance(arr, list):
                    continue
                for child in arr:
                    if not isinstance(child, dict):
                        continue
                    child_entity_count += 1
                    for ck, cv in child.items():
                        if not _SNAKE.match(ck):
                            continue
                        children_values.setdefault(ck, []).append(cv)
                        children_presence[ck] = children_presence.get(ck, 0) + 1
            child_fields: list[SchemaField] = []
            for ck, cv in children_values.items():
                ct = _infer_type(cv)
                if ct is None or ct is FieldType.ARRAY:
                    continue  # skip 2-level nesting in v1 derivation
                child_fields.append(
                    SchemaField(
                        name=ck,
                        type=ct,
                        required=children_presence[ck] == child_entity_count,
                        description=_PLACEHOLDER,
                    )
                )
            if not child_fields:
                continue
            out.append(
                SchemaField(
                    name=name,
                    type=FieldType.ARRAY,
                    required=required,
                    description=_PLACEHOLDER,
                    child_fields=child_fields,
                )
            )
        else:
            out.append(
                SchemaField(name=name, type=ftype, required=required, description=_PLACEHOLDER)
            )
    return out
```

- [ ] **Step 4: Run test to verify it passes**

Expected: `5 passed`.

- [ ] **Step 5: Commit**

```bash
git add backend/app/engine/derive_schema.py backend/tests/test_derive_schema.py
git commit -m "feat(engine): derive_schema_candidate from Annotation outputs (placeholder descriptions)"
```

---

## Task 12: Version + schema endpoints (read, edit, lock)

**Files:**
- Create: `backend/app/schemas/project_version.py`
- Create: `backend/app/api/routes/versions.py`
- Modify: `backend/app/api/v1.py` (mount)
- Create: `backend/tests/test_version_routes.py`
- Create: `backend/tests/test_lock_workflow.py`

Endpoints:
- `GET /api/v1/projects/{pid}/versions/active` → returns active `ProjectVersion`
- `PATCH /api/v1/projects/{pid}/schema` → body = `{ schema: list[SchemaField], global_notes: str, model_id: str }` → creates new `ProjectVersion (source=user_edit)` and sets `active_version_id`
- `GET /api/v1/projects/{pid}/lock-status` → returns `{ can_lock: bool, reason: str | None }` per spec §2.3
- `POST /api/v1/projects/{pid}/lock` → if `can_lock`, sets `ProjectVersion.locked = true` on active version
- `POST /api/v1/projects/{pid}/unlock` → unsets

- [ ] **Step 1: Write failing tests for read + patch**

`backend/tests/test_version_routes.py`:

```python
import pytest


async def _auth_and_project(client, email="vp@vp.com"):
    await client.post("/api/v1/auth/register", json={"email": email, "password": "hunter22"})
    tok = (
        await client.post("/api/v1/auth/login", json={"email": email, "password": "hunter22"})
    ).json()["access_token"]
    h = {"Authorization": f"Bearer {tok}"}
    pid = (await client.post("/api/v1/projects", json={"name": "P"}, headers=h)).json()["id"]
    return h, pid


@pytest.mark.asyncio
async def test_get_active_version_returns_initial(client):
    h, pid = await _auth_and_project(client)
    resp = await client.get(f"/api/v1/projects/{pid}/versions/active", headers=h)
    assert resp.status_code == 200
    body = resp.json()
    assert body["version_number"] == 0
    assert body["schema"] == []
    assert body["locked"] is False


@pytest.mark.asyncio
async def test_patch_schema_creates_new_version(client):
    h, pid = await _auth_and_project(client)
    payload = {
        "schema": [
            {
                "name": "shop_name",
                "type": "string",
                "required": True,
                "description": "店名",
            }
        ],
        "global_notes": "all in JPY",
        "model_id": "gpt-4o-2024-08-06",
    }
    r1 = await client.patch(f"/api/v1/projects/{pid}/schema", json=payload, headers=h)
    assert r1.status_code == 200
    body = r1.json()
    assert body["version_number"] == 1
    assert body["schema"][0]["name"] == "shop_name"
    assert body["global_notes"] == "all in JPY"

    # active is now the new version
    r2 = await client.get(f"/api/v1/projects/{pid}/versions/active", headers=h)
    assert r2.json()["version_number"] == 1


@pytest.mark.asyncio
async def test_patch_schema_validates_field_shape(client):
    h, pid = await _auth_and_project(client)
    bad = {
        "schema": [{"name": "ShopName", "type": "string", "description": "bad"}],
        "global_notes": "",
        "model_id": "x",
    }
    resp = await client.patch(f"/api/v1/projects/{pid}/schema", json=bad, headers=h)
    assert resp.status_code == 422
```

- [ ] **Step 2: Write failing tests for lock**

`backend/tests/test_lock_workflow.py`:

```python
import pytest

from app.models.annotation import Annotation, AnnotationRole, AnnotationStatus
from app.models.document import Document
from app.models.user import User


async def _auth_and_project(client, email="lk@lk.com"):
    await client.post("/api/v1/auth/register", json={"email": email, "password": "hunter22"})
    tok = (
        await client.post("/api/v1/auth/login", json={"email": email, "password": "hunter22"})
    ).json()["access_token"]
    h = {"Authorization": f"Bearer {tok}"}
    pid = (await client.post("/api/v1/projects", json={"name": "P"}, headers=h)).json()["id"]
    return h, pid


@pytest.mark.asyncio
async def test_lock_status_initially_blocked(client):
    h, pid = await _auth_and_project(client)
    resp = await client.get(f"/api/v1/projects/{pid}/lock-status", headers=h)
    body = resp.json()
    assert body["can_lock"] is False
    assert "need at least 2" in body["reason"].lower()


@pytest.mark.asyncio
async def test_lock_succeeds_when_two_corrections_agree(client, db_session):
    h, pid = await _auth_and_project(client)
    # set schema first
    payload = {
        "schema": [
            {"name": "shop_name", "type": "string", "description": "d"},
            {"name": "total", "type": "number", "description": "d"},
        ],
        "global_notes": "",
        "model_id": "x",
    }
    await client.patch(f"/api/v1/projects/{pid}/schema", json=payload, headers=h)

    # seed two saved Annotations directly into DB whose key sets agree
    user_id = (await db_session.execute(__import__("sqlalchemy").select(User))).scalar_one().id
    for fname in ("a.pdf", "b.pdf"):
        d = Document(
            project_id=pid,
            filename=fname,
            file_path=f"/tmp/{fname}",
            mime_type="application/pdf",
            page_count=1,
            byte_size=10,
            uploaded_by=user_id,
        )
        db_session.add(d)
        await db_session.flush()
        db_session.add(
            Annotation(
                document_id=d.id,
                output=[{"shop_name": "X", "total": 1}],
                role=AnnotationRole.NONE.value,
                status=AnnotationStatus.SAVED.value,
                created_by=user_id,
                last_modified_by=user_id,
            )
        )
    await db_session.commit()

    status = await client.get(f"/api/v1/projects/{pid}/lock-status", headers=h)
    assert status.json()["can_lock"] is True

    locked = await client.post(f"/api/v1/projects/{pid}/lock", headers=h)
    assert locked.status_code == 200
    assert locked.json()["locked"] is True
```

- [ ] **Step 3: Run — expect failures**

- [ ] **Step 4: Implement `app/schemas/project_version.py`**

```python
from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.schema_field import SchemaField


class ProjectVersionOut(BaseModel):
    id: int
    project_id: int
    version_number: int
    schema: list[SchemaField] = Field(serialization_alias="schema", validation_alias="schema_snapshot")
    global_notes: str = Field(serialization_alias="global_notes", validation_alias="global_notes_snapshot")
    model_id: str = Field(serialization_alias="model_id", validation_alias="model_id_snapshot")
    locked: bool
    source: str
    created_at: datetime

    model_config = {"from_attributes": True, "populate_by_name": True}


class SchemaPatchIn(BaseModel):
    schema: list[SchemaField] = Field(default_factory=list)
    global_notes: str = ""
    model_id: str
```

- [ ] **Step 5: Implement `app/api/routes/versions.py`**

```python
from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import current_user, current_workspace_id
from app.db import get_session
from app.engine.derive_schema import _SNAKE  # noqa
from app.errors import EmergeError, ErrorCode
from app.models.annotation import Annotation, AnnotationRole, AnnotationStatus
from app.models.project import Project
from app.models.project_version import ProjectVersion, VersionSource
from app.models.user import User
from app.schemas.project_version import ProjectVersionOut, SchemaPatchIn
from app.schemas.schema_field import SchemaField

router = APIRouter(prefix="/projects/{project_id}", tags=["versions"])


async def _get_project(session, project_id, workspace_id) -> Project:
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


async def _active_version(session, p: Project) -> ProjectVersion:
    if p.active_version_id is None:
        raise EmergeError(ErrorCode.NOT_FOUND, status_code=404)
    return (
        await session.execute(
            select(ProjectVersion).where(ProjectVersion.id == p.active_version_id)
        )
    ).scalar_one()


@router.get("/versions/active", response_model=ProjectVersionOut)
async def get_active_version(
    project_id: int,
    workspace_id: int = Depends(current_workspace_id),
    session: AsyncSession = Depends(get_session),
):
    p = await _get_project(session, project_id, workspace_id)
    return await _active_version(session, p)


@router.patch("/schema", response_model=ProjectVersionOut)
async def patch_schema(
    project_id: int,
    payload: SchemaPatchIn,
    user: User = Depends(current_user),
    workspace_id: int = Depends(current_workspace_id),
    session: AsyncSession = Depends(get_session),
):
    p = await _get_project(session, project_id, workspace_id)
    parent = await _active_version(session, p)
    if parent.locked:
        raise EmergeError(ErrorCode.CONFLICT, status_code=409)
    new_v = ProjectVersion(
        project_id=p.id,
        parent_version_id=parent.id,
        version_number=parent.version_number + 1,
        schema_snapshot=[f.model_dump() for f in payload.schema],
        global_notes_snapshot=payload.global_notes,
        model_id_snapshot=payload.model_id,
        counterexample_ids=parent.counterexample_ids,
        source=VersionSource.USER_EDIT.value,
        source_metadata={"editor": "form"},
        created_by=user.id,
    )
    session.add(new_v)
    await session.flush()
    p.active_version_id = new_v.id
    await session.commit()
    await session.refresh(new_v)
    return new_v


@router.get("/lock-status")
async def lock_status(
    project_id: int,
    workspace_id: int = Depends(current_workspace_id),
    session: AsyncSession = Depends(get_session),
):
    p = await _get_project(session, project_id, workspace_id)
    rows = (
        await session.execute(
            select(Annotation).join(Annotation.__table__.c.document_id).where(False)
        )
    )  # placeholder; we'll filter via raw join below
    # join Annotation -> Document -> Project
    from app.models.document import Document

    saved = (
        await session.execute(
            select(Annotation)
            .join(Document, Document.id == Annotation.document_id)
            .where(
                Document.project_id == project_id,
                Annotation.role == AnnotationRole.NONE.value,
                Annotation.status == AnnotationStatus.SAVED.value,
            )
        )
    ).scalars().all()
    if len(saved) < 2:
        return {"can_lock": False, "reason": "Need at least 2 saved corrections."}
    keys = [set(e.keys()) for ann in saved for e in ann.output]
    if not keys:
        return {"can_lock": False, "reason": "No entities yet in any annotation."}
    union = set().union(*keys)
    intersection = set(keys[0]).intersection(*keys[1:])
    if len(union - intersection) > 1:
        return {"can_lock": False, "reason": "Field set still differs by >1 between corrections."}
    return {"can_lock": True, "reason": None}


@router.post("/lock", response_model=ProjectVersionOut)
async def lock(
    project_id: int,
    workspace_id: int = Depends(current_workspace_id),
    session: AsyncSession = Depends(get_session),
):
    p = await _get_project(session, project_id, workspace_id)
    v = await _active_version(session, p)
    status_resp = await lock_status(project_id, workspace_id, session)
    if not status_resp["can_lock"]:
        raise EmergeError(
            ErrorCode.CONFLICT, status_code=409, message_override=status_resp["reason"]
        )
    v.locked = True
    await session.commit()
    await session.refresh(v)
    return v


@router.post("/unlock", response_model=ProjectVersionOut)
async def unlock(
    project_id: int,
    workspace_id: int = Depends(current_workspace_id),
    session: AsyncSession = Depends(get_session),
):
    p = await _get_project(session, project_id, workspace_id)
    v = await _active_version(session, p)
    v.locked = False
    await session.commit()
    await session.refresh(v)
    return v
```

- [ ] **Step 6: Mount router in `app/api/v1.py`**

```python
from app.api.routes import auth, documents, extraction, me, projects, versions

api_v1.include_router(versions.router)
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `cd backend && uv run pytest tests/test_version_routes.py tests/test_lock_workflow.py -v`
Expected: `3 + 2 passed`.

- [ ] **Step 8: Commit**

```bash
git add backend/app/schemas/project_version.py backend/app/api/routes/versions.py backend/app/api/v1.py backend/tests/test_version_routes.py backend/tests/test_lock_workflow.py
git commit -m "feat(api): version read/patch + lock workflow"
```

---

## Task 13: Wire latest_prediction into Document detail

**Files:**
- Modify: `backend/app/api/routes/documents.py` (populate `latest_prediction` field placeholdered in R2)
- Modify: `backend/tests/test_document_routes.py` (post-extract assertion)

- [ ] **Step 1: Append the failing test**

```python
@pytest.mark.asyncio
async def test_document_detail_includes_latest_prediction_after_extract(
    client, tmp_path, monkeypatch, app
):
    monkeypatch.setattr("app.services.storage.settings.storage_root", str(tmp_path))
    h, pid = await _auth_and_project(client)
    did = (
        await client.post(
            f"/api/v1/projects/{pid}/documents",
            files=[("files", ("a.pdf", io.BytesIO(b"AAA"), "application/pdf"))],
            headers=h,
        )
    ).json()[0]["id"]

    from app.engine.providers import get_provider_dep
    from app.engine.providers.fake import FakeProvider

    fake = FakeProvider(canned=[[{"any": "thing"}]])
    app.dependency_overrides[get_provider_dep] = lambda: fake
    await client.post(f"/api/v1/projects/{pid}/extract", headers=h)

    resp = await client.get(f"/api/v1/projects/{pid}/documents/{did}", headers=h)
    body = resp.json()
    assert body["latest_prediction"]["output"] == [{"any": "thing"}]
    assert body["latest_prediction"]["status"] == "success"
```

- [ ] **Step 2: Run — expect failure (still null)**

- [ ] **Step 3: Update `get_document` in `app/api/routes/documents.py`**

Replace `payload["latest_prediction"] = None` with:

```python
from app.models.prediction import Prediction

latest = (
    await session.execute(
        select(Prediction)
        .where(Prediction.document_id == d.id)
        .order_by(Prediction.id.desc())
        .limit(1)
    )
).scalar_one_or_none()
payload["latest_prediction"] = (
    {
        "id": latest.id,
        "output": latest.output,
        "status": latest.status,
        "model_id": latest.model_id,
        "tokens_used": latest.tokens_used,
        "error_message": latest.error_message,
    }
    if latest
    else None
)
```

- [ ] **Step 4: Run test to verify it passes**

- [ ] **Step 5: Commit**

```bash
git add backend/app/api/routes/documents.py backend/tests/test_document_routes.py
git commit -m "feat(api): populate latest_prediction on document detail"
```

---

## R3 exit criteria

End-to-end (M1 walking skeleton):

1. `register → login → create project` (creates initial empty `ProjectVersion v0`)
2. `upload 3 PDFs → POST /extract` (SSE stream of progress; predictions written for all 3)
3. `GET document detail` returns `latest_prediction.output` from the model
4. `PATCH /schema` with a non-empty schema (creates v1)
5. `POST /extract` re-extracts using v1 (responseSchema enforced)
6. `GET /lock-status` after seeding 2 corrections returns `can_lock=true`
7. `POST /lock` locks v1; further `PATCH /schema` returns 409

Run `cd backend && uv run pytest -v` — all tests R1+R2+R3 pass.

R4 plumbs the user-correction path that produces the saved Annotations the lock heuristic relies on. R5 plugs the judge into per-prediction confidence. R7 plumbs the publish flow that exposes the locked version through `POST /extract/{api_code}`.
