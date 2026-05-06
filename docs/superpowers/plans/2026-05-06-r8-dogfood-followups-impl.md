# R8 dogfood follow-ups implementation plan (2026-05-06)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Land items #1–#7 from `docs/superpowers/plans/2026-05-06-r8-dogfood-followups.md`. #8 explicitly deferred. Decisions are locked; this plan only codifies the bite-sized steps.

**Architecture:**
- Three independently testable commits in order: (A) workspace isolation + ExtractResponse reshape, (B) Studio dual-affordance + Contract Diff initial-publish copy + Readiness rename, (C) Toast pill + Revoke AlertDialog. Items map to the `Suggested commit / PR shape` in the parent doc.
- All UI work uses the existing semantic Tailwind tokens (`bg-bg-elevated`, `text-fg-muted`, …); no raw color classes (CLAUDE.md hard rule).
- Schema rename strategy for #7: hard rename `reviewed_*` → `annotated_*` (no shim). Single in-flight feature, single workspace, no integrators consuming readiness JSON yet — drop the dead form rather than carry both.
- Toast (commit C) uses `@radix-ui/react-toast` (already in `package.json`). AlertDialog (commit C) uses the existing `@radix-ui/react-dialog` wrapper instead of pulling a new Radix package; the destructive-confirmation pattern doesn't need the AlertDialog's role/escape semantics for v1.

**Tech Stack:** FastAPI + async SQLAlchemy + alembic + aiosqlite + pytest (backend); Vite + React 19 + Zustand + Radix + Tailwind + Vitest (frontend).

---

## File map (decisions locked)

### Commit A — #1 + #2

| File | Action |
|---|---|
| `backend/alembic/versions/0016_document_source.py` | Create — adds `documents.source` String(16) NOT NULL DEFAULT 'lab' with check constraint |
| `backend/app/models/document.py` | Modify — add `source: Mapped[str]` column + `DocumentSource` enum + check constraint |
| `backend/app/api/routes/public.py` | Modify — set `source="public_api"` on Document insert; reshape `PublicExtractOut` to `{request_id, prediction_id, project_version_id, output: {entities}}` |
| `backend/app/api/routes/documents.py` | Modify — `list_documents` filters `Document.source == "lab"` |
| `backend/app/engine/recompute.py` | Modify — `vibe_check_predictions_query` filters `Document.source == "lab"` (and ditto in `_setup_published_project`-style code paths) |
| `backend/app/services/readiness.py` | Modify — `saved_anns` join filters on Document.source = 'lab' |
| `backend/tests/test_public_extract.py` | Modify — assert new response envelope; add `assert document.source == "public_api"` and editor list-API does not see it |
| `backend/tests/test_document_routes.py` | Modify (or add new test file `test_document_source_isolation.py`) — public extract should NOT contaminate the editor's `/documents` list |
| `backend/tests/test_public_feedback.py` | Modify if it asserts response shape — likely just exercises the feedback endpoint, untouched by the extract reshape |
| `frontend/src/pages/ApiConsole.tsx` | Modify — curl + python snippets show new envelope (`response['output']['entities']`) and `request_id` round-trip |
| `frontend/src/__tests__/api_console.test.tsx` | Modify if it snapshots snippet text |
| `docs/local-demo.md` | Verify only — should already match new envelope; if it diverges, update |

### Commit B — #3 + #6 + #7

| File | Action |
|---|---|
| `frontend/src/components/ReportWrongFieldDialog.tsx` | Delete — redundant with editing the textbox per dogfood doc |
| `frontend/src/__tests__/report_wrong_dialog.test.tsx` | Delete — covers a UI being removed |
| `frontend/src/components/FlagFieldMenu.tsx` | Create — ⋮ trigger + small inline dialog with `issue_type` select + optional comment, calls a new `studio.flagField` action |
| `frontend/src/__tests__/flag_field_menu.test.tsx` | Create — opens menu, selects issue_type, saves Annotation with unchanged output + `notes` containing `[lab_flag]={...}` |
| `frontend/src/stores/studio.ts` | Modify — add `flagField({issueType, comment})` action; remove `reportWrong` (no caller after the dialog deletion) |
| `frontend/src/pages/Studio.tsx` | Modify — drop the per-field `Flag` button, render `FlagFieldMenu` once per `FieldRow` |
| `frontend/src/i18n/locales/en.json` | Modify — drop `studio.report_wrong.*` block, add `studio.flag.*` block + `api_console.diff_initial_*` keys + `readiness.evidence_value` rewrite |
| `frontend/src/components/ReadinessPanel.tsx` | Modify — `evidence_value` translation now uses `annotated` instead of `fields` |
| `frontend/src/types/readiness.ts` | Modify — rename `EvidenceCoverage.reviewed_*` → `annotated_*` |
| `frontend/src/__tests__/readiness_panel.test.tsx` | Modify — update fixtures + assertions |
| `frontend/src/__tests__/api_console.test.tsx` | Modify — add a test for initial-publish (`from_version_id: null`) Contract Diff copy switch; update existing fixture to keep covering the breaking-warning path |
| `frontend/src/pages/ApiConsole.tsx` | Modify — `ContractDiffSection` swaps copy when `diff.from_version_id == null` |
| `backend/app/schemas/readiness.py` | Modify — rename `reviewed_*` → `annotated_*` on `EvidenceCoverageOut` and `SchemaMaturityOut` |
| `backend/app/services/readiness.py` | Modify — rename local vars + emit new keys; thresholds inside `maturity_status` heuristic still read the new names |
| `backend/tests/test_readiness_routes.py` | Modify — update fixture assertions to new keys |

### Commit C — #4 + #5

| File | Action |
|---|---|
| `frontend/src/components/ui/Toast.tsx` | Create — Radix Toast wrapper exposing `useToast()` hook with a single auto-dismiss "Saved" pill |
| `frontend/src/main.tsx` | Modify — wrap the app in `<ToastProvider>` |
| `frontend/src/pages/Studio.tsx` | Modify — fire toast on save success (and `flagField` success — same hook) |
| `frontend/src/pages/ApiConsole.tsx` | Modify — fire toast on Activate / Unpublish / Revoke success; gate Revoke behind a confirmation dialog |
| `frontend/src/components/ConfirmRevokeKeyDialog.tsx` | Create — Radix Dialog confirmation, copy: "Revoke key '{name}'? Integrators using this key will start getting 403 immediately." |
| `frontend/src/i18n/locales/en.json` | Modify — `common.saved`, `common.revoke_dialog_*` keys |
| `frontend/src/__tests__/api_console.test.tsx` | Modify — Revoke now requires confirm-button click before the row disappears; assert toast |
| `frontend/src/__tests__/studio_save.test.tsx` | Modify — assert toast appears after save |
| `docs/superpowers/plans/2026-05-04-r8-hygiene-tail.md` | Modify — mark item #13 as fixed (commit message reference is enough; row stays so the audit trail survives) |

---

## Commit A: #1 + #2 — workspace isolation + ExtractResponse reshape

### Task A1: Add `Document.source` column + alembic migration

**Files:**
- Create: `backend/alembic/versions/0016_document_source.py`
- Modify: `backend/app/models/document.py`
- Test: `backend/tests/test_document_model.py`

- [ ] **Step 1: Write the failing model test**

In `backend/tests/test_document_model.py` add:

```python
@pytest.mark.asyncio
async def test_document_source_defaults_to_lab(db_session):
    from tests.fixtures.helpers import create_user_and_project  # if available; otherwise inline
    proj_id = await _make_project(db_session)
    d = Document(
        project_id=proj_id,
        filename="x.pdf", file_path="/tmp/x.pdf", mime_type="application/pdf",
        page_count=0, byte_size=10, uploaded_by=1,
    )
    db_session.add(d)
    await db_session.commit()
    await db_session.refresh(d)
    assert d.source == "lab"


@pytest.mark.asyncio
async def test_document_source_rejects_unknown(db_session):
    from sqlalchemy.exc import IntegrityError
    proj_id = await _make_project(db_session)
    d = Document(
        project_id=proj_id, filename="x.pdf", file_path="/tmp/x.pdf",
        mime_type="application/pdf", page_count=0, byte_size=10, uploaded_by=1,
        source="floofs",
    )
    db_session.add(d)
    with pytest.raises(IntegrityError):
        await db_session.commit()
```

If `_make_project` doesn't exist, inline a minimal fixture: create a `Project` with `workspace_id=1, name="P", created_by=1` after seeding a workspace + user via the existing helpers in this test file (mirror existing tests in the file).

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd backend && uv run pytest tests/test_document_model.py -v
```

Expected: both new tests fail (column doesn't exist / no constraint).

- [ ] **Step 3: Add the column to the model**

In `backend/app/models/document.py`:

```python
from enum import Enum

from sqlalchemy import JSON, CheckConstraint, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class DocumentStatus(str, Enum):
    UPLOADED = "uploaded"
    EXTRACTING = "extracting"
    EXTRACTED = "extracted"
    ERRORED = "errored"
    ARCHIVED = "archived"


class DocumentSource(str, Enum):
    LAB = "lab"
    PUBLIC_API = "public_api"


_VALID_STATUSES = ",".join(f"'{s.value}'" for s in DocumentStatus)
_VALID_SOURCES = ",".join(f"'{s.value}'" for s in DocumentSource)


class Document(Base, TimestampMixin):
    __tablename__ = "documents"
    __table_args__ = (
        CheckConstraint(f"status IN ({_VALID_STATUSES})", name="ck_document_status"),
        CheckConstraint(f"source IN ({_VALID_SOURCES})", name="ck_document_source"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), nullable=False, index=True)
    filename: Mapped[str] = mapped_column(String(512), nullable=False)
    file_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(128), nullable=False)
    page_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    byte_size: Mapped[int] = mapped_column(Integer, nullable=False)
    uploaded_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    data: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default=DocumentStatus.UPLOADED.value
    )
    source: Mapped[str] = mapped_column(
        String(16), nullable=False, default=DocumentSource.LAB.value, index=True,
    )
```

- [ ] **Step 4: Add the alembic migration**

Create `backend/alembic/versions/0016_document_source.py`:

```python
"""add documents.source ('lab' | 'public_api')

Workspace isolation: public-API extractions create a Document with
source='public_api' and must NOT appear in the editor's Documents list
or the vibe-check pool. Spec §7.1 separates Lab and integrator traffic.

Revision ID: 0016
Revises: 0015
Create Date: 2026-05-06
"""
from alembic import op
import sqlalchemy as sa


revision = '0016'
down_revision = '0015'
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table('documents') as batch:
        batch.add_column(
            sa.Column(
                'source', sa.String(length=16), nullable=False, server_default='lab',
            )
        )
        batch.create_check_constraint(
            'ck_document_source', "source IN ('lab','public_api')"
        )
        batch.create_index('ix_documents_source', ['source'])


def downgrade() -> None:
    with op.batch_alter_table('documents') as batch:
        batch.drop_index('ix_documents_source')
        batch.drop_constraint('ck_document_source', type_='check')
        batch.drop_column('source')
```

- [ ] **Step 5: Run migration to verify it applies cleanly**

```bash
cd backend && uv run alembic upgrade head && uv run alembic downgrade -1 && uv run alembic upgrade head
```

Expected: upgrade → downgrade → upgrade all succeed without errors.

- [ ] **Step 6: Run tests to verify they pass**

```bash
cd backend && uv run pytest tests/test_document_model.py -v
```

Expected: both new tests PASS.

- [ ] **Step 7: Commit (intermediate — no behavior change yet)**

Defer commit until A2 is also done; same logical change.

### Task A2: Public extract sets source='public_api'; editor list + vibe-check filter to source='lab'

**Files:**
- Modify: `backend/app/api/routes/public.py`
- Modify: `backend/app/api/routes/documents.py`
- Modify: `backend/app/engine/recompute.py`
- Modify: `backend/app/services/readiness.py`
- Test: `backend/tests/test_public_extract.py` + `backend/tests/test_document_routes.py`

- [ ] **Step 1: Write the failing tests**

Add to `backend/tests/test_public_extract.py`:

```python
@pytest.mark.asyncio
async def test_public_extract_creates_public_api_document(
    client, db_session, app, tmp_path, monkeypatch
):
    """Spec §7.1: public-API extracts must NOT pollute the Lab Documents list."""
    api_code, key = await _setup_published_project(client, db_session, monkeypatch, tmp_path)
    fake = FakeProvider(canned=[[{"shop_name": "ABC"}]])
    app.dependency_overrides[get_provider_dep] = lambda: fake

    resp = await client.post(
        f"/extract/{api_code}",
        files=[("file", ("a.pdf", io.BytesIO(b"PDF"), "application/pdf"))],
        headers={"X-Api-Key": key},
    )
    assert resp.status_code == 200, resp.text

    # The created Document must be tagged source='public_api'.
    from app.models.document import Document, DocumentSource
    docs = (await db_session.execute(select(Document))).scalars().all()
    assert any(d.source == DocumentSource.PUBLIC_API.value for d in docs)


@pytest.mark.asyncio
async def test_editor_list_documents_excludes_public_api(
    client, db_session, app, tmp_path, monkeypatch
):
    api_code, key = await _setup_published_project(client, db_session, monkeypatch, tmp_path)
    fake = FakeProvider(canned=[[{"shop_name": "ABC"}]])
    app.dependency_overrides[get_provider_dep] = lambda: fake

    # Public extraction
    await client.post(
        f"/extract/{api_code}",
        files=[("file", ("public.pdf", io.BytesIO(b"PDF"), "application/pdf"))],
        headers={"X-Api-Key": key},
    )

    # Editor login + list documents (mirrors _setup_published_project's session)
    tok = (
        await client.post(
            "/api/v1/auth/login", json={"email": "px@px.com", "password": "hunter22"}
        )
    ).json()["access_token"]
    h = {"Authorization": f"Bearer {tok}"}
    pid = (
        await db_session.execute(select(Project).where(Project.api_code == api_code))
    ).scalar_one().id
    listed = (
        await client.get(f"/api/v1/projects/{pid}/documents", headers=h)
    ).json()
    assert all(d["filename"] != "public.pdf" for d in listed), listed
```

- [ ] **Step 2: Run to verify they fail**

```bash
cd backend && uv run pytest tests/test_public_extract.py::test_public_extract_creates_public_api_document tests/test_public_extract.py::test_editor_list_documents_excludes_public_api -v
```

Expected: first asserts no `source='public_api'` (column defaults to 'lab' on insert path that doesn't set it); second asserts `public.pdf` IS listed (no filter yet).

- [ ] **Step 3: Set source='public_api' in the public extract handler**

In `backend/app/api/routes/public.py`, in `public_extract`, the `Document(...)` construction:

```python
    doc = Document(
        project_id=project.id,
        filename=rec.filename,
        file_path=rec.file_path,
        mime_type=rec.mime_type,
        page_count=0,
        byte_size=rec.byte_size,
        uploaded_by=0,  # external API caller — no user
        status=DocumentStatus.UPLOADED.value,
        source="public_api",
        data={"source": "public_api", "api_code": api_code},
    )
```

(`data["source"]` is kept for back-compat audit; the typed column is now authoritative.)

Also add the import at the top:

```python
from app.models.document import Document, DocumentSource, DocumentStatus
```

(Use the enum value only if it improves readability; literal string `"public_api"` is fine and matches the column constraint.)

- [ ] **Step 4: Filter the editor list endpoint**

In `backend/app/api/routes/documents.py`, in `list_documents`:

```python
    rows = (
        await session.execute(
            select(Document)
            .where(
                Document.project_id == project_id,
                Document.source == "lab",
            )
            .order_by(Document.id.desc())
        )
    ).scalars().all()
```

- [ ] **Step 5: Filter vibe-check pool to source='lab'**

In `backend/app/engine/recompute.py`, in `vibe_check_predictions_query`:

```python
def vibe_check_predictions_query(
    project_id: int, *, ignore_annotations: bool = False
) -> Select:
    has_prediction = exists().where(Prediction.document_id == Document.id)
    if ignore_annotations:
        return select(Document.id).where(
            Document.project_id == project_id,
            Document.source == "lab",
            has_prediction,
        )
    latest_pred_id = (
        select(func.max(Prediction.id))
        .where(Prediction.document_id == Document.id)
        .correlate(Document)
        .scalar_subquery()
    )
    covered_by_annotation = exists().where(
        and_(
            Annotation.document_id == Document.id,
            Annotation.role == AnnotationRole.NONE.value,
            Annotation.status == AnnotationStatus.SAVED.value,
            or_(
                Annotation.parent_prediction_id.is_(None),
                Annotation.parent_prediction_id == latest_pred_id,
            ),
        )
    )
    return select(Document.id).where(
        Document.project_id == project_id,
        Document.source == "lab",
        has_prediction,
        ~covered_by_annotation,
    )
```

Update the docstring to mention that public_api documents are excluded so the integrator-traffic pool doesn't dilute the editor's review signal.

- [ ] **Step 6: Filter readiness saved_anns join**

In `backend/app/services/readiness.py`, in `build_readiness`, the `saved_anns` query:

```python
    saved_anns = (
        await session.execute(
            select(Annotation)
            .join(Document, Document.id == Annotation.document_id)
            .where(
                Document.project_id == project_id,
                Document.source == "lab",
                Annotation.role == AnnotationRole.NONE.value,
                Annotation.status == AnnotationStatus.SAVED.value,
            )
        )
    ).scalars().all()
```

Counterexample query right below it (lines 147–157) uses `AnnotationRole.COUNTEREXAMPLE` — counterexamples come from public feedback, so we DO want them counted regardless of Document.source. Leave that join unchanged.

- [ ] **Step 7: Run tests to verify they pass**

```bash
cd backend && uv run pytest tests/test_public_extract.py tests/test_document_routes.py tests/test_readiness_routes.py tests/test_recompute.py -v
```

Expected: PASS. If `test_recompute.py` has fixtures that don't set `source` explicitly, they pick up the default 'lab' and continue to pass — verify.

- [ ] **Step 8: Commit (Task A1 + A2 together)**

```bash
git add backend/alembic/versions/0016_document_source.py \
        backend/app/models/document.py \
        backend/app/api/routes/public.py \
        backend/app/api/routes/documents.py \
        backend/app/engine/recompute.py \
        backend/app/services/readiness.py \
        backend/tests/test_document_model.py \
        backend/tests/test_public_extract.py
git commit -m "feat(documents): isolate public-API traffic via Document.source"
```

(Body should reference dogfood doc #1 and the alembic 0016 migration.)

### Task A3: Reshape PublicExtractOut to `{request_id, prediction_id, project_version_id, output: {entities}}`

**Files:**
- Modify: `backend/app/api/routes/public.py`
- Modify: `backend/tests/test_public_extract.py`
- Modify: `frontend/src/pages/ApiConsole.tsx` (snippets only)
- Verify: `docs/local-demo.md`

- [ ] **Step 1: Update existing test_extract_returns_entities to expect new envelope**

In `backend/tests/test_public_extract.py`:

```python
@pytest.mark.asyncio
async def test_extract_returns_entities(client, db_session, app, tmp_path, monkeypatch):
    api_code, key = await _setup_published_project(client, db_session, monkeypatch, tmp_path)

    fake = FakeProvider(canned=[[{"shop_name": "ABC"}]])
    app.dependency_overrides[get_provider_dep] = lambda: fake

    resp = await client.post(
        f"/extract/{api_code}",
        files=[("file", ("a.pdf", io.BytesIO(b"PDF"), "application/pdf"))],
        headers={"X-Api-Key": key},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    # New envelope (dogfood #2): output: {entities}, project_version_id renamed,
    # request_id mirrors prediction_id so feedback-POST has an obvious source field.
    assert body["output"]["entities"] == [{"shop_name": "ABC"}]
    assert isinstance(body["prediction_id"], int)
    assert body["request_id"] == body["prediction_id"]
    assert isinstance(body["project_version_id"], int)
    # Old fields gone.
    assert "entities" not in body
    assert "project_version" not in body
```

Also update `test_public_extract_uses_published_version_not_active`:

```python
    assert body["project_version_id"] == published_version_id
```

- [ ] **Step 2: Run to verify they fail**

```bash
cd backend && uv run pytest tests/test_public_extract.py -v
```

Expected: assertions on `body["output"]["entities"]` etc. fail.

- [ ] **Step 3: Reshape `PublicExtractOut` and the handler**

In `backend/app/api/routes/public.py`:

```python
class PublicExtractOutput(BaseModel):
    entities: list[dict]


class PublicExtractOut(BaseModel):
    request_id: int
    prediction_id: int
    project_version_id: int
    output: PublicExtractOutput
```

And the handler return:

```python
    return PublicExtractOut(
        request_id=pred.id,
        prediction_id=pred.id,
        project_version_id=pred.project_version_id,
        output=PublicExtractOutput(entities=pred.output),
    )
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd backend && uv run pytest tests/test_public_extract.py -v
```

Expected: PASS.

- [ ] **Step 5: Update API Console snippets**

In `frontend/src/pages/ApiConsole.tsx`, replace the curl + python `useMemo` blocks (≈ lines 471–480):

```ts
  const curl = useMemo(
    () =>
      `curl -X POST "https://api.emerge.dev/extract/${code}" \\\n  -H "X-Api-Key: $EMERGE_API_KEY" \\\n  -F "file=@invoice.pdf"\n# Response: {request_id, prediction_id, project_version_id, output: {entities: [...]}}`,
    [code],
  );
  const py = useMemo(
    () =>
      `import os, requests\nresp = requests.post(\n  f"https://api.emerge.dev/extract/${code}",\n  headers={"X-Api-Key": os.environ["EMERGE_API_KEY"]},\n  files={"file": open("invoice.pdf", "rb")},\n).json()\nentities = resp["output"]["entities"]\nrequest_id = resp["request_id"]   # echo back as feedback's request_id`,
    [code],
  );
```

- [ ] **Step 6: Verify `docs/local-demo.md` matches**

```bash
grep -n "output\":\|request_id\|project_version" docs/local-demo.md
```

If the doc still shows the old `entities` top-level shape, fix it (single-line change). Skip if already correct.

- [ ] **Step 7: Run frontend test suite**

```bash
cd frontend && npm test -- --run
```

Expected: PASS. If `api_console.test.tsx` snapshots snippet text, update the snapshot.

- [ ] **Step 8: Commit**

```bash
git add backend/app/api/routes/public.py \
        backend/tests/test_public_extract.py \
        frontend/src/pages/ApiConsole.tsx \
        docs/local-demo.md  # only if it changed
git commit -m "feat(public-api): wrap extract response in {output, request_id, project_version_id}"
```

Commit body cites dogfood #2 and notes the breaking-change scoping (pre-GA, only consumer is the local demo).

### Gate review for Commit A

After commits A1+A2 and A3 land, dispatch a `superpowers:code-reviewer` agent for gate review per `feedback_gate_review_subagent`:

> Review commits {hash1} {hash2} on branch r8-productization-mvp against `docs/superpowers/plans/2026-05-06-r8-dogfood-followups.md` items #1 and #2. Focus on: (a) public_api Documents truly invisible to editor + vibe-check + readiness; (b) alembic migration round-trips cleanly; (c) response envelope matches `docs/local-demo.md`. Flag anything that breaks `./scripts/release-checklist.sh` or `EMERGE_E2E=1` smoke.

Address review feedback before opening commit B.

---

## Commit B: #3 + #6 + #7 — Studio dual-affordance + Contract Diff initial copy + Readiness rename

### Task B1: Rename `reviewed_*` → `annotated_*` (backend)

**Files:**
- Modify: `backend/app/schemas/readiness.py`
- Modify: `backend/app/services/readiness.py`
- Modify: `backend/tests/test_readiness_routes.py`

- [ ] **Step 1: Update test fixtures + assertions to new keys**

In `backend/tests/test_readiness_routes.py` find `reviewed_docs`, `reviewed_entities`, `reviewed_fields` and rename to `annotated_docs`, `annotated_entities`, `annotated_fields`. Schema-maturity has `reviewed_docs` / `reviewed_entities` too — rename those.

- [ ] **Step 2: Run to verify it fails**

```bash
cd backend && uv run pytest tests/test_readiness_routes.py -v
```

Expected: FAIL with KeyError or assertion mismatch on the new key names.

- [ ] **Step 3: Rename schema fields**

In `backend/app/schemas/readiness.py`:

```python
class EvidenceCoverageOut(BaseModel):
    annotated_docs: int
    annotated_entities: int
    annotated_fields: int
    field_evidence_fields: int
    field_evidence_coverage_ratio: float


class SchemaMaturityOut(BaseModel):
    status: str
    annotated_docs: int
    annotated_entities: int
    recent_schema_breaking_changes: int
    message: str
```

In `backend/app/services/readiness.py`, rename local vars (`reviewed_docs` → `annotated_docs`, etc.) and the kwargs to the two output models. The threshold expression `if annotated_docs >= 5 and annotated_entities >= 20 …` keeps the same numeric values.

- [ ] **Step 4: Run to verify pass**

```bash
cd backend && uv run pytest tests/test_readiness_routes.py -v
```

Expected: PASS.

### Task B2: Mirror rename on the frontend + copy refresh

**Files:**
- Modify: `frontend/src/types/readiness.ts`
- Modify: `frontend/src/components/ReadinessPanel.tsx`
- Modify: `frontend/src/i18n/locales/en.json`
- Modify: `frontend/src/__tests__/readiness_panel.test.tsx`
- Modify: `frontend/src/__tests__/api_console.test.tsx` (READINESS_STUB)

- [ ] **Step 1: Update readiness_panel test fixture + assertions**

In `frontend/src/__tests__/readiness_panel.test.tsx` rename the keys in any `evidence_coverage` / `schema_maturity` literals to `annotated_*`. Update the rendered-text assertion to match the new copy: `2 docs · 16 entities · 72 annotated`.

- [ ] **Step 2: Run to verify it fails**

```bash
cd frontend && npm test -- readiness_panel --run
```

Expected: FAIL — fixture has old keys, type errors and/or assertion mismatch.

- [ ] **Step 3: Rename the type**

In `frontend/src/types/readiness.ts`:

```ts
export type EvidenceCoverage = {
  annotated_docs: number;
  annotated_entities: number;
  annotated_fields: number;
  field_evidence_fields: number;
  field_evidence_coverage_ratio: number;
};

export type SchemaMaturity = {
  status: SchemaMaturityStatus;
  annotated_docs: number;
  annotated_entities: number;
  recent_schema_breaking_changes: number;
  message: string;
};
```

- [ ] **Step 4: Update the i18n string + ReadinessPanel call site**

In `frontend/src/i18n/locales/en.json`:

```json
    "evidence_value": "{{docs}} docs · {{entities}} entities · {{fields}} annotated",
```

Keep the `evidence_coverage` template the same — the rename is about disambiguating "annotated" from "with field evidence", not about the percent line.

In `frontend/src/components/ReadinessPanel.tsx`, `EvidenceRow`:

```ts
        <span>
          {t("readiness.evidence_value", {
            docs: e.annotated_docs,
            entities: e.annotated_entities,
            fields: e.annotated_fields,
          })}
        </span>{" "}
```

- [ ] **Step 5: Update other fixtures**

In `frontend/src/__tests__/api_console.test.tsx` rename the `READINESS_STUB.evidence_coverage` and `READINESS_STUB.schema_maturity` keys.

- [ ] **Step 6: Run frontend tests to verify pass**

```bash
cd frontend && npm test -- --run
```

Expected: PASS.

### Task B3: Contract Diff initial-publish copy switch (#6)

**Files:**
- Modify: `frontend/src/pages/ApiConsole.tsx`
- Modify: `frontend/src/i18n/locales/en.json`
- Modify: `frontend/src/__tests__/api_console.test.tsx`

- [ ] **Step 1: Add the failing test**

In `frontend/src/__tests__/api_console.test.tsx`, add:

```ts
it("Contract diff swaps to initial-publish copy when from_version_id is null", async () => {
  vi.spyOn(api, "get").mockImplementation((url: string) => {
    if (url.endsWith("/readiness"))
      return Promise.resolve({ data: READINESS_STUB });
    if (url.endsWith("/versions"))
      return Promise.resolve({ data: VERSIONS });
    if (url.endsWith("/api-keys"))
      return Promise.resolve({ data: KEYS });
    if (url.endsWith("/contract-diff") || url.includes("/contract-diff?"))
      return Promise.resolve({
        data: {
          from_version_id: null,
          to_version_id: 7,
          has_breaking_changes: true,
          items: [
            {
              kind: "required_field_added",
              severity: "breaking",
              field_name: "shop_name",
              before: null,
              after: { name: "shop_name", type: "string" },
              message: "required field 'shop_name' added",
            },
          ],
        },
      });
    return Promise.resolve({ data: PROJECT });
  });

  renderConsole();
  await settle();
  // Initial-publish copy must NOT contain the alarming "will break existing
  // integrators" string.
  expect(
    screen.queryByText(/will break existing integrators/i),
  ).not.toBeInTheDocument();
  expect(
    await screen.findByText(/initial contract — no prior version/i),
  ).toBeInTheDocument();
});
```

- [ ] **Step 2: Run to verify it fails**

```bash
cd frontend && npm test -- api_console --run
```

Expected: FAIL on the new `initial contract` assertion.

- [ ] **Step 3: Add i18n keys**

In `frontend/src/i18n/locales/en.json`:

```json
    "diff_initial_callout": "Initial contract — no prior version to break.",
```

- [ ] **Step 4: Branch the ContractDiffSection on null `from_version_id`**

In `frontend/src/pages/ApiConsole.tsx`, replace `ContractDiffSection`:

```tsx
function ContractDiffSection({ diff }: { diff: ContractDiff | null }) {
  const t = useT();
  if (!diff) return null;
  const isInitial =
    diff.from_version_id === null || diff.from_version_id === undefined;
  return (
    <section className="space-y-2 rounded-md border border-border-default bg-bg-elevated p-4">
      <h2 className="text-sm font-semibold text-fg-primary">
        {t("api_console.diff_section")}
      </h2>
      {isInitial ? (
        <p className="text-sm text-fg-muted">
          {t("api_console.diff_initial_callout")}
        </p>
      ) : diff.has_breaking_changes ? (
        <p className="text-sm text-status-error">
          {t("api_console.diff_breaking_warning")}
        </p>
      ) : null}
      {diff.items.length === 0 ? (
        <p className="text-sm text-fg-muted">{t("api_console.diff_empty")}</p>
      ) : (
        <ul className="space-y-1">
          {diff.items.map((item, i) => (
            <li key={i} className="flex items-center gap-2 text-sm">
              <Badge tone={isInitial ? "muted" : item.severity === "breaking" ? "error" : "success"}>
                {isInitial
                  ? t("api_console.diff_non_breaking_label")
                  : item.severity === "breaking"
                  ? t("api_console.diff_breaking_label")
                  : t("api_console.diff_non_breaking_label")}
              </Badge>
              <span className="font-mono text-xs text-fg-muted">{item.kind}</span>
              {item.field_name ? (
                <span className="font-mono text-xs text-fg-primary">
                  {item.field_name}
                </span>
              ) : null}
              <span className="text-fg-primary">{item.message}</span>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
```

The `Badge tone="muted"` for initial-publish removes the alarming red while keeping the field list visible.

- [ ] **Step 5: Run frontend tests**

```bash
cd frontend && npm test -- --run
```

Expected: PASS.

### Task B4: Drop ReportWrongFieldDialog + per-field flag button (#3)

**Files:**
- Delete: `frontend/src/components/ReportWrongFieldDialog.tsx`
- Delete: `frontend/src/__tests__/report_wrong_dialog.test.tsx`
- Modify: `frontend/src/stores/studio.ts`
- Modify: `frontend/src/pages/Studio.tsx`
- Modify: `frontend/src/i18n/locales/en.json`
- Create: `frontend/src/components/FlagFieldMenu.tsx`
- Create: `frontend/src/__tests__/flag_field_menu.test.tsx`

- [ ] **Step 1: Write the failing test for FlagFieldMenu**

Create `frontend/src/__tests__/flag_field_menu.test.tsx`:

```tsx
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { FlagFieldMenu } from "@/components/FlagFieldMenu";
import { api } from "@/lib/api";
import { useStudio, type DocumentDetail } from "@/stores/studio";

const PRED_ID = 7777;
const DOC: DocumentDetail = {
  id: 42, project_id: 9, filename: "r.pdf", mime_type: "application/pdf",
  page_count: 1, byte_size: 100, status: "extracted",
  created_at: "2026-05-06T00:00:00Z",
  latest_prediction: {
    id: PRED_ID, output: [{ total: "100" }], status: "ok",
    model_id: "m", tokens_used: 1, error_message: null,
  },
  latest_annotation: null,
};

beforeEach(() => {
  useStudio.setState({ doc: DOC, draft: DOC.latest_prediction!.output, loading: false, saving: false, error: null });
});
afterEach(() => {
  vi.restoreAllMocks();
  useStudio.setState({ doc: null, draft: [], loading: false, saving: false, error: null });
});

describe("FlagFieldMenu", () => {
  it("opens via the ⋮ trigger and shows the issue_type select", () => {
    render(<FlagFieldMenu projectId={9} entityIndex={0} fieldName="total" />);
    fireEvent.click(screen.getByRole("button", { name: /more actions for total/i }));
    expect(screen.getByLabelText(/issue type/i)).toBeInTheDocument();
  });

  it("flag-without-correcting POSTs an Annotation with unchanged output and notes-encoded issue_type", async () => {
    const post = vi.spyOn(api, "post").mockResolvedValue({ data: {} });
    vi.spyOn(api, "get").mockResolvedValue({ data: DOC });
    render(<FlagFieldMenu projectId={9} entityIndex={0} fieldName="total" />);
    fireEvent.click(screen.getByRole("button", { name: /more actions for total/i }));
    fireEvent.change(screen.getByLabelText(/issue type/i), { target: { value: "missing_field" } });
    fireEvent.click(screen.getByRole("button", { name: /^flag$/i }));

    await waitFor(() => expect(post).toHaveBeenCalled());
    const [url, body] = post.mock.calls[0]!;
    expect(url).toBe("/api/v1/projects/9/documents/42/annotations");
    expect(body).toMatchObject({
      output: [{ total: "100" }],
      parent_prediction_id: PRED_ID,
    });
    expect(String(body.notes ?? "")).toContain("[lab_flag]");
    expect(String(body.notes ?? "")).toContain("missing_field");
  });
});
```

- [ ] **Step 2: Run to verify it fails**

```bash
cd frontend && npm test -- flag_field_menu --run
```

Expected: FAIL — module doesn't exist.

- [ ] **Step 3: Add `flagField` action to studio store**

In `frontend/src/stores/studio.ts`, replace the `reportWrong` action with `flagField`:

```ts
type StudioState = {
  // … existing fields …
  flagField: (args: {
    projectId: number;
    entityIndex: number;
    fieldName: string;
    issueType: string;
    comment?: string;
  }) => Promise<void>;
};

  async flagField({ projectId, entityIndex, fieldName, issueType, comment }) {
    const { doc } = get();
    if (doc === null) return;
    const baseline =
      doc.latest_annotation?.output ?? doc.latest_prediction?.output ?? [];
    set({ saving: true, error: null });
    try {
      const tag = JSON.stringify({
        issue_type: issueType,
        entity_index: entityIndex,
        field_name: fieldName,
        comment: comment ?? null,
      });
      await api.post(
        `/api/v1/projects/${projectId}/documents/${doc.id}/annotations`,
        {
          output: baseline,
          parent_prediction_id: doc.latest_prediction?.id ?? null,
          notes: `[lab_flag]=${tag}`,
        },
      );
      await get().load(projectId, doc.id);
      refreshProjectPanels(projectId);
    } catch (e) {
      set({ error: emergeErrorKey(e) });
    } finally {
      set({ saving: false });
    }
  },
```

Remove the `reportWrong` declaration + implementation. Remove the `reportWrong` import in `ReportWrongFieldDialog.tsx` (file deleted next step).

- [ ] **Step 4: Create FlagFieldMenu**

`frontend/src/components/FlagFieldMenu.tsx`:

```tsx
import { MoreVertical } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/Button";
import { Dialog } from "@/components/ui/Dialog";
import { Input } from "@/components/ui/Input";
import { useT } from "@/i18n/useT";
import { useStudio } from "@/stores/studio";

const ISSUE_TYPES = [
  "wrong_value",
  "missing_field",
  "extra_field",
  "wrong_entity_count",
  "other",
] as const;

export function FlagFieldMenu({
  projectId,
  entityIndex,
  fieldName,
}: {
  projectId: number;
  entityIndex: number;
  fieldName: string;
}) {
  const t = useT();
  const [open, setOpen] = useState(false);
  const [issueType, setIssueType] = useState<string>("wrong_value");
  const [comment, setComment] = useState("");
  const saving = useStudio((s) => s.saving);
  const flagField = useStudio((s) => s.flagField);

  async function onFlag() {
    await flagField({ projectId, entityIndex, fieldName, issueType, comment });
    setOpen(false);
  }

  return (
    <>
      <button
        type="button"
        aria-label={t("studio.flag.trigger_aria", { field: fieldName })}
        onClick={() => setOpen(true)}
        className="text-fg-muted hover:text-fg-primary"
      >
        <MoreVertical size={14} />
      </button>
      {open ? (
        <Dialog
          open={open}
          onOpenChange={setOpen}
          title={t("studio.flag.dialog_title")}
        >
          <div className="space-y-3 text-sm">
            <p className="text-xs text-fg-muted">{t("studio.flag.dialog_hint")}</p>
            <label className="flex flex-col gap-1 text-xs">
              <span className="text-fg-muted">{t("studio.flag.issue_type_label")}</span>
              <select
                value={issueType}
                onChange={(e) => setIssueType(e.target.value)}
                aria-label={t("studio.flag.issue_type_label")}
                className="rounded-md border border-border-default bg-bg-surface px-2 py-1 text-fg-primary"
              >
                {ISSUE_TYPES.map((kind) => (
                  <option key={kind} value={kind}>
                    {t(`studio.flag.issue_type.${kind}`)}
                  </option>
                ))}
              </select>
            </label>
            <label className="flex flex-col gap-1 text-xs">
              <span className="text-fg-muted">{t("studio.flag.comment_label")}</span>
              <Input value={comment} onChange={(e) => setComment(e.target.value)} />
            </label>
            <div className="flex justify-end gap-2 pt-2">
              <Button variant="secondary" onClick={() => setOpen(false)}>
                {t("studio.flag.cancel_button")}
              </Button>
              <Button onClick={() => void onFlag()} disabled={saving}>
                {t("studio.flag.flag_button")}
              </Button>
            </div>
          </div>
        </Dialog>
      ) : null}
    </>
  );
}
```

- [ ] **Step 5: Wire FlagFieldMenu into Studio.tsx; drop the per-field Flag + ReportWrongFieldDialog**

In `frontend/src/pages/Studio.tsx`:

```tsx
import { FlagFieldMenu } from "@/components/FlagFieldMenu";
// drop: import { Flag } from "lucide-react";
// drop: import { ReportWrongFieldDialog } from "@/components/ReportWrongFieldDialog";
```

In `FieldRow`, replace the `<button … Flag>` block + trailing `ReportWrongFieldDialog` with:

```tsx
        <FlagFieldMenu
          projectId={projectId}
          entityIndex={entityIndex}
          fieldName={fieldName}
        />
```

Drop the local `reportOpen` state and the `useState`/dialog mount block.

- [ ] **Step 6: Delete the dead files**

```bash
git rm frontend/src/components/ReportWrongFieldDialog.tsx \
       frontend/src/__tests__/report_wrong_dialog.test.tsx
```

- [ ] **Step 7: Update i18n**

In `frontend/src/i18n/locales/en.json`, drop the `studio.report_wrong.*` block, add:

```json
    "flag": {
      "trigger_aria": "More actions for {{field}}",
      "dialog_title": "Flag this field",
      "dialog_hint": "Save a Lab annotation flagging this field without changing its value. Editing the textbox above is the way to correct a value; use this for issues that aren't a value-fix (e.g. unparseable output, field doesn't apply).",
      "issue_type_label": "Issue type",
      "comment_label": "Comment (optional)",
      "cancel_button": "Cancel",
      "flag_button": "Flag",
      "issue_type": {
        "wrong_value": "Wrong value",
        "missing_field": "Missing / N/A",
        "extra_field": "Extra field",
        "wrong_entity_count": "Wrong entity count",
        "other": "Other"
      }
    }
```

Place it inside the existing `studio` block, replacing the `report_wrong` key.

- [ ] **Step 8: Run frontend tests**

```bash
cd frontend && npm test -- --run
```

Expected: PASS. If `studio_save.test.tsx` references the Flag button or `ReportWrongFieldDialog`, update it (it shouldn't — but verify).

### Task B5: Commit B as one logical unit

- [ ] **Step 1: Run the full backend + frontend suite**

```bash
cd backend && uv run pytest -v
cd ../frontend && npm test -- --run
```

Both must PASS.

- [ ] **Step 2: Commit**

```bash
git add backend/app/schemas/readiness.py backend/app/services/readiness.py \
        backend/tests/test_readiness_routes.py \
        frontend/src/types/readiness.ts \
        frontend/src/components/ReadinessPanel.tsx \
        frontend/src/i18n/locales/en.json \
        frontend/src/pages/ApiConsole.tsx \
        frontend/src/pages/Studio.tsx \
        frontend/src/stores/studio.ts \
        frontend/src/components/FlagFieldMenu.tsx \
        frontend/src/__tests__/api_console.test.tsx \
        frontend/src/__tests__/readiness_panel.test.tsx \
        frontend/src/__tests__/flag_field_menu.test.tsx
git rm frontend/src/components/ReportWrongFieldDialog.tsx \
       frontend/src/__tests__/report_wrong_dialog.test.tsx
git commit -m "feat(ui): drop dual-affordance flag button, fix initial-publish diff copy, rename reviewed→annotated"
```

### Gate review for Commit B

Dispatch `superpowers:code-reviewer`:

> Review commit {hash} on `r8-productization-mvp` against dogfood follow-ups #3, #6, #7. Focus: (a) FlagFieldMenu does not silently dilute the vibe-check pool (Annotation gets saved with unchanged output — verify this is the intended design); (b) Contract Diff initial-publish copy reads naturally and the `tone="muted"` Badge avoids the false alarm; (c) backend rename is hard (no `reviewed_*` left anywhere). Run `cd frontend && npm test -- --run` and `cd backend && uv run pytest -v` and report any regressions.

---

## Commit C: #4 + #5 — Toast + Revoke confirmation

### Task C1: Toast wrapper + provider mount

**Files:**
- Create: `frontend/src/components/ui/Toast.tsx`
- Modify: `frontend/src/main.tsx`
- Modify: `frontend/src/i18n/locales/en.json`

- [ ] **Step 1: Create the Toast wrapper**

`frontend/src/components/ui/Toast.tsx`:

```tsx
import * as RadixToast from "@radix-ui/react-toast";
import { createContext, useCallback, useContext, useState, type ReactNode } from "react";

type ToastState = { id: number; message: string };

type ToastContextShape = { show: (message: string) => void };

const ToastCtx = createContext<ToastContextShape | null>(null);

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<ToastState[]>([]);
  const show = useCallback((message: string) => {
    setToasts((prev) => [...prev, { id: Date.now() + Math.random(), message }]);
  }, []);
  return (
    <ToastCtx.Provider value={{ show }}>
      <RadixToast.Provider duration={2000} swipeDirection="right">
        {children}
        {toasts.map((toast) => (
          <RadixToast.Root
            key={toast.id}
            onOpenChange={(o) =>
              !o && setToasts((prev) => prev.filter((t) => t.id !== toast.id))
            }
            className="rounded-md border border-border-default bg-bg-elevated px-3 py-2 text-sm text-fg-primary shadow-lg"
          >
            <RadixToast.Description>{toast.message}</RadixToast.Description>
          </RadixToast.Root>
        ))}
        <RadixToast.Viewport
          data-testid="toast-viewport"
          className="fixed top-4 right-4 flex w-80 max-w-[100vw] flex-col gap-2 outline-none"
        />
      </RadixToast.Provider>
    </ToastCtx.Provider>
  );
}

export function useToast(): ToastContextShape {
  const ctx = useContext(ToastCtx);
  if (ctx === null) {
    // No-op fallback so tests that don't mount the provider still pass; in
    // production the provider must wrap the app.
    return { show: () => undefined };
  }
  return ctx;
}
```

- [ ] **Step 2: Mount the provider**

In `frontend/src/main.tsx` wrap the existing `<App />` (or the router root) in `<ToastProvider>`. Read the file first to see the current root, then edit minimally.

- [ ] **Step 3: Add i18n key**

In `frontend/src/i18n/locales/en.json`, inside `common`:

```json
    "saved": "Saved",
```

(Single key — every save site reuses it. Don't multiply copy variants we don't need.)

### Task C2: Wire Toast into Studio + ApiConsole; add Revoke confirm dialog

**Files:**
- Modify: `frontend/src/pages/Studio.tsx`
- Modify: `frontend/src/pages/ApiConsole.tsx`
- Modify: `frontend/src/__tests__/studio_save.test.tsx`
- Modify: `frontend/src/__tests__/api_console.test.tsx`
- Create: `frontend/src/components/ConfirmRevokeKeyDialog.tsx`

- [ ] **Step 1: Update studio_save.test.tsx with the toast assertion**

Read the test, add an assertion that after save the text "Saved" appears in the toast viewport. Before adjusting the test wrap the rendered tree with `<ToastProvider>` (or assert against the no-op fallback if the test doesn't mount the provider — better to mount it for realism).

- [ ] **Step 2: Update api_console.test.tsx**

For Revoke: after clicking the original Revoke button, the test should now find a confirmation dialog with the dynamic copy "Revoke key 'default'?" (KEYS[0].name === "default"). Click the confirmation's primary button. Then assert (a) toast "Saved" appears; (b) the row disappears.

For Activate / Unpublish, optional toast asserts — only add if the tests already exercise those paths. Existing tests don't, so leave them; main scope is Revoke confirm.

- [ ] **Step 3: Run to verify they fail**

```bash
cd frontend && npm test -- studio_save api_console --run
```

Expected: FAIL — toast never shows; Revoke removes the row immediately without a confirmation dialog.

- [ ] **Step 4: Fire toast in Studio save success path**

In `frontend/src/pages/Studio.tsx`:

```tsx
import { useToast } from "@/components/ui/Toast";

// inside StudioPage, near other hooks:
const toast = useToast();

// replace onClick={() => void save(projectId)} with a wrapper:
async function handleSave() {
  const before = useStudio.getState().error;
  await save(projectId);
  // If save did not set an error, treat it as success.
  if (useStudio.getState().error === before) {
    toast.show(t("common.saved"));
  }
}
// header Button: onClick={() => void handleSave()}
```

(Equivalent for `flagField` if `FlagFieldMenu` should also fire the toast — wire `useToast()` inside `FlagFieldMenu`'s `onFlag`.)

- [ ] **Step 5: Add ConfirmRevokeKeyDialog**

`frontend/src/components/ConfirmRevokeKeyDialog.tsx`:

```tsx
import { Button } from "@/components/ui/Button";
import { Dialog } from "@/components/ui/Dialog";
import { useT } from "@/i18n/useT";

export function ConfirmRevokeKeyDialog({
  open,
  onOpenChange,
  keyName,
  onConfirm,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  keyName: string;
  onConfirm: () => void;
}) {
  const t = useT();
  return (
    <Dialog
      open={open}
      onOpenChange={onOpenChange}
      title={t("api_console.revoke_dialog_title")}
    >
      <div className="space-y-3 text-sm">
        <p className="text-fg-primary">
          {t("api_console.revoke_dialog_body", { name: keyName })}
        </p>
        <div className="flex justify-end gap-2 pt-2">
          <Button variant="secondary" onClick={() => onOpenChange(false)}>
            {t("common.cancel")}
          </Button>
          <Button variant="danger" onClick={onConfirm}>
            {t("api_console.revoke_dialog_confirm")}
          </Button>
        </div>
      </div>
    </Dialog>
  );
}
```

i18n additions inside `api_console`:

```json
    "revoke_dialog_title": "Revoke API key",
    "revoke_dialog_body": "Revoke key '{{name}}'? Integrators using this key will start getting 403 immediately.",
    "revoke_dialog_confirm": "Revoke",
```

- [ ] **Step 6: Wire the dialog into ApiConsole**

In `frontend/src/pages/ApiConsole.tsx`:

```tsx
import { ConfirmRevokeKeyDialog } from "@/components/ConfirmRevokeKeyDialog";
import { useToast } from "@/components/ui/Toast";

// inside ApiConsolePage:
const toast = useToast();
const [pendingRevoke, setPendingRevoke] = useState<{ id: number; name: string } | null>(null);

async function confirmRevoke() {
  if (pendingRevoke === null) return;
  setActionError(null);
  try {
    await revokeKey(projectId, pendingRevoke.id);
    toast.show(t("common.saved"));
    setPendingRevoke(null);
  } catch (e) {
    setActionError(emergeMessage(e));
  }
}

// Replace handleRevoke direct call with: setPendingRevoke({id: k.id, name: k.name})

// In the Revoke button:
<Button
  variant="ghost"
  size="sm"
  onClick={() => setPendingRevoke({ id: k.id, name: k.name })}
>
  {t("api_console.revoke_button")}
</Button>

// Mount near the ApiKeyRevealModal:
{pendingRevoke ? (
  <ConfirmRevokeKeyDialog
    open
    onOpenChange={(o) => !o && setPendingRevoke(null)}
    keyName={pendingRevoke.name}
    onConfirm={() => void confirmRevoke()}
  />
) : null}
```

Optionally fire toast on Activate / Unpublish success too — small win, low risk.

- [ ] **Step 7: Run frontend tests**

```bash
cd frontend && npm test -- --run
```

Expected: PASS.

- [ ] **Step 8: Mark hygiene-tail #13 as fixed**

In `docs/superpowers/plans/2026-05-04-r8-hygiene-tail.md` update the row for #13 (line ~30) to note the fix:

```
| 13 | gate-review (R8.1.d), smoke | `pages/Studio.tsx`, ApiConsole | ~~No save-success toast on Studio / Activate / Unpublish / Revoke. MVP fine; add a small `useToast` hook later.~~ Fixed in dogfood follow-up commit C ({hash}). |
```

- [ ] **Step 9: Commit**

```bash
git add frontend/src/components/ui/Toast.tsx \
        frontend/src/components/ConfirmRevokeKeyDialog.tsx \
        frontend/src/main.tsx \
        frontend/src/pages/Studio.tsx \
        frontend/src/pages/ApiConsole.tsx \
        frontend/src/i18n/locales/en.json \
        frontend/src/__tests__/studio_save.test.tsx \
        frontend/src/__tests__/api_console.test.tsx \
        docs/superpowers/plans/2026-05-04-r8-hygiene-tail.md
git commit -m "feat(ui): toast on save + Revoke confirmation dialog"
```

### Gate review for Commit C

Dispatch `superpowers:code-reviewer`:

> Review commit {hash} on `r8-productization-mvp` against dogfood #4 + #5. Focus: (a) Toast auto-dismisses (2s) and does not block subsequent saves; (b) Revoke confirmation copy interpolates the key name correctly and the dialog is dismissable on Esc/Cancel; (c) `useToast` no-op fallback is acceptable for tests that don't mount the provider; (d) hygiene-tail #13 row reflects the fix. Run the full vitest suite.

---

## Final smoke before opening PR

After all three commits land + gate reviews accepted:

- [ ] **Run release checklist + e2e**

```bash
./scripts/release-checklist.sh
EMERGE_E2E=1 ./scripts/release-checklist.sh
```

Both must exit 0.

- [ ] **Re-dogfood `docs/local-demo.md`**

Walk the doc end-to-end. Specifically confirm:
- A public `POST /extract/{api_code}` does NOT add a row to the editor's Documents list and the Readiness `annotated_*` counters do not move.
- The response body is `{request_id, prediction_id, project_version_id, output: {entities: [...]}}`.
- Studio shows ⋮ (no per-field flag icon); editing a value still works as the primary correction path.
- The first-publish Contract Diff section reads "Initial contract — no prior version to break." with muted-tone badges.
- Readiness EVIDENCE row shows "N annotated" and "M% with field evidence" without contradiction.
- Saving a correction shows a "Saved" pill that disappears in ~2s.
- Revoking a key now requires a confirm click and shows the success toast on completion.

- [ ] **Open PR**

```bash
git push -u origin r8-productization-mvp
gh pr create --title "R8 dogfood follow-ups #1–#7" --body "$(cat <<'EOF'
## Summary
- Workspace isolation: public-API extracts now create `Document.source='public_api'` and stay out of the editor's Documents list, vibe-check pool, and Readiness counts (#1).
- Public extract response wrapped in `{request_id, prediction_id, project_version_id, output: {entities}}` to match `docs/local-demo.md` (#2, breaking pre-GA).
- Studio: dropped the per-field "Report this field as wrong" button; editing the textbox is the correction path. Added ⋮ menu for flag-without-correcting (#3).
- API Console: initial-publish Contract Diff reads "Initial contract — no prior version" with muted badges instead of a breaking-change alarm (#6).
- Readiness: renamed `reviewed_*` → `annotated_*` so "annotated" and "with field evidence" no longer collide semantically (#7).
- Toast pill on Studio save + Revoke now requires a confirmation dialog (#4 + #5). Hygiene-tail #13 marked fixed.

#8 (real PDF preview) explicitly deferred per dogfood doc; tracked for v1.1.

## Test plan
- [ ] `cd backend && uv run pytest -v`
- [ ] `cd frontend && npm test -- --run`
- [ ] `./scripts/release-checklist.sh`
- [ ] `EMERGE_E2E=1 ./scripts/release-checklist.sh`
- [ ] Manual re-dogfood of `docs/local-demo.md` per checklist above.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

---

## Self-review (notes for the executor)

- **Spec coverage**: every dogfood numbered item maps to a task. #8 is explicitly out-of-scope here.
- **Schema rename safety**: `reviewed_*` → `annotated_*` is a hard rename. Grep before merging — `git grep reviewed_docs reviewed_entities reviewed_fields` should return zero hits in the diff's working tree.
- **Annotation pollution risk (Task B4)**: `flagField` saves an Annotation with unchanged output, which DOES cover the doc in the vibe-check pool when the schema is locked. That matches today's behavior of `reportWrong` (also covers via Annotation). If the gate reviewer pushes back, the alternative is a separate `lab_flags` table — out of scope for this batch unless the reviewer escalates.
- **AlertDialog deferral**: using `Dialog` for the Revoke confirmation keeps deps unchanged. If a future incident shows we need `role="alertdialog"`/escape-trap semantics, install `@radix-ui/react-alert-dialog` then.
- **Public response breaking change**: there are no integrators today (local demo only), so no migration shim. If a partner is added before this ships, gate it with `X-Emerge-API-Version`.
