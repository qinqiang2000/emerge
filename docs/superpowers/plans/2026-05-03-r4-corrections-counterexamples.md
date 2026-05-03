# R4 — Corrections & Counterexamples Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Plumb the user-correction path (Annotation `role=none`) and the counterexample-creation service that R7's public feedback endpoint will reuse. After R4: a user can save corrected JSON for any document and the resulting Annotations satisfy R3's lock heuristic and R5's calibration inputs.

**Architecture:**
- Two write paths feed `Annotation`: in-app correction (role=`none`) and feedback (role=`counterexample`).
- The two roles share a single service module (`services/corrections.py`) so R7 can route the public feedback endpoint through identical validation. **No fan-out logic** — Annotation is just persisted; no judge, no AutoResearch trigger here. Those wires hang off Annotation save in R5/R6.
- Annotation creation is **soft-delete-only**: status `cancelled` replaces hard deletion (spec §3.2 — counterexample references in `ProjectVersion.counterexample_ids` must remain resolvable even after a user "deletes" an Annotation).
- "Counterexample list" is a query view over `Annotation` filtered by `role='counterexample' AND status='saved'` (spec §3.1). We do not introduce a separate table.

**Tech Stack:** R1+R2+R3 stack only. No new deps.

**Spec sections covered:** §1 (counterexample = role=`counterexample` Annotation; **never enters runtime prompt**), §3.1 (Annotation columns + role/status enums), §3.2 (`role` enforced via DB CHECK; soft-delete via `status='cancelled'`; no Annotation count cap), §2.4 (description **not** auto-derived from JSON; corrections only update Annotation), §7.1 (the `/extract/{api_code}/feedback` endpoint creates `Annotation` with role=`counterexample` — R4 builds the service; R7 wires the public route).

**Depends on:** R3 (ProjectVersion exists, prediction write path exists; lock heuristic consumes saved Annotations).

---

## File Structure

New backend files:

```
backend/app/
├── schemas/
│   └── annotation.py             # AnnotationIn / AnnotationOut / FeedbackIn
├── services/
│   └── corrections.py            # save_correction(), save_counterexample()
├── api/routes/
│   └── annotations.py            # POST/GET /projects/{pid}/documents/{did}/annotations
│                                 # PATCH/DELETE /projects/{pid}/annotations/{id}
│                                 # GET /projects/{pid}/counterexamples
└── alembic/versions/             # no new migration — schema came in R2's 0006
```

Tests:

```
backend/tests/
├── test_corrections_service.py
├── test_annotation_routes.py
└── test_counterexample_list.py
```

---

## Task 1: AnnotationIn/Out + FeedbackIn pydantic schemas

**Files:**
- Create: `backend/app/schemas/annotation.py`
- Create: `backend/tests/test_annotation_schemas.py`

`AnnotationIn.output` is `list[dict]` with no schema validation at this layer — the LLM-generated / user-edited JSON shape isn't strictly typed in v1. Validation against the schema happens implicitly via the responseSchema on the *next* extraction; corrected outputs are accepted as-is.

- [ ] **Step 1: Write the failing test**

```python
import pytest
from pydantic import ValidationError

from app.schemas.annotation import AnnotationIn, FeedbackIn


def test_annotation_in_minimum():
    a = AnnotationIn(output=[{"x": 1}])
    assert a.notes is None


def test_annotation_in_rejects_non_array_root():
    with pytest.raises(ValidationError):
        AnnotationIn(output={"x": 1})  # must be list


def test_annotation_in_rejects_non_object_entries():
    with pytest.raises(ValidationError):
        AnnotationIn(output=["x", "y"])  # entries must be objects


def test_feedback_in_requires_correct_output_array():
    fb = FeedbackIn(request_id=1, correct_output=[{"shop": "X"}])
    assert fb.request_id == 1
    with pytest.raises(ValidationError):
        FeedbackIn(request_id=1, correct_output={"x": 1})
```

- [ ] **Step 2: Run — expect ImportError**

- [ ] **Step 3: Implement `app/schemas/annotation.py`**

```python
from datetime import datetime

from pydantic import BaseModel, Field, field_validator


def _validate_array_of_object(v):
    if not isinstance(v, list):
        raise ValueError("output must be an array")
    if not all(isinstance(e, dict) for e in v):
        raise ValueError("output entries must be objects")
    return v


class AnnotationIn(BaseModel):
    output: list[dict]
    notes: str | None = None
    parent_prediction_id: int | None = None

    @field_validator("output", mode="before")
    @classmethod
    def _check(cls, v):
        return _validate_array_of_object(v)


class AnnotationOut(BaseModel):
    id: int
    document_id: int
    parent_prediction_id: int | None
    output: list[dict]
    role: str
    status: str
    notes: str | None
    created_by: int
    created_at: datetime
    last_modified_at: datetime

    model_config = {"from_attributes": True}


class FeedbackIn(BaseModel):
    request_id: int = Field(description="prediction_id returned by /extract")
    correct_output: list[dict]
    notes: str | None = None

    @field_validator("correct_output", mode="before")
    @classmethod
    def _check(cls, v):
        return _validate_array_of_object(v)
```

- [ ] **Step 4: Run test to verify it passes**

- [ ] **Step 5: Commit**

```bash
git add backend/app/schemas/annotation.py backend/tests/test_annotation_schemas.py
git commit -m "feat(backend): add Annotation/Feedback pydantic schemas"
```

---

## Task 2: corrections service — save_correction + save_counterexample

**Files:**
- Create: `backend/app/services/corrections.py`
- Create: `backend/tests/test_corrections_service.py`

Two functions; both write `Annotation` rows. `save_counterexample` validates that the supplied `prediction_id` belongs to the supplied `project_id` so R7's public feedback endpoint can rely on this guard.

- [ ] **Step 1: Write the failing tests**

```python
import pytest

from app.models.annotation import Annotation, AnnotationRole, AnnotationStatus
from app.models.document import Document
from app.models.prediction import Prediction, PredictionStatus
from app.models.project import Project
from app.models.project_version import ProjectVersion, VersionSource
from app.models.user import User
from app.models.workspace import Workspace
from app.services.corrections import (
    PredictionScopeError,
    save_correction,
    save_counterexample,
)


async def _scaffold(db_session) -> tuple[int, int, int]:
    """Returns (user_id, project_id, document_id)."""
    user = User(email="c@c.com", password_hash="x")
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
        source=VersionSource.INITIAL.value,
        source_metadata={},
        created_by=user.id,
    )
    db_session.add(v)
    await db_session.flush()
    p.active_version_id = v.id
    d = Document(
        project_id=p.id,
        filename="f",
        file_path="/tmp/f",
        mime_type="application/pdf",
        page_count=1,
        byte_size=1,
        uploaded_by=user.id,
    )
    db_session.add(d)
    await db_session.commit()
    return user.id, p.id, d.id


@pytest.mark.asyncio
async def test_save_correction_creates_role_none(db_session):
    uid, pid, did = await _scaffold(db_session)
    ann = await save_correction(
        session=db_session,
        document_id=did,
        output=[{"shop_name": "X"}],
        user_id=uid,
        notes="manual edit",
    )
    assert ann.role == AnnotationRole.NONE.value
    assert ann.status == AnnotationStatus.SAVED.value
    assert ann.created_by == uid
    assert ann.last_modified_by == uid


@pytest.mark.asyncio
async def test_save_counterexample_creates_role_counterexample(db_session):
    uid, pid, did = await _scaffold(db_session)
    pred = Prediction(
        document_id=did,
        project_version_id=None,
        model_id="m",
        prompt_hash="h",
        output=[{"a": 1}],
        per_field_confidence={},
        status=PredictionStatus.SUCCESS.value,
    )
    db_session.add(pred)
    await db_session.commit()

    ann = await save_counterexample(
        session=db_session,
        project_id=pid,
        prediction_id=pred.id,
        correct_output=[{"a": 99}],
        user_id=uid,
    )
    assert ann.role == AnnotationRole.COUNTEREXAMPLE.value
    assert ann.parent_prediction_id == pred.id


@pytest.mark.asyncio
async def test_save_counterexample_rejects_cross_project_prediction(db_session):
    uid, pid_a, did_a = await _scaffold(db_session)
    # second project + prediction
    user2 = User(email="z@z.com", password_hash="x")
    db_session.add(user2)
    await db_session.flush()
    ws2 = Workspace(name="W2", owner_id=user2.id)
    db_session.add(ws2)
    await db_session.flush()
    p2 = Project(workspace_id=ws2.id, name="P2", created_by=user2.id)
    db_session.add(p2)
    await db_session.flush()
    d2 = Document(
        project_id=p2.id,
        filename="f",
        file_path="/tmp/f",
        mime_type="application/pdf",
        page_count=1,
        byte_size=1,
        uploaded_by=user2.id,
    )
    db_session.add(d2)
    await db_session.flush()
    pred = Prediction(
        document_id=d2.id,
        project_version_id=None,
        model_id="m",
        prompt_hash="h",
        output=[],
        per_field_confidence={},
        status=PredictionStatus.SUCCESS.value,
    )
    db_session.add(pred)
    await db_session.commit()

    with pytest.raises(PredictionScopeError):
        await save_counterexample(
            session=db_session,
            project_id=pid_a,
            prediction_id=pred.id,
            correct_output=[{"x": 1}],
            user_id=uid,
        )
```

- [ ] **Step 2: Run — expect ImportError**

- [ ] **Step 3: Implement `app/services/corrections.py`**

```python
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.annotation import Annotation, AnnotationRole, AnnotationStatus
from app.models.document import Document
from app.models.prediction import Prediction


class PredictionScopeError(Exception):
    """Prediction does not belong to the supplied project."""


async def save_correction(
    *,
    session: AsyncSession,
    document_id: int,
    output: list[dict],
    user_id: int,
    notes: str | None = None,
    parent_prediction_id: int | None = None,
) -> Annotation:
    ann = Annotation(
        document_id=document_id,
        parent_prediction_id=parent_prediction_id,
        output=output,
        role=AnnotationRole.NONE.value,
        status=AnnotationStatus.SAVED.value,
        notes=notes,
        created_by=user_id,
        last_modified_by=user_id,
    )
    session.add(ann)
    await session.commit()
    await session.refresh(ann)
    return ann


async def save_counterexample(
    *,
    session: AsyncSession,
    project_id: int,
    prediction_id: int,
    correct_output: list[dict],
    user_id: int,
    notes: str | None = None,
) -> Annotation:
    pred = (
        await session.execute(
            select(Prediction).where(Prediction.id == prediction_id)
        )
    ).scalar_one_or_none()
    if pred is None:
        raise PredictionScopeError(f"prediction {prediction_id} not found")
    doc = (
        await session.execute(select(Document).where(Document.id == pred.document_id))
    ).scalar_one()
    if doc.project_id != project_id:
        raise PredictionScopeError(
            f"prediction {prediction_id} does not belong to project {project_id}"
        )
    ann = Annotation(
        document_id=doc.id,
        parent_prediction_id=pred.id,
        output=correct_output,
        role=AnnotationRole.COUNTEREXAMPLE.value,
        status=AnnotationStatus.SAVED.value,
        notes=notes,
        created_by=user_id,
        last_modified_by=user_id,
    )
    session.add(ann)
    await session.commit()
    await session.refresh(ann)
    return ann
```

- [ ] **Step 4: Run test to verify it passes**

Expected: `3 passed`.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/corrections.py backend/tests/test_corrections_service.py
git commit -m "feat(backend): add corrections service (save_correction / save_counterexample)"
```

---

## Task 3: Annotation save + list endpoints (in-app correction)

**Files:**
- Create: `backend/app/api/routes/annotations.py`
- Modify: `backend/app/api/v1.py` (mount)
- Create: `backend/tests/test_annotation_routes.py`

Routes:
- `POST /api/v1/projects/{pid}/documents/{did}/annotations` → save correction (role=`none`)
- `GET /api/v1/projects/{pid}/documents/{did}/annotations` → list per document
- `PATCH /api/v1/projects/{pid}/annotations/{id}` → update output / notes (preserves role)
- `DELETE /api/v1/projects/{pid}/annotations/{id}` → soft-delete (status=`cancelled`)

- [ ] **Step 1: Write the failing tests**

```python
import io

import pytest


async def _scaffold(client, tmp_path, monkeypatch) -> tuple[dict, int, int]:
    monkeypatch.setattr("app.services.storage.settings.storage_root", str(tmp_path))
    await client.post(
        "/api/v1/auth/register", json={"email": "a@a.com", "password": "hunter22"}
    )
    tok = (
        await client.post(
            "/api/v1/auth/login", json={"email": "a@a.com", "password": "hunter22"}
        )
    ).json()["access_token"]
    h = {"Authorization": f"Bearer {tok}"}
    pid = (await client.post("/api/v1/projects", json={"name": "P"}, headers=h)).json()["id"]
    did = (
        await client.post(
            f"/api/v1/projects/{pid}/documents",
            files=[("files", ("a.pdf", io.BytesIO(b"AA"), "application/pdf"))],
            headers=h,
        )
    ).json()[0]["id"]
    return h, pid, did


@pytest.mark.asyncio
async def test_save_correction(client, tmp_path, monkeypatch):
    h, pid, did = await _scaffold(client, tmp_path, monkeypatch)
    resp = await client.post(
        f"/api/v1/projects/{pid}/documents/{did}/annotations",
        json={"output": [{"shop_name": "ABC"}], "notes": "fixed shop"},
        headers=h,
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["role"] == "none"
    assert body["status"] == "saved"
    assert body["output"] == [{"shop_name": "ABC"}]


@pytest.mark.asyncio
async def test_list_annotations(client, tmp_path, monkeypatch):
    h, pid, did = await _scaffold(client, tmp_path, monkeypatch)
    await client.post(
        f"/api/v1/projects/{pid}/documents/{did}/annotations",
        json={"output": [{"a": 1}]},
        headers=h,
    )
    await client.post(
        f"/api/v1/projects/{pid}/documents/{did}/annotations",
        json={"output": [{"a": 2}]},
        headers=h,
    )
    resp = await client.get(
        f"/api/v1/projects/{pid}/documents/{did}/annotations", headers=h
    )
    assert resp.status_code == 200
    assert len(resp.json()) == 2


@pytest.mark.asyncio
async def test_patch_annotation(client, tmp_path, monkeypatch):
    h, pid, did = await _scaffold(client, tmp_path, monkeypatch)
    aid = (
        await client.post(
            f"/api/v1/projects/{pid}/documents/{did}/annotations",
            json={"output": [{"a": 1}]},
            headers=h,
        )
    ).json()["id"]
    resp = await client.patch(
        f"/api/v1/projects/{pid}/annotations/{aid}",
        json={"output": [{"a": 99}], "notes": "amended"},
        headers=h,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["output"] == [{"a": 99}]
    assert body["notes"] == "amended"


@pytest.mark.asyncio
async def test_delete_annotation_soft_deletes(client, tmp_path, monkeypatch):
    h, pid, did = await _scaffold(client, tmp_path, monkeypatch)
    aid = (
        await client.post(
            f"/api/v1/projects/{pid}/documents/{did}/annotations",
            json={"output": [{"a": 1}]},
            headers=h,
        )
    ).json()["id"]
    resp = await client.delete(f"/api/v1/projects/{pid}/annotations/{aid}", headers=h)
    assert resp.status_code == 200
    assert resp.json()["status"] == "cancelled"

    listing = await client.get(
        f"/api/v1/projects/{pid}/documents/{did}/annotations", headers=h
    )
    assert all(a["status"] != "cancelled" for a in listing.json())  # default filter excludes


@pytest.mark.asyncio
async def test_cross_project_annotation_404(client, tmp_path, monkeypatch):
    h, pid, did = await _scaffold(client, tmp_path, monkeypatch)
    # second user
    await client.post("/api/v1/auth/register", json={"email": "z@z.com", "password": "hunter22"})
    tok = (
        await client.post("/api/v1/auth/login", json={"email": "z@z.com", "password": "hunter22"})
    ).json()["access_token"]
    h2 = {"Authorization": f"Bearer {tok}"}
    resp = await client.post(
        f"/api/v1/projects/{pid}/documents/{did}/annotations",
        json={"output": [{"x": 1}]},
        headers=h2,
    )
    assert resp.status_code == 404
```

- [ ] **Step 2: Run — expect 404**

- [ ] **Step 3: Implement `app/api/routes/annotations.py`**

```python
from fastapi import APIRouter, Depends, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import current_user, current_workspace_id
from app.db import get_session
from app.errors import EmergeError, ErrorCode
from app.models.annotation import Annotation, AnnotationStatus
from app.models.document import Document
from app.models.project import Project
from app.models.user import User
from app.schemas.annotation import AnnotationIn, AnnotationOut
from app.services.corrections import save_correction

router = APIRouter(prefix="/projects/{project_id}", tags=["annotations"])


async def _project_or_404(session, project_id, workspace_id) -> Project:
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


async def _document_in_project(session, project_id, document_id) -> Document:
    d = (
        await session.execute(
            select(Document).where(
                Document.id == document_id, Document.project_id == project_id
            )
        )
    ).scalar_one_or_none()
    if d is None:
        raise EmergeError(ErrorCode.NOT_FOUND, status_code=404)
    return d


async def _annotation_in_project(session, project_id, annotation_id) -> Annotation:
    ann = (
        await session.execute(
            select(Annotation)
            .join(Document, Document.id == Annotation.document_id)
            .where(Annotation.id == annotation_id, Document.project_id == project_id)
        )
    ).scalar_one_or_none()
    if ann is None:
        raise EmergeError(ErrorCode.NOT_FOUND, status_code=404)
    return ann


@router.post(
    "/documents/{document_id}/annotations",
    response_model=AnnotationOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_annotation(
    project_id: int,
    document_id: int,
    payload: AnnotationIn,
    user: User = Depends(current_user),
    workspace_id: int = Depends(current_workspace_id),
    session: AsyncSession = Depends(get_session),
):
    await _project_or_404(session, project_id, workspace_id)
    await _document_in_project(session, project_id, document_id)
    ann = await save_correction(
        session=session,
        document_id=document_id,
        output=payload.output,
        user_id=user.id,
        notes=payload.notes,
        parent_prediction_id=payload.parent_prediction_id,
    )
    return ann


@router.get(
    "/documents/{document_id}/annotations", response_model=list[AnnotationOut]
)
async def list_annotations(
    project_id: int,
    document_id: int,
    workspace_id: int = Depends(current_workspace_id),
    session: AsyncSession = Depends(get_session),
):
    await _project_or_404(session, project_id, workspace_id)
    await _document_in_project(session, project_id, document_id)
    rows = (
        await session.execute(
            select(Annotation)
            .where(
                Annotation.document_id == document_id,
                Annotation.status != AnnotationStatus.CANCELLED.value,
            )
            .order_by(Annotation.id.desc())
        )
    ).scalars().all()
    return [AnnotationOut.model_validate(a) for a in rows]


class AnnotationPatchIn(BaseModel):
    output: list[dict] | None = None
    notes: str | None = None


@router.patch("/annotations/{annotation_id}", response_model=AnnotationOut)
async def patch_annotation(
    project_id: int,
    annotation_id: int,
    payload: AnnotationPatchIn,
    user: User = Depends(current_user),
    workspace_id: int = Depends(current_workspace_id),
    session: AsyncSession = Depends(get_session),
):
    await _project_or_404(session, project_id, workspace_id)
    ann = await _annotation_in_project(session, project_id, annotation_id)
    if payload.output is not None:
        ann.output = payload.output
    if payload.notes is not None:
        ann.notes = payload.notes
    ann.last_modified_by = user.id
    await session.commit()
    await session.refresh(ann)
    return ann


@router.delete("/annotations/{annotation_id}", response_model=AnnotationOut)
async def delete_annotation(
    project_id: int,
    annotation_id: int,
    user: User = Depends(current_user),
    workspace_id: int = Depends(current_workspace_id),
    session: AsyncSession = Depends(get_session),
):
    await _project_or_404(session, project_id, workspace_id)
    ann = await _annotation_in_project(session, project_id, annotation_id)
    ann.status = AnnotationStatus.CANCELLED.value
    ann.last_modified_by = user.id
    await session.commit()
    await session.refresh(ann)
    return ann
```

- [ ] **Step 4: Mount router in `app/api/v1.py`**

```python
from app.api.routes import annotations

api_v1.include_router(annotations.router)
```

- [ ] **Step 5: Run tests to verify they pass**

Expected: `5 passed`.

- [ ] **Step 6: Commit**

```bash
git add backend/app/api/routes/annotations.py backend/app/api/v1.py backend/tests/test_annotation_routes.py
git commit -m "feat(api): annotation save/list/patch/soft-delete (role=none)"
```

---

## Task 4: Counterexample list endpoint

**Files:**
- Modify: `backend/app/api/routes/annotations.py` (append `GET /projects/{pid}/counterexamples`)
- Create: `backend/tests/test_counterexample_list.py`

This endpoint exists for the UI surface and for AutoResearch's regression test set lookup in R5/R6. Unlike the per-document list, this view is project-scoped and filters strictly to `role='counterexample' AND status='saved'`.

- [ ] **Step 1: Write the failing test**

```python
import io

import pytest

from app.models.annotation import Annotation, AnnotationRole, AnnotationStatus
from app.models.prediction import Prediction, PredictionStatus
from sqlalchemy import select


@pytest.mark.asyncio
async def test_counterexample_list_excludes_role_none_and_cancelled(
    client, db_session, tmp_path, monkeypatch
):
    monkeypatch.setattr("app.services.storage.settings.storage_root", str(tmp_path))
    await client.post("/api/v1/auth/register", json={"email": "ce@ce.com", "password": "hunter22"})
    tok = (
        await client.post("/api/v1/auth/login", json={"email": "ce@ce.com", "password": "hunter22"})
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

    # save a regular correction (role=none)
    await client.post(
        f"/api/v1/projects/{pid}/documents/{did}/annotations",
        json={"output": [{"a": 1}]},
        headers=h,
    )

    # seed a Prediction + a counterexample directly
    from app.models.user import User

    user_id = (await db_session.execute(select(User))).scalar_one().id
    pred = Prediction(
        document_id=did,
        model_id="m",
        prompt_hash="h",
        output=[{"a": 1}],
        per_field_confidence={},
        status=PredictionStatus.SUCCESS.value,
    )
    db_session.add(pred)
    await db_session.flush()
    db_session.add(
        Annotation(
            document_id=did,
            parent_prediction_id=pred.id,
            output=[{"a": 99}],
            role=AnnotationRole.COUNTEREXAMPLE.value,
            status=AnnotationStatus.SAVED.value,
            created_by=user_id,
            last_modified_by=user_id,
        )
    )
    db_session.add(
        Annotation(
            document_id=did,
            parent_prediction_id=pred.id,
            output=[{"a": 88}],
            role=AnnotationRole.COUNTEREXAMPLE.value,
            status=AnnotationStatus.CANCELLED.value,
            created_by=user_id,
            last_modified_by=user_id,
        )
    )
    await db_session.commit()

    resp = await client.get(f"/api/v1/projects/{pid}/counterexamples", headers=h)
    assert resp.status_code == 200
    rows = resp.json()
    assert len(rows) == 1
    assert rows[0]["output"] == [{"a": 99}]
    assert rows[0]["role"] == "counterexample"
```

- [ ] **Step 2: Run — expect 404**

- [ ] **Step 3: Append endpoint to `app/api/routes/annotations.py`**

```python
@router.get("/counterexamples", response_model=list[AnnotationOut])
async def list_counterexamples(
    project_id: int,
    workspace_id: int = Depends(current_workspace_id),
    session: AsyncSession = Depends(get_session),
):
    await _project_or_404(session, project_id, workspace_id)
    rows = (
        await session.execute(
            select(Annotation)
            .join(Document, Document.id == Annotation.document_id)
            .where(
                Document.project_id == project_id,
                Annotation.role == "counterexample",
                Annotation.status == AnnotationStatus.SAVED.value,
            )
            .order_by(Annotation.id.desc())
        )
    ).scalars().all()
    return [AnnotationOut.model_validate(a) for a in rows]
```

- [ ] **Step 4: Run test to verify it passes**

- [ ] **Step 5: Commit**

```bash
git add backend/app/api/routes/annotations.py backend/tests/test_counterexample_list.py
git commit -m "feat(api): counterexample list endpoint scoped to project"
```

---

## Task 5: Internal counterexample-create endpoint (admin-only path)

**Files:**
- Modify: `backend/app/api/routes/annotations.py` (append `POST /projects/{pid}/counterexamples`)
- Modify: `backend/tests/test_counterexample_list.py` (append create test)

This internal endpoint mirrors what the public feedback API will do in R7: takes `prediction_id + correct_output`, calls `save_counterexample`. Splitting the public route from the internal one means R7 can reuse the same service while changing only auth (key vs JWT) and rate-limiting.

- [ ] **Step 1: Append failing test**

```python
@pytest.mark.asyncio
async def test_create_counterexample_endpoint(client, db_session, tmp_path, monkeypatch):
    monkeypatch.setattr("app.services.storage.settings.storage_root", str(tmp_path))
    await client.post("/api/v1/auth/register", json={"email": "f@f.com", "password": "hunter22"})
    tok = (
        await client.post("/api/v1/auth/login", json={"email": "f@f.com", "password": "hunter22"})
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
    # seed a prediction
    from app.models.prediction import Prediction, PredictionStatus

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

    resp = await client.post(
        f"/api/v1/projects/{pid}/counterexamples",
        json={"request_id": pred.id, "correct_output": [{"a": 99}]},
        headers=h,
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["role"] == "counterexample"
    assert body["parent_prediction_id"] == pred.id
```

- [ ] **Step 2: Run — expect 404**

- [ ] **Step 3: Append endpoint**

In `app/api/routes/annotations.py`:

```python
from app.schemas.annotation import FeedbackIn
from app.services.corrections import PredictionScopeError, save_counterexample


@router.post(
    "/counterexamples",
    response_model=AnnotationOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_counterexample(
    project_id: int,
    payload: FeedbackIn,
    user: User = Depends(current_user),
    workspace_id: int = Depends(current_workspace_id),
    session: AsyncSession = Depends(get_session),
):
    await _project_or_404(session, project_id, workspace_id)
    try:
        ann = await save_counterexample(
            session=session,
            project_id=project_id,
            prediction_id=payload.request_id,
            correct_output=payload.correct_output,
            user_id=user.id,
            notes=payload.notes,
        )
    except PredictionScopeError as e:
        raise EmergeError(
            ErrorCode.VALIDATION_FAILED, status_code=422, message_override=str(e)
        ) from e
    return ann
```

- [ ] **Step 4: Run test to verify it passes**

- [ ] **Step 5: Commit**

```bash
git add backend/app/api/routes/annotations.py backend/tests/test_counterexample_list.py
git commit -m "feat(api): internal counterexample create endpoint reusing save_counterexample"
```

---

## Task 6: Wire latest_annotation into Document detail

**Files:**
- Modify: `backend/app/api/routes/documents.py` (populate `latest_annotation`)
- Modify: `backend/tests/test_document_routes.py` (post-correction assertion)

Spec §3 the Document detail surfaces "the most recent saved correction" so the UI can mark a row as "已矫正". Latest = most recent `Annotation` with `role='none' AND status='saved'`.

- [ ] **Step 1: Append failing test**

```python
@pytest.mark.asyncio
async def test_document_detail_includes_latest_annotation_after_save(
    client, tmp_path, monkeypatch
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

    await client.post(
        f"/api/v1/projects/{pid}/documents/{did}/annotations",
        json={"output": [{"shop_name": "ABC"}]},
        headers=h,
    )

    resp = await client.get(f"/api/v1/projects/{pid}/documents/{did}", headers=h)
    body = resp.json()
    assert body["latest_annotation"]["output"] == [{"shop_name": "ABC"}]
    assert body["latest_annotation"]["role"] == "none"
```

- [ ] **Step 2: Run — expect failure**

- [ ] **Step 3: Update `get_document` in `app/api/routes/documents.py`**

Replace `payload["latest_annotation"] = None` with:

```python
from app.models.annotation import Annotation, AnnotationStatus

latest_ann = (
    await session.execute(
        select(Annotation)
        .where(
            Annotation.document_id == d.id,
            Annotation.role == "none",
            Annotation.status == AnnotationStatus.SAVED.value,
        )
        .order_by(Annotation.id.desc())
        .limit(1)
    )
).scalar_one_or_none()
payload["latest_annotation"] = (
    {
        "id": latest_ann.id,
        "output": latest_ann.output,
        "role": latest_ann.role,
        "notes": latest_ann.notes,
    }
    if latest_ann
    else None
)
```

- [ ] **Step 4: Run test to verify it passes**

- [ ] **Step 5: Run full suite**

Run: `cd backend && uv run pytest -v`
Expected: every R1+R2+R3+R4 test passes.

- [ ] **Step 6: Commit**

```bash
git add backend/app/api/routes/documents.py backend/tests/test_document_routes.py
git commit -m "feat(api): populate latest_annotation on document detail"
```

---

## R4 exit criteria

End-to-end:

1. Upload + extract a doc (R3) → call `POST /annotations` to save corrected JSON → `Annotation` row exists with `role=none, status=saved`.
2. Save 2 corrections agreeing on the same field set → `GET /lock-status` (R3) returns `can_lock=true`.
3. Seed a `Prediction` and call `POST /projects/{pid}/counterexamples` with the prediction id → returns Annotation `role=counterexample`.
4. `GET /projects/{pid}/counterexamples` returns only role=counterexample saved rows; cancelled and role=none excluded.
5. `PATCH /annotations/{id}` updates output; `DELETE /annotations/{id}` flips status to cancelled but row persists.
6. `GET /documents/{did}` shows `latest_annotation.output` after correction.

Run `cd backend && uv run pytest -v` — all tests R1+R2+R3+R4 pass.

R5 builds on this: judge runs over predictions, counterexample regression iterates over the rows returned by `GET /counterexamples`, calibration accumulates from human verdicts on annotation save. R6's AutoResearch consumes the saved annotations as `state.counterexample_set`. R7's public `/extract/{api_code}/feedback` route delegates to `save_counterexample` from this slice.
