# R7 — Templates & API Publish Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship the two ends of the platform: (a) **Templates** as workspace-level reusable schema knowledge with 5 system builtins, and (b) **public API publish** with key authentication, an `/extract/{api_code}` endpoint that reads the project's active version live, and `/extract/{api_code}/feedback` that creates counterexamples through R4's service.

**Architecture:**
- **Template = pure-text snapshot.** Schema descriptions, examples, enums, global_notes, recommended model. No counterexamples, no calibration, no doc binaries (spec §1.1). Template is immutable per version; "save new" creates a new row. **Fork semantics** — Project copies the Template at creation; no back-propagation.
- **Builtin templates ship as a data migration** (alembic) so they exist on every deployment. The 5 names are: `china_vat`, `us_invoice`, `japan_receipt`, `de_rechnung`, `custom_blank`. Every workspace sees them; they have `builtin=true` and are read-only.
- **API publish is just a label + a key**: `Project.api_code` (workspace-unique) becomes the public path segment; `ApiKey` rows authenticate. The public route reads `Project.active_version_id` *on every call* — single round-trip semantics per spec §7.2.
- **Key format `ek_<8-char-prefix>-<32-char-secret>`** (spec §14). Prefix is indexed for fast lookup; secret is bcrypt-compared in constant time.
- **Rate limiting** uses `slowapi` (default 60/min/key, configurable per workspace). Exceeded = 429 with the standard error envelope.
- **Public feedback** delegates to R4's `save_counterexample`. The only difference vs. the internal route is auth (key vs JWT) and rate-limit class.

**Tech Stack:** R1–R6 stack, plus `slowapi>=0.1.9` for rate limiting.

**Spec sections covered:** §1.1 (Template asset), §6 (Templates lifecycle, fork semantics, 5 builtins), §7 (publish, key, public routes, feedback), §14 (key prefix `ek_`, public route shape).

**Depends on:** R3 (ProjectVersion exists; active_version_id wired); R4 (`save_counterexample` service exists). Can run in parallel with R5/R6 — does not depend on them.

---

## File Structure

```
backend/app/
├── models/
│   ├── template.py                # Template table
│   └── api_key.py                 # ApiKey table
├── schemas/
│   ├── template.py                # TemplateIn/Out, ProjectFromTemplateIn
│   └── api_key.py                 # ApiKeyOut, PublishIn, ExtractFeedbackIn
├── services/
│   ├── api_key.py                 # generate_key, verify_key
│   └── ratelimit.py               # slowapi limiter + key extractor
├── api/routes/
│   ├── templates.py               # GET / POST templates; save-as
│   ├── publish.py                 # POST /projects/{pid}/publish + ApiKey CRUD
│   └── public.py                  # POST /extract/{api_code} + feedback
└── alembic/versions/
    ├── 0012_template.py
    ├── 0013_project_template_fk.py # tighten Project.template_id → FK template.id
    ├── 0014_api_key.py
    └── 0015_seed_builtin_templates.py
```

Tests:

```
backend/tests/
├── test_template_model.py
├── test_template_routes.py
├── test_builtin_seed.py
├── test_api_key.py
├── test_publish_routes.py
├── test_public_extract.py
├── test_public_feedback.py
└── test_ratelimit.py
```

---

## Task 1: Template model + migration

**Files:**
- Create: `backend/app/models/template.py`
- Modify: `backend/app/models/__init__.py`
- Create: `backend/alembic/versions/0012_template.py`
- Create: `backend/alembic/versions/0013_project_template_fk.py`
- Create: `backend/tests/test_template_model.py`

`(name, version)` is unique within a workspace (or globally for builtins). `schema_json` is the immutable snapshot.

- [ ] **Step 1: Write the failing test**

```python
import pytest

from app.models.template import Template
from app.models.user import User
from app.models.workspace import Workspace


@pytest.mark.asyncio
async def test_template_persists(db_session):
    user = User(email="tp@tp.com", password_hash="x")
    db_session.add(user)
    await db_session.flush()
    ws = Workspace(name="W", owner_id=user.id)
    db_session.add(ws)
    await db_session.flush()

    t = Template(
        workspace_id=ws.id,
        name="japan_receipts",
        description="japan receipts",
        version=1,
        schema_json=[{"name": "shop_name", "type": "string", "description": "店名"}],
        global_notes="all in JPY",
        recommended_model_id="claude-opus-4-7",
        created_by=user.id,
        builtin=False,
    )
    db_session.add(t)
    await db_session.commit()
    assert t.id is not None


@pytest.mark.asyncio
async def test_builtin_template_has_null_workspace(db_session):
    """Builtins are visible to every workspace; workspace_id is NULL."""
    user = User(email="bi@bi.com", password_hash="x")
    db_session.add(user)
    await db_session.flush()
    t = Template(
        workspace_id=None,
        name="china_vat",
        description="builtin",
        version=1,
        schema_json=[],
        global_notes="",
        recommended_model_id="m",
        created_by=user.id,
        builtin=True,
    )
    db_session.add(t)
    await db_session.commit()
    assert t.workspace_id is None
```

- [ ] **Step 2: Run — expect ImportError**

- [ ] **Step 3: Implement `app/models/template.py`**

```python
from sqlalchemy import JSON, Boolean, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class Template(Base, TimestampMixin):
    __tablename__ = "templates"
    __table_args__ = (
        UniqueConstraint(
            "workspace_id", "name", "version", name="uq_template_workspace_name_version"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    workspace_id: Mapped[int | None] = mapped_column(
        ForeignKey("workspaces.id"), nullable=True, index=True
    )  # NULL for builtins
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    schema_json: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    global_notes: Mapped[str] = mapped_column(Text, nullable=False, default="")
    recommended_model_id: Mapped[str] = mapped_column(String(128), nullable=False)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    builtin: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
```

Re-export.

- [ ] **Step 4: Run test to verify it passes**

- [ ] **Step 5: Generate + apply migrations**

```bash
cd backend && uv run alembic revision --autogenerate -m "template table"
# rename to 0012_template.py
uv run alembic revision --autogenerate -m "project template fk"
# rename to 0013_project_template_fk.py — adds FK from Project.template_id to Template.id
uv run alembic upgrade head
```

- [ ] **Step 6: Commit**

```bash
git add backend/app/models/template.py backend/app/models/__init__.py backend/alembic/versions/0012_template.py backend/alembic/versions/0013_project_template_fk.py backend/tests/test_template_model.py
git commit -m "feat(backend): add Template model + 0012/0013 migrations"
```

---

## Task 2: Template list + get endpoints

**Files:**
- Create: `backend/app/schemas/template.py`
- Create: `backend/app/api/routes/templates.py`
- Modify: `backend/app/api/v1.py` (mount)
- Create: `backend/tests/test_template_routes.py`

`GET /api/v1/templates` returns: builtins (workspace_id IS NULL) + workspace-owned templates. `GET /templates/{id}` returns a single template if visible to the user's workspace.

- [ ] **Step 1: Write failing tests**

```python
import pytest


async def _auth(client, email="tt@tt.com"):
    await client.post("/api/v1/auth/register", json={"email": email, "password": "hunter22"})
    tok = (
        await client.post("/api/v1/auth/login", json={"email": email, "password": "hunter22"})
    ).json()["access_token"]
    return {"Authorization": f"Bearer {tok}"}


@pytest.mark.asyncio
async def test_list_templates_includes_builtins(client, db_session):
    h = await _auth(client)
    from app.models.template import Template
    from app.models.user import User
    from sqlalchemy import select

    user_id = (await db_session.execute(select(User))).scalar_one().id
    db_session.add(
        Template(
            workspace_id=None,
            name="china_vat",
            description="builtin",
            version=1,
            schema_json=[],
            global_notes="",
            recommended_model_id="m",
            created_by=user_id,
            builtin=True,
        )
    )
    await db_session.commit()
    resp = await client.get("/api/v1/templates", headers=h)
    body = resp.json()
    assert any(t["name"] == "china_vat" and t["builtin"] is True for t in body)


@pytest.mark.asyncio
async def test_template_isolated_per_workspace(client, db_session):
    """Template owned by one workspace is not visible to another."""
    h1 = await _auth(client, "u1@u1.com")
    h2 = await _auth(client, "u2@u2.com")
    from app.models.template import Template
    from app.models.user import User
    from sqlalchemy import select

    rows = (await db_session.execute(select(User).order_by(User.id))).scalars().all()
    user1, user2 = rows[0], rows[1]
    from app.models.workspace import WorkspaceMembership

    ws1 = (
        await db_session.execute(
            select(WorkspaceMembership).where(WorkspaceMembership.user_id == user1.id)
        )
    ).scalar_one().workspace_id
    db_session.add(
        Template(
            workspace_id=ws1,
            name="custom",
            description="d",
            version=1,
            schema_json=[],
            global_notes="",
            recommended_model_id="m",
            created_by=user1.id,
            builtin=False,
        )
    )
    await db_session.commit()
    resp = await client.get("/api/v1/templates", headers=h2)
    assert all(t["name"] != "custom" for t in resp.json())
```

- [ ] **Step 2: Run — expect 404**

- [ ] **Step 3: Implement `app/schemas/template.py`**

```python
from datetime import datetime

from pydantic import BaseModel

from app.schemas.schema_field import SchemaField


class TemplateOut(BaseModel):
    id: int
    workspace_id: int | None
    name: str
    description: str
    version: int
    schema: list[SchemaField]
    global_notes: str
    recommended_model_id: str
    builtin: bool
    created_at: datetime

    @classmethod
    def from_orm_row(cls, row) -> "TemplateOut":
        return cls(
            id=row.id,
            workspace_id=row.workspace_id,
            name=row.name,
            description=row.description,
            version=row.version,
            schema=[SchemaField(**f) for f in row.schema_json],
            global_notes=row.global_notes,
            recommended_model_id=row.recommended_model_id,
            builtin=row.builtin,
            created_at=row.created_at,
        )


class TemplateSaveAsIn(BaseModel):
    name: str
    description: str = ""
    create_new_version: bool = False
```

- [ ] **Step 4: Implement `app/api/routes/templates.py`**

```python
from fastapi import APIRouter, Depends
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import current_workspace_id
from app.db import get_session
from app.errors import EmergeError, ErrorCode
from app.models.template import Template
from app.schemas.template import TemplateOut

router = APIRouter(prefix="/templates", tags=["templates"])


@router.get("", response_model=list[TemplateOut])
async def list_templates(
    workspace_id: int = Depends(current_workspace_id),
    session: AsyncSession = Depends(get_session),
):
    rows = (
        await session.execute(
            select(Template)
            .where(or_(Template.workspace_id.is_(None), Template.workspace_id == workspace_id))
            .order_by(Template.builtin.desc(), Template.id.desc())
        )
    ).scalars().all()
    return [TemplateOut.from_orm_row(r) for r in rows]


@router.get("/{template_id}", response_model=TemplateOut)
async def get_template(
    template_id: int,
    workspace_id: int = Depends(current_workspace_id),
    session: AsyncSession = Depends(get_session),
):
    row = (
        await session.execute(
            select(Template).where(
                Template.id == template_id,
                or_(Template.workspace_id.is_(None), Template.workspace_id == workspace_id),
            )
        )
    ).scalar_one_or_none()
    if row is None:
        raise EmergeError(ErrorCode.NOT_FOUND, status_code=404)
    return TemplateOut.from_orm_row(row)
```

Mount in `app/api/v1.py`:

```python
from app.api.routes import templates

api_v1.include_router(templates.router)
```

- [ ] **Step 5: Run tests to verify they pass**

- [ ] **Step 6: Commit**

```bash
git add backend/app/schemas/template.py backend/app/api/routes/templates.py backend/app/api/v1.py backend/tests/test_template_routes.py
git commit -m "feat(api): template list/get with builtin + workspace visibility"
```

---

## Task 3: Save-as-Template + Project from Template

**Files:**
- Modify: `backend/app/api/routes/templates.py` (POST `/projects/{pid}/save-as-template`)
- Modify: `backend/app/api/routes/projects.py` (accept `template_id` on create)
- Modify: `backend/app/schemas/project.py` (add `template_id` optional)
- Modify: `backend/tests/test_project_routes.py` (template fork test)
- Modify: `backend/tests/test_template_routes.py` (save-as test)

- [ ] **Step 1: Append failing tests**

In `test_template_routes.py`:

```python
@pytest.mark.asyncio
async def test_save_as_template_promotes_active_schema(client):
    h = await _auth(client, "saveas@s.com")
    pid = (await client.post("/api/v1/projects", json={"name": "P"}, headers=h)).json()["id"]
    await client.patch(
        f"/api/v1/projects/{pid}/schema",
        json={
            "schema": [{"name": "shop_name", "type": "string", "description": "店名"}],
            "global_notes": "JPY",
            "model_id": "m",
        },
        headers=h,
    )
    resp = await client.post(
        f"/api/v1/projects/{pid}/save-as-template",
        json={"name": "japan_receipts", "description": "from project P"},
        headers=h,
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["name"] == "japan_receipts"
    assert body["version"] == 1
    assert body["schema"][0]["name"] == "shop_name"


@pytest.mark.asyncio
async def test_save_as_creates_new_version_when_name_exists(client):
    h = await _auth(client, "sv@s.com")
    pid = (await client.post("/api/v1/projects", json={"name": "P"}, headers=h)).json()["id"]
    payload = {"name": "tplA", "description": ""}
    r1 = await client.post(
        f"/api/v1/projects/{pid}/save-as-template",
        json={**payload, "create_new_version": False},
        headers=h,
    )
    assert r1.json()["version"] == 1
    r2 = await client.post(
        f"/api/v1/projects/{pid}/save-as-template",
        json={**payload, "create_new_version": True},
        headers=h,
    )
    assert r2.json()["version"] == 2
```

In `test_project_routes.py`:

```python
@pytest.mark.asyncio
async def test_create_project_from_template_forks_schema(client, db_session):
    h = await _auth(client, "fork@f.com")
    # seed a builtin template
    from app.models.template import Template
    from app.models.user import User
    from sqlalchemy import select

    user_id = (await db_session.execute(select(User))).scalar_one().id
    db_session.add(
        Template(
            workspace_id=None,
            name="builtin_for_fork",
            description="d",
            version=1,
            schema_json=[
                {"name": "shop_name", "type": "string", "description": "店名"},
            ],
            global_notes="hi",
            recommended_model_id="m1",
            created_by=user_id,
            builtin=True,
        )
    )
    await db_session.commit()
    tpl_id = (
        await db_session.execute(select(Template).where(Template.name == "builtin_for_fork"))
    ).scalar_one().id

    resp = await client.post(
        "/api/v1/projects",
        json={"name": "P", "template_id": tpl_id},
        headers=h,
    )
    body = resp.json()
    pid = body["id"]
    assert body["template_id"] == tpl_id

    active = (
        await client.get(f"/api/v1/projects/{pid}/versions/active", headers=h)
    ).json()
    assert active["schema"][0]["name"] == "shop_name"
    assert active["global_notes"] == "hi"
    assert active["model_id"] == "m1"
```

- [ ] **Step 2: Run — expect failures**

- [ ] **Step 3: Update `app/schemas/project.py`**

```python
class ProjectIn(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    template_id: int | None = None
```

- [ ] **Step 4: Update `app/api/routes/projects.py` `create_project`**

After parsing `payload`, if `template_id` is set, look up the Template (must be visible: workspace_id IS NULL or == current_workspace_id), and use its schema as the initial `ProjectVersion v0` instead of empty.

```python
from sqlalchemy import or_

from app.models.template import Template


# inside create_project:
schema_json: list = []
global_notes = ""
model_id = "claude-opus-4-7"
template_id = payload.template_id
if template_id is not None:
    tpl = (
        await session.execute(
            select(Template).where(
                Template.id == template_id,
                or_(Template.workspace_id.is_(None), Template.workspace_id == workspace_id),
            )
        )
    ).scalar_one_or_none()
    if tpl is None:
        raise EmergeError(ErrorCode.NOT_FOUND, status_code=404)
    schema_json = tpl.schema_json
    global_notes = tpl.global_notes
    model_id = tpl.recommended_model_id

p = Project(
    workspace_id=workspace_id,
    name=payload.name,
    created_by=user.id,
    template_id=template_id,
)
session.add(p)
await session.flush()

v = ProjectVersion(
    project_id=p.id,
    version_number=0,
    schema_snapshot=schema_json,
    global_notes_snapshot=global_notes,
    model_id_snapshot=model_id,
    counterexample_ids=[],
    source=VersionSource.INITIAL.value,
    source_metadata={"reason": "project_created", "from_template_id": template_id},
    created_by=user.id,
)
session.add(v)
await session.flush()
p.active_version_id = v.id
await session.commit()
await session.refresh(p)
return ProjectOut.model_validate(p)
```

- [ ] **Step 5: Add save-as-template endpoint to `app/api/routes/templates.py`**

```python
from fastapi import status
from sqlalchemy import desc

from app.core.deps import current_user
from app.models.project import Project
from app.models.project_version import ProjectVersion
from app.models.user import User
from app.schemas.template import TemplateSaveAsIn


@router.post("/projects/{project_id}/save-as-template", response_model=TemplateOut, status_code=status.HTTP_201_CREATED)
async def save_as_template(
    project_id: int,
    payload: TemplateSaveAsIn,
    user: User = Depends(current_user),
    workspace_id: int = Depends(current_workspace_id),
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
    if project.active_version_id is None:
        raise EmergeError(ErrorCode.CONFLICT, status_code=409)
    v = (
        await session.execute(
            select(ProjectVersion).where(ProjectVersion.id == project.active_version_id)
        )
    ).scalar_one()

    existing = (
        await session.execute(
            select(Template)
            .where(
                Template.workspace_id == workspace_id,
                Template.name == payload.name,
            )
            .order_by(desc(Template.version))
            .limit(1)
        )
    ).scalar_one_or_none()
    if existing is None:
        next_version = 1
    elif payload.create_new_version:
        next_version = existing.version + 1
    else:
        raise EmergeError(
            ErrorCode.CONFLICT,
            status_code=409,
            message_override=f"Template '{payload.name}' already exists; pass create_new_version=true to add v{existing.version + 1}",
        )

    tpl = Template(
        workspace_id=workspace_id,
        name=payload.name,
        description=payload.description,
        version=next_version,
        schema_json=v.schema_snapshot,
        global_notes=v.global_notes_snapshot,
        recommended_model_id=v.model_id_snapshot,
        created_by=user.id,
        builtin=False,
    )
    session.add(tpl)
    await session.commit()
    await session.refresh(tpl)
    return TemplateOut.from_orm_row(tpl)
```

The save-as-template route lives under `/api/v1/templates/projects/{project_id}/save-as-template`; mount as part of templates router (no separate router file needed).

- [ ] **Step 6: Run tests to verify they pass**

- [ ] **Step 7: Commit**

```bash
git add backend/app/api/routes/projects.py backend/app/api/routes/templates.py backend/app/schemas/project.py backend/tests/test_project_routes.py backend/tests/test_template_routes.py
git commit -m "feat(api): create project from template + save-as-template"
```

---

## Task 4: Builtin templates seed migration

**Files:**
- Create: `backend/alembic/versions/0015_seed_builtin_templates.py`
- Create: `backend/tests/test_builtin_seed.py`

Five rows inserted as a data migration. Each carries a curated schema reflecting common fields with English description text.

- [ ] **Step 1: Write the failing test**

```python
import pytest
from sqlalchemy import select

from app.models.template import Template


@pytest.mark.asyncio
async def test_five_builtins_present(db_session):
    rows = (
        await db_session.execute(select(Template).where(Template.builtin.is_(True)))
    ).scalars().all()
    names = {r.name for r in rows}
    assert names >= {"china_vat", "us_invoice", "japan_receipt", "de_rechnung", "custom_blank"}


@pytest.mark.asyncio
async def test_custom_blank_has_empty_schema(db_session):
    row = (
        await db_session.execute(select(Template).where(Template.name == "custom_blank"))
    ).scalar_one()
    assert row.schema_json == []
    assert row.global_notes == ""


@pytest.mark.asyncio
async def test_japan_receipt_has_shop_name_field(db_session):
    row = (
        await db_session.execute(select(Template).where(Template.name == "japan_receipt"))
    ).scalar_one()
    names = {f["name"] for f in row.schema_json}
    assert "shop_name" in names
```

The conftest `db_engine` fixture creates an in-memory DB and runs `Base.metadata.create_all` — that does not run alembic migrations. The seed migration must therefore be replicated as a fixture for tests, OR we ship a thin "ensure_builtins" startup function that the conftest can call. Choose the latter: cleaner and lets prod code run independent of alembic ordering.

- [ ] **Step 2: Implement `app/services/builtin_templates.py`**

```python
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.template import Template
from app.models.user import User

BUILTINS = [
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
    """Idempotent: inserts any missing builtin Templates. Called on app startup and from
    test fixtures so unit tests can assert their presence."""
    user = (await session.execute(select(User).order_by(User.id).limit(1))).scalar_one_or_none()
    creator_id = user.id if user else 0
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
                recommended_model_id="claude-opus-4-7",
                created_by=creator_id,
                builtin=True,
            )
        )
    await session.commit()
```

- [ ] **Step 3: Wire into app startup**

In `app/main.py`:

```python
from contextlib import asynccontextmanager

from app.db import SessionFactory
from app.services.builtin_templates import seed_builtin_templates


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with SessionFactory() as session:
        try:
            await seed_builtin_templates(session)
        except Exception:
            # leave seeding silent if no users yet — happens before first registration
            pass
    yield


def create_app() -> FastAPI:
    app = FastAPI(title="emerge", version="0.1.0", lifespan=lifespan)
    ...
```

- [ ] **Step 4: Run startup-side seeding from test conftest**

In `backend/tests/conftest.py`, modify the `db_session` fixture to seed builtins after table creation:

```python
@pytest_asyncio.fixture
async def db_session(db_engine) -> AsyncIterator[AsyncSession]:
    factory = async_sessionmaker(db_engine, expire_on_commit=False)
    async with factory() as session:
        from app.services.builtin_templates import seed_builtin_templates

        await seed_builtin_templates(session)
        yield session
```

Note: when `seed_builtin_templates` runs against an empty DB before any user exists, `creator_id` falls back to 0. SQLite without strict FK enforcement accepts this; alembic in prod runs after at least bootstrap migration. If FK is strict in test environment, adapt to skip seeding when no user exists, or ensure conftest creates a system user first.

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd backend && uv run pytest tests/test_builtin_seed.py -v`

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/builtin_templates.py backend/app/main.py backend/tests/conftest.py backend/tests/test_builtin_seed.py
git commit -m "feat(backend): seed 5 builtin templates idempotently on startup + in tests"
```

Optional: also add a no-op alembic migration `0015_seed_builtin_templates.py` that calls `seed_builtin_templates` for production — but the startup hook is authoritative.

---

## Task 5: ApiKey model + key service

**Files:**
- Create: `backend/app/models/api_key.py`
- Modify: `backend/app/models/__init__.py`
- Create: `backend/alembic/versions/0014_api_key.py`
- Create: `backend/app/services/api_key.py`
- Create: `backend/tests/test_api_key.py`

Key format: `ek_<8-prefix>-<32-secret>`. Prefix indexed; secret bcrypt-hashed; constant-time check on lookup.

- [ ] **Step 1: Implement `app/models/api_key.py`**

```python
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class ApiKey(Base, TimestampMixin):
    __tablename__ = "api_keys"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(128), nullable=False, default="default")
    prefix: Mapped[str] = mapped_column(String(8), nullable=False, index=True)
    key_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
```

Re-export.

- [ ] **Step 2: Generate + apply migration**

```bash
cd backend && uv run alembic revision --autogenerate -m "api_key table"
uv run alembic upgrade head
```

- [ ] **Step 3: Write the failing tests**

`backend/tests/test_api_key.py`:

```python
import pytest

from app.services.api_key import generate_api_key, verify_api_key


def test_generate_format():
    key, prefix, hashed = generate_api_key()
    assert key.startswith(f"ek_{prefix}-")
    assert len(prefix) == 8
    assert len(key.split("-", 1)[1]) == 32
    assert hashed != key


def test_verify_round_trip():
    key, prefix, hashed = generate_api_key()
    assert verify_api_key(key, prefix=prefix, key_hash=hashed) is True
    assert verify_api_key(key + "x", prefix=prefix, key_hash=hashed) is False


def test_verify_wrong_prefix():
    key, _, hashed = generate_api_key()
    assert verify_api_key(key, prefix="WRONGPRE", key_hash=hashed) is False
```

- [ ] **Step 4: Implement `app/services/api_key.py`**

```python
import secrets

import bcrypt


def _gen_token(n: int) -> str:
    alphabet = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
    return "".join(secrets.choice(alphabet) for _ in range(n))


def generate_api_key() -> tuple[str, str, str]:
    """Returns (full_key, prefix, hash). Caller stores prefix + hash."""
    prefix = _gen_token(8)
    secret = _gen_token(32)
    full = f"ek_{prefix}-{secret}"
    hashed = bcrypt.hashpw(secret.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
    return full, prefix, hashed


def verify_api_key(presented: str, *, prefix: str, key_hash: str) -> bool:
    if not presented.startswith("ek_") or "-" not in presented:
        return False
    pres_prefix, pres_secret = presented.removeprefix("ek_").split("-", 1)
    if not secrets.compare_digest(pres_prefix.encode(), prefix.encode()):
        return False
    try:
        return bcrypt.checkpw(pres_secret.encode("utf-8"), key_hash.encode("utf-8"))
    except (ValueError, KeyError):
        return False


def parse_prefix(presented: str) -> str | None:
    if not presented.startswith("ek_") or "-" not in presented:
        return None
    pres_prefix, _ = presented.removeprefix("ek_").split("-", 1)
    return pres_prefix
```

- [ ] **Step 5: Run test to verify it passes**

- [ ] **Step 6: Commit**

```bash
git add backend/app/models/api_key.py backend/app/models/__init__.py backend/alembic/versions/0014_api_key.py backend/app/services/api_key.py backend/tests/test_api_key.py
git commit -m "feat(backend): ApiKey model + generate/verify with constant-time prefix match"
```

---

## Task 6: Publish + key CRUD endpoints

**Files:**
- Create: `backend/app/schemas/api_key.py`
- Create: `backend/app/api/routes/publish.py`
- Modify: `backend/app/api/v1.py` (mount)
- Create: `backend/tests/test_publish_routes.py`

Routes:
- `POST /api/v1/projects/{pid}/publish` body `{api_code}` → sets `Project.api_code` (must be workspace-unique kebab-friendly slug); requires active version locked; sets `api_published_at`.
- `POST /api/v1/projects/{pid}/unpublish`
- `POST /api/v1/projects/{pid}/api-keys` body `{name}` → returns full key in plaintext **once**; persists prefix + hash.
- `GET /api/v1/projects/{pid}/api-keys` → list (no secrets, just prefix + name + last_used_at).
- `DELETE /api/v1/projects/{pid}/api-keys/{kid}` → soft-delete (sets `deleted_at`).

- [ ] **Step 1: Write failing tests**

```python
import pytest


async def _auth_and_project(client) -> tuple[dict, int]:
    await client.post("/api/v1/auth/register", json={"email": "pb@pb.com", "password": "hunter22"})
    tok = (
        await client.post("/api/v1/auth/login", json={"email": "pb@pb.com", "password": "hunter22"})
    ).json()["access_token"]
    h = {"Authorization": f"Bearer {tok}"}
    pid = (await client.post("/api/v1/projects", json={"name": "P"}, headers=h)).json()["id"]
    return h, pid


@pytest.mark.asyncio
async def test_publish_requires_locked_version(client):
    h, pid = await _auth_and_project(client)
    resp = await client.post(
        f"/api/v1/projects/{pid}/publish", json={"api_code": "ja-rcpt"}, headers=h
    )
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_publish_succeeds_after_lock(client, db_session):
    h, pid = await _auth_and_project(client)
    # set schema, seed two corrections to allow lock
    await client.patch(
        f"/api/v1/projects/{pid}/schema",
        json={
            "schema": [{"name": "shop_name", "type": "string", "description": "店名"}],
            "global_notes": "",
            "model_id": "m",
        },
        headers=h,
    )
    from app.models.annotation import Annotation, AnnotationRole, AnnotationStatus
    from app.models.document import Document
    from app.models.user import User
    from sqlalchemy import select

    user_id = (await db_session.execute(select(User))).scalar_one().id
    for fn in ("a.pdf", "b.pdf"):
        d = Document(
            project_id=pid,
            filename=fn,
            file_path="/tmp/x",
            mime_type="application/pdf",
            page_count=1,
            byte_size=1,
            uploaded_by=user_id,
        )
        db_session.add(d)
        await db_session.flush()
        db_session.add(
            Annotation(
                document_id=d.id,
                output=[{"shop_name": "X"}],
                role=AnnotationRole.NONE.value,
                status=AnnotationStatus.SAVED.value,
                created_by=user_id,
                last_modified_by=user_id,
            )
        )
    await db_session.commit()
    await client.post(f"/api/v1/projects/{pid}/lock", headers=h)

    resp = await client.post(
        f"/api/v1/projects/{pid}/publish", json={"api_code": "ja-rcpt"}, headers=h
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["api_code"] == "ja-rcpt"
    assert body["api_published_at"] is not None


@pytest.mark.asyncio
async def test_create_api_key_returns_plaintext_once(client, db_session):
    h, pid = await _auth_and_project(client)
    resp = await client.post(
        f"/api/v1/projects/{pid}/api-keys", json={"name": "default"}, headers=h
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["key"].startswith("ek_")
    assert "key_hash" not in body

    # subsequent list does NOT return the secret
    listing = (await client.get(f"/api/v1/projects/{pid}/api-keys", headers=h)).json()
    assert len(listing) == 1
    assert "key" not in listing[0]
    assert listing[0]["prefix"] == body["prefix"]


@pytest.mark.asyncio
async def test_api_code_unique_per_workspace(client, db_session):
    h, pid = await _auth_and_project(client)
    await client.patch(
        f"/api/v1/projects/{pid}/schema",
        json={
            "schema": [{"name": "shop_name", "type": "string", "description": "店名"}],
            "global_notes": "",
            "model_id": "m",
        },
        headers=h,
    )
    # bypass lock for this test by directly setting locked=True
    from app.models.project import Project
    from app.models.project_version import ProjectVersion
    from sqlalchemy import select

    proj = (await db_session.execute(select(Project).where(Project.id == pid))).scalar_one()
    v = (
        await db_session.execute(
            select(ProjectVersion).where(ProjectVersion.id == proj.active_version_id)
        )
    ).scalar_one()
    v.locked = True
    await db_session.commit()

    r1 = await client.post(
        f"/api/v1/projects/{pid}/publish", json={"api_code": "shared-code"}, headers=h
    )
    assert r1.status_code == 200
    pid2 = (await client.post("/api/v1/projects", json={"name": "P2"}, headers=h)).json()["id"]
    # again lock
    proj2 = (await db_session.execute(select(Project).where(Project.id == pid2))).scalar_one()
    v2 = (
        await db_session.execute(
            select(ProjectVersion).where(ProjectVersion.id == proj2.active_version_id)
        )
    ).scalar_one()
    v2.locked = True
    await db_session.commit()
    r2 = await client.post(
        f"/api/v1/projects/{pid2}/publish", json={"api_code": "shared-code"}, headers=h
    )
    assert r2.status_code == 409
```

- [ ] **Step 2: Run — expect 404**

- [ ] **Step 3: Implement `app/schemas/api_key.py`**

```python
import re
from datetime import datetime

from pydantic import BaseModel, Field, field_validator

_API_CODE = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,62}[a-z0-9])?$")


class PublishIn(BaseModel):
    api_code: str

    @field_validator("api_code")
    @classmethod
    def _check(cls, v):
        if not _API_CODE.match(v):
            raise ValueError("api_code must be lowercase alphanumeric with hyphens, 1-64 chars")
        return v


class ApiKeyIn(BaseModel):
    name: str = Field(default="default", min_length=1, max_length=128)


class ApiKeyOnceOut(BaseModel):
    id: int
    prefix: str
    name: str
    key: str  # plaintext, returned only on create


class ApiKeyOut(BaseModel):
    id: int
    prefix: str
    name: str
    last_used_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}
```

- [ ] **Step 4: Implement `app/api/routes/publish.py`**

```python
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import current_user, current_workspace_id
from app.db import get_session
from app.errors import EmergeError, ErrorCode
from app.models.api_key import ApiKey
from app.models.project import Project
from app.models.project_version import ProjectVersion
from app.models.user import User
from app.schemas.api_key import ApiKeyIn, ApiKeyOnceOut, ApiKeyOut, PublishIn
from app.schemas.project import ProjectOut
from app.services.api_key import generate_api_key

router = APIRouter(prefix="/projects/{project_id}", tags=["publish"])


async def _project(session, project_id, workspace_id) -> Project:
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


@router.post("/publish", response_model=ProjectOut)
async def publish(
    project_id: int,
    payload: PublishIn,
    workspace_id: int = Depends(current_workspace_id),
    session: AsyncSession = Depends(get_session),
):
    p = await _project(session, project_id, workspace_id)
    if p.active_version_id is None:
        raise EmergeError(ErrorCode.CONFLICT, status_code=409)
    v = (
        await session.execute(
            select(ProjectVersion).where(ProjectVersion.id == p.active_version_id)
        )
    ).scalar_one()
    if not v.locked:
        raise EmergeError(
            ErrorCode.CONFLICT,
            status_code=409,
            message_override="Active version must be locked before publishing.",
        )
    # check api_code uniqueness within workspace
    clash = (
        await session.execute(
            select(Project).where(
                Project.workspace_id == workspace_id,
                Project.api_code == payload.api_code,
                Project.id != p.id,
            )
        )
    ).scalar_one_or_none()
    if clash is not None:
        raise EmergeError(ErrorCode.CONFLICT, status_code=409)

    p.api_code = payload.api_code
    p.api_published_at = datetime.now(tz=timezone.utc)
    await session.commit()
    await session.refresh(p)
    return ProjectOut.model_validate(p)


@router.post("/unpublish", response_model=ProjectOut)
async def unpublish(
    project_id: int,
    workspace_id: int = Depends(current_workspace_id),
    session: AsyncSession = Depends(get_session),
):
    p = await _project(session, project_id, workspace_id)
    p.api_code = None
    p.api_published_at = None
    await session.commit()
    await session.refresh(p)
    return ProjectOut.model_validate(p)


@router.post(
    "/api-keys", response_model=ApiKeyOnceOut, status_code=status.HTTP_201_CREATED
)
async def create_api_key(
    project_id: int,
    payload: ApiKeyIn,
    user: User = Depends(current_user),
    workspace_id: int = Depends(current_workspace_id),
    session: AsyncSession = Depends(get_session),
):
    await _project(session, project_id, workspace_id)
    full, prefix, hashed = generate_api_key()
    row = ApiKey(
        project_id=project_id,
        name=payload.name,
        prefix=prefix,
        key_hash=hashed,
        created_by=user.id,
    )
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return ApiKeyOnceOut(id=row.id, prefix=prefix, name=row.name, key=full)


@router.get("/api-keys", response_model=list[ApiKeyOut])
async def list_api_keys(
    project_id: int,
    workspace_id: int = Depends(current_workspace_id),
    session: AsyncSession = Depends(get_session),
):
    await _project(session, project_id, workspace_id)
    rows = (
        await session.execute(
            select(ApiKey)
            .where(ApiKey.project_id == project_id, ApiKey.deleted_at.is_(None))
            .order_by(ApiKey.id.desc())
        )
    ).scalars().all()
    return [ApiKeyOut.model_validate(r) for r in rows]


@router.delete("/api-keys/{key_id}", response_model=ApiKeyOut)
async def revoke_api_key(
    project_id: int,
    key_id: int,
    workspace_id: int = Depends(current_workspace_id),
    session: AsyncSession = Depends(get_session),
):
    await _project(session, project_id, workspace_id)
    row = (
        await session.execute(
            select(ApiKey).where(ApiKey.id == key_id, ApiKey.project_id == project_id)
        )
    ).scalar_one_or_none()
    if row is None:
        raise EmergeError(ErrorCode.NOT_FOUND, status_code=404)
    row.deleted_at = datetime.now(tz=timezone.utc)
    await session.commit()
    await session.refresh(row)
    return ApiKeyOut.model_validate(row)
```

Mount in `app/api/v1.py`:

```python
from app.api.routes import publish

api_v1.include_router(publish.router)
```

- [ ] **Step 5: Run tests to verify they pass**

Expected: `4 passed`.

- [ ] **Step 6: Commit**

```bash
git add backend/app/schemas/api_key.py backend/app/api/routes/publish.py backend/app/api/v1.py backend/tests/test_publish_routes.py
git commit -m "feat(api): publish + ApiKey CRUD endpoints"
```

---

## Task 7: Public extract endpoint

**Files:**
- Create: `backend/app/api/routes/public.py`
- Modify: `backend/app/main.py` (mount `public.router` *outside* `/api/v1` per spec §14)
- Create: `backend/tests/test_public_extract.py`

Public route is `POST /extract/{api_code}` (no `/api/v1` prefix). Auth = `X-Api-Key` header only; no JWT.

- [ ] **Step 1: Write the failing tests**

```python
import io

import pytest


async def _setup_published_project(client, db_session, monkeypatch, tmp_path) -> tuple[str, str]:
    """Returns (api_code, api_key)."""
    monkeypatch.setattr("app.services.storage.settings.storage_root", str(tmp_path))
    await client.post("/api/v1/auth/register", json={"email": "px@px.com", "password": "hunter22"})
    tok = (
        await client.post("/api/v1/auth/login", json={"email": "px@px.com", "password": "hunter22"})
    ).json()["access_token"]
    h = {"Authorization": f"Bearer {tok}"}
    pid = (await client.post("/api/v1/projects", json={"name": "P"}, headers=h)).json()["id"]
    await client.patch(
        f"/api/v1/projects/{pid}/schema",
        json={
            "schema": [{"name": "shop_name", "type": "string", "description": "店名"}],
            "global_notes": "",
            "model_id": "m",
        },
        headers=h,
    )
    # bypass lock for test
    from app.models.project import Project
    from app.models.project_version import ProjectVersion
    from sqlalchemy import select

    proj = (await db_session.execute(select(Project).where(Project.id == pid))).scalar_one()
    v = (
        await db_session.execute(
            select(ProjectVersion).where(ProjectVersion.id == proj.active_version_id)
        )
    ).scalar_one()
    v.locked = True
    await db_session.commit()

    await client.post(
        f"/api/v1/projects/{pid}/publish", json={"api_code": "test-receipts"}, headers=h
    )
    key = (
        await client.post(
            f"/api/v1/projects/{pid}/api-keys", json={"name": "default"}, headers=h
        )
    ).json()["key"]
    return "test-receipts", key


@pytest.mark.asyncio
async def test_extract_returns_entities(client, db_session, app, tmp_path, monkeypatch):
    api_code, key = await _setup_published_project(client, db_session, monkeypatch, tmp_path)

    from app.engine.providers import get_provider_dep
    from app.engine.providers.fake import FakeProvider

    fake = FakeProvider(canned=[[{"shop_name": "ABC"}]])
    app.dependency_overrides[get_provider_dep] = lambda: fake

    resp = await client.post(
        f"/extract/{api_code}",
        files=[("file", ("a.pdf", io.BytesIO(b"PDF"), "application/pdf"))],
        headers={"X-Api-Key": key},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["entities"] == [{"shop_name": "ABC"}]
    assert "prediction_id" in body
    assert "project_version" in body


@pytest.mark.asyncio
async def test_extract_missing_key_401(client, db_session, monkeypatch, tmp_path):
    api_code, _ = await _setup_published_project(client, db_session, monkeypatch, tmp_path)
    resp = await client.post(
        f"/extract/{api_code}",
        files=[("file", ("a.pdf", io.BytesIO(b"PDF"), "application/pdf"))],
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_extract_unknown_api_code_404(client):
    resp = await client.post(
        "/extract/nonexistent",
        files=[("file", ("a.pdf", io.BytesIO(b"PDF"), "application/pdf"))],
        headers={"X-Api-Key": "ek_DEADBEEF-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"},
    )
    assert resp.status_code in (401, 404)


@pytest.mark.asyncio
async def test_extract_unpublished_returns_403(client, db_session, monkeypatch, tmp_path):
    api_code, key = await _setup_published_project(client, db_session, monkeypatch, tmp_path)
    # unpublish via authed call
    await client.post(
        "/api/v1/auth/login", json={"email": "px@px.com", "password": "hunter22"}
    )  # already auth'd; just call unpublish — but tests use fresh client; rebuild header
    tok = (
        await client.post(
            "/api/v1/auth/login", json={"email": "px@px.com", "password": "hunter22"}
        )
    ).json()["access_token"]
    h = {"Authorization": f"Bearer {tok}"}
    from app.models.project import Project
    from sqlalchemy import select

    pid = (
        await db_session.execute(select(Project).where(Project.api_code == api_code))
    ).scalar_one().id
    await client.post(f"/api/v1/projects/{pid}/unpublish", headers=h)

    resp = await client.post(
        f"/extract/{api_code}",
        files=[("file", ("a.pdf", io.BytesIO(b"PDF"), "application/pdf"))],
        headers={"X-Api-Key": key},
    )
    assert resp.status_code == 404  # api_code no longer exists
```

- [ ] **Step 2: Run — expect 404**

- [ ] **Step 3: Implement `app/api/routes/public.py`**

```python
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Header, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session, SessionFactory
from app.engine.extract import extract_document
from app.engine.provider import Provider
from app.engine.providers import get_provider_dep
from app.errors import EmergeError, ErrorCode
from app.models.api_key import ApiKey
from app.models.document import Document, DocumentStatus
from app.models.project import Project
from app.services.api_key import parse_prefix, verify_api_key
from app.services.storage import save_upload

router = APIRouter(tags=["public"])


async def _resolve_project(session: AsyncSession, api_code: str) -> Project:
    p = (
        await session.execute(
            select(Project).where(
                Project.api_code == api_code, Project.api_published_at.is_not(None)
            )
        )
    ).scalar_one_or_none()
    if p is None:
        raise EmergeError(ErrorCode.NOT_FOUND, status_code=404)
    return p


async def _authenticate_key(
    session: AsyncSession, project_id: int, presented: str | None
) -> ApiKey:
    if not presented:
        raise EmergeError(ErrorCode.UNAUTHORIZED, status_code=401)
    prefix = parse_prefix(presented)
    if prefix is None:
        raise EmergeError(ErrorCode.UNAUTHORIZED, status_code=401)
    rows = (
        await session.execute(
            select(ApiKey).where(
                ApiKey.project_id == project_id,
                ApiKey.prefix == prefix,
                ApiKey.deleted_at.is_(None),
            )
        )
    ).scalars().all()
    for row in rows:
        if verify_api_key(presented, prefix=row.prefix, key_hash=row.key_hash):
            row.last_used_at = datetime.now(tz=timezone.utc)
            await session.commit()
            return row
    raise EmergeError(ErrorCode.UNAUTHORIZED, status_code=401)


@router.post("/extract/{api_code}")
async def public_extract(
    api_code: str,
    file: UploadFile,
    x_api_key: str | None = Header(default=None, alias="X-Api-Key"),
    provider: Provider = Depends(get_provider_dep),
    session: AsyncSession = Depends(get_session),
):
    project = await _resolve_project(session, api_code)
    await _authenticate_key(session, project.id, x_api_key)

    rec = await save_upload(file, project_id=project.id)
    doc = Document(
        project_id=project.id,
        filename=rec.filename,
        file_path=rec.file_path,
        mime_type=rec.mime_type,
        page_count=0,
        byte_size=rec.byte_size,
        uploaded_by=0,  # 0 = "external API caller"
        status=DocumentStatus.UPLOADED.value,
        data={"source": "public_api", "api_code": api_code},
    )
    session.add(doc)
    await session.commit()
    await session.refresh(doc)

    pred = await extract_document(doc.id, session=session, provider=provider)
    return {
        "entities": pred.output,
        "project_version": pred.project_version_id,
        "prediction_id": pred.id,
    }
```

- [ ] **Step 4: Mount in `app/main.py` (outside `/api/v1`)**

```python
from app.api.routes import public


def create_app() -> FastAPI:
    app = FastAPI(...)
    app.include_router(api_v1)
    app.include_router(public.router)  # no prefix
    ...
```

- [ ] **Step 5: Run test to verify it passes**

Expected: `4 passed`.

- [ ] **Step 6: Commit**

```bash
git add backend/app/api/routes/public.py backend/app/main.py backend/tests/test_public_extract.py
git commit -m "feat(api): public /extract/{api_code} with X-Api-Key auth"
```

---

## Task 8: Public feedback endpoint

**Files:**
- Modify: `backend/app/api/routes/public.py` (append `/extract/{api_code}/feedback`)
- Create: `backend/tests/test_public_feedback.py`

Calls R4's `save_counterexample` with `user_id=0` (external API caller). Validates that `request_id` (= prediction id) belongs to the current `api_code`'s project.

- [ ] **Step 1: Write failing test**

```python
import io

import pytest


@pytest.mark.asyncio
async def test_public_feedback_creates_counterexample(client, db_session, app, tmp_path, monkeypatch):
    from tests.test_public_extract import _setup_published_project

    api_code, key = await _setup_published_project(client, db_session, monkeypatch, tmp_path)

    from app.engine.providers import get_provider_dep
    from app.engine.providers.fake import FakeProvider

    fake = FakeProvider(canned=[[{"shop_name": "WRONG"}]])
    app.dependency_overrides[get_provider_dep] = lambda: fake

    extract_resp = await client.post(
        f"/extract/{api_code}",
        files=[("file", ("a.pdf", io.BytesIO(b"PDF"), "application/pdf"))],
        headers={"X-Api-Key": key},
    )
    pred_id = extract_resp.json()["prediction_id"]

    fb = await client.post(
        f"/extract/{api_code}/feedback",
        json={"request_id": pred_id, "correct_output": [{"shop_name": "RIGHT"}]},
        headers={"X-Api-Key": key},
    )
    assert fb.status_code == 200, fb.text

    # verify a counterexample row exists
    from app.models.annotation import Annotation, AnnotationRole
    from sqlalchemy import select

    rows = (
        await db_session.execute(
            select(Annotation).where(Annotation.role == AnnotationRole.COUNTEREXAMPLE.value)
        )
    ).scalars().all()
    assert len(rows) == 1
    assert rows[0].output == [{"shop_name": "RIGHT"}]


@pytest.mark.asyncio
async def test_feedback_with_mismatched_prediction_returns_422(client, db_session, app, tmp_path, monkeypatch):
    from tests.test_public_extract import _setup_published_project

    api_code, key = await _setup_published_project(client, db_session, monkeypatch, tmp_path)
    fb = await client.post(
        f"/extract/{api_code}/feedback",
        json={"request_id": 999_999, "correct_output": [{"x": 1}]},
        headers={"X-Api-Key": key},
    )
    assert fb.status_code == 422
```

- [ ] **Step 2: Run — expect 404**

- [ ] **Step 3: Append endpoint to `app/api/routes/public.py`**

```python
from app.schemas.annotation import FeedbackIn
from app.services.corrections import PredictionScopeError, save_counterexample


@router.post("/extract/{api_code}/feedback")
async def public_feedback(
    api_code: str,
    payload: FeedbackIn,
    x_api_key: str | None = Header(default=None, alias="X-Api-Key"),
    session: AsyncSession = Depends(get_session),
):
    project = await _resolve_project(session, api_code)
    await _authenticate_key(session, project.id, x_api_key)
    try:
        ann = await save_counterexample(
            session=session,
            project_id=project.id,
            prediction_id=payload.request_id,
            correct_output=payload.correct_output,
            user_id=0,
            notes=payload.notes,
        )
    except PredictionScopeError as e:
        raise EmergeError(
            ErrorCode.VALIDATION_FAILED, status_code=422, message_override=str(e)
        ) from e
    return {"counterexample_id": ann.id}
```

- [ ] **Step 4: Run test to verify it passes**

- [ ] **Step 5: Commit**

```bash
git add backend/app/api/routes/public.py backend/tests/test_public_feedback.py
git commit -m "feat(api): public /extract/{api_code}/feedback creates counterexample"
```

---

## Task 9: Rate limiting

**Files:**
- Add `slowapi>=0.1.9` to `pyproject.toml`
- Create: `backend/app/services/ratelimit.py`
- Modify: `backend/app/main.py` (register limiter)
- Modify: `backend/app/api/routes/public.py` (apply limiter)
- Create: `backend/tests/test_ratelimit.py`

Default 60/min/key (spec §7.1). The key extractor uses the `X-Api-Key` header value. Rate-limit error returns the standard envelope with `error_code=RATE_LIMITED` (add to `ErrorCode` enum) and HTTP 429.

- [ ] **Step 1: Add `RATE_LIMITED` to `app/errors.py`**

```python
class ErrorCode(str, Enum):
    ...
    RATE_LIMITED = "RATE_LIMITED"


_MESSAGES[ErrorCode.RATE_LIMITED] = "Too many requests. Slow down and try again."
```

- [ ] **Step 2: Add `slowapi>=0.1.9`** to pyproject and `uv sync --extra dev`.

- [ ] **Step 3: Implement `app/services/ratelimit.py`**

```python
from fastapi import Request
from slowapi import Limiter
from slowapi.util import get_remote_address


def key_or_remote(request: Request) -> str:
    return request.headers.get("X-Api-Key") or get_remote_address(request)


limiter = Limiter(key_func=key_or_remote, default_limits=["60/minute"])
```

- [ ] **Step 4: Wire in `app/main.py`**

```python
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.errors import ErrorCode
from app.services.ratelimit import limiter


def create_app() -> FastAPI:
    app = FastAPI(...)
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    ...

```

Override the handler so it produces the emerge envelope:

```python
from fastapi import Request
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded


@app.exception_handler(RateLimitExceeded)
async def _rl(_: Request, _exc: RateLimitExceeded):
    return JSONResponse(
        status_code=429,
        content={
            "error_code": ErrorCode.RATE_LIMITED.value,
            "error_message_en": "Too many requests. Slow down and try again.",
        },
    )
```

- [ ] **Step 5: Decorate public endpoints**

In `app/api/routes/public.py`:

```python
from app.services.ratelimit import limiter


@router.post("/extract/{api_code}")
@limiter.limit("60/minute")
async def public_extract(request: Request, ...):
    ...


@router.post("/extract/{api_code}/feedback")
@limiter.limit("60/minute")
async def public_feedback(request: Request, ...):
    ...
```

(Both functions must accept a `request: Request` first positional param for slowapi to read headers — adjust signatures accordingly.)

- [ ] **Step 6: Write the failing test**

```python
import io

import pytest


@pytest.mark.asyncio
async def test_rate_limit_returns_429(client, db_session, app, tmp_path, monkeypatch):
    from app.services.ratelimit import limiter
    from tests.test_public_extract import _setup_published_project

    api_code, key = await _setup_published_project(client, db_session, monkeypatch, tmp_path)

    # tighten limit for the test
    limiter.reset()
    limiter._default_limits = ["2/minute"]

    from app.engine.providers import get_provider_dep
    from app.engine.providers.fake import FakeProvider

    fake = FakeProvider(canned=[[{"x": "1"}]] * 10)
    app.dependency_overrides[get_provider_dep] = lambda: fake

    for _ in range(2):
        await client.post(
            f"/extract/{api_code}",
            files=[("file", ("a.pdf", io.BytesIO(b"PDF"), "application/pdf"))],
            headers={"X-Api-Key": key},
        )
    resp = await client.post(
        f"/extract/{api_code}",
        files=[("file", ("a.pdf", io.BytesIO(b"PDF"), "application/pdf"))],
        headers={"X-Api-Key": key},
    )
    assert resp.status_code == 429
    assert resp.json()["error_code"] == "RATE_LIMITED"
```

- [ ] **Step 7: Run test to verify it passes**

Note: slowapi's middleware coupling can be brittle in test setups. If the limiter doesn't reset cleanly between tests, switch to a `pytest fixture` that constructs a fresh limiter per test. Investigate before claiming success.

- [ ] **Step 8: Run full suite**

Run: `cd backend && uv run pytest -v`
Expected: every R1+…+R7 test passes.

- [ ] **Step 9: Commit**

```bash
git add backend/pyproject.toml backend/app/services/ratelimit.py backend/app/api/routes/public.py backend/app/errors.py backend/app/main.py backend/tests/test_ratelimit.py
git commit -m "feat(api): rate limit public extract/feedback at 60/min/key"
```

---

## R7 exit criteria

End-to-end (M4 reuse + ship):

1. New workspace sees 5 builtins on `GET /templates`.
2. `POST /projects` with `template_id=<japan_receipt builtin id>` creates a project whose v0 has the Japanese-receipt schema.
3. After locking the active version, `POST /publish {api_code}` succeeds; before lock it 409s.
4. `POST /api-keys` returns full plaintext once; subsequent list shows only prefix.
5. `POST /extract/{api_code}` with valid key returns `{entities, project_version, prediction_id}`; missing key 401; unpublished 404.
6. `POST /extract/{api_code}/feedback` with `prediction_id` belonging to that project creates an Annotation `role=counterexample`.
7. 61st call within a minute on a fixed key returns 429 with `error_code=RATE_LIMITED`.
8. `POST /save-as-template` produces a Template visible to the workspace; second save with same name without `create_new_version` 409s.

Run `cd backend && uv run pytest -v` — all tests R1+…+R7 pass.

R8 surfaces all of this in the UI: Project creation dialog with 5 builtins + NL-first input; Schema editor with form/chat dual mode; Project page header with publish flow + key reveal modal; Studio sidebar; AutoResearch run viewer; Document list view with filters.
