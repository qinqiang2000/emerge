# R2 — Project & Document Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stand up the four core tables (`Project`, `Document`, `Prediction`, `Annotation`) and the CRUD endpoints needed to create projects, upload documents in batch, and list them — without yet running extraction or saving corrections (those land in R3 and R4).

**Architecture:** Each `Project` is scoped to a `Workspace`; the auth dependency from R1 (`current_workspace_id`) drives tenant isolation. Documents are stored on local disk under `settings.storage_root` (one folder per project), with metadata in DB. `Prediction` and `Annotation` tables are introduced as empty tables in R2 — their write paths come in R3/R4 — so that all four tables exist together in one alembic revision and later slices add behaviour, not schema.

**Tech Stack:** Same as R1 (FastAPI / async SQLAlchemy / aiosqlite / pydantic v2). New: `python-multipart` (already in deps for R1) for file upload, plus `pathlib` / `aiofiles`-equivalent (we use sync `open` wrapped via `asyncio.to_thread` to avoid the extra dep — file I/O is not a hot path here).

**Spec sections covered:** §3.1 (Project / Document / Prediction / Annotation tables), §3.2 (key invariants — at least one ProjectVersion per Project, but the version itself is created lazily in R3), §8.0 (普通用户 URL 不带 workspace_id — backend resolves implicitly), §8.1 (Document list view → drives the list endpoint shape).

**Depends on:** R1 (auth, error envelope, db session, current_workspace_id dep).

---

## File Structure

New backend files added on top of R1 layout:

```
backend/app/
├── models/
│   ├── project.py             # Project (active_version_id nullable in R2; wired in R3)
│   ├── document.py            # Document
│   ├── prediction.py          # Prediction (table only; write path in R3)
│   └── annotation.py          # Annotation (table only; write path in R4)
├── schemas/
│   ├── project.py             # ProjectIn / ProjectOut
│   └── document.py            # DocumentOut, DocumentStatus
├── api/routes/
│   ├── projects.py            # POST/GET /api/v1/projects, GET /api/v1/projects/{id}
│   └── documents.py           # POST/GET /api/v1/projects/{id}/documents
└── services/
    ├── __init__.py
    └── storage.py             # save_upload(file, project_id) -> file_path
```

New migrations:

```
backend/alembic/versions/
├── 0003_project.py
├── 0004_document.py
├── 0005_prediction.py
└── 0006_annotation.py
```

Tests:

```
backend/tests/
├── test_project_model.py
├── test_project_routes.py
├── test_document_model.py
├── test_document_routes.py
├── test_prediction_model.py
└── test_annotation_model.py
```

The split into per-aggregate files keeps each file <100 lines and gives R3/R4/R5 a natural place to extend (e.g. R3 adds `ProjectVersion` next to `Project`).

---

## Task 1: Project model + migration

**Files:**
- Create: `backend/app/models/project.py`
- Modify: `backend/app/models/__init__.py`
- Create: `backend/alembic/versions/0003_project.py`
- Create: `backend/tests/test_project_model.py`

`active_version_id` and `template_id` are nullable in this migration. R3 will add the FK target table and may add a NOT-VALID constraint via a follow-up migration. `api_code` is unique scoped per workspace.

- [ ] **Step 1: Write the failing test**

```python
import pytest

from app.models.project import Project
from app.models.user import User
from app.models.workspace import Workspace


@pytest.mark.asyncio
async def test_project_persists(db_session):
    user = User(email="o@o.com", password_hash="x")
    db_session.add(user)
    await db_session.flush()
    ws = Workspace(name="W", owner_id=user.id)
    db_session.add(ws)
    await db_session.flush()
    p = Project(workspace_id=ws.id, name="Receipts", created_by=user.id)
    db_session.add(p)
    await db_session.commit()
    await db_session.refresh(p)
    assert p.id is not None
    assert p.api_code is None
    assert p.active_version_id is None


@pytest.mark.asyncio
async def test_api_code_is_unique_per_workspace(db_session):
    user = User(email="u@u.com", password_hash="x")
    db_session.add(user)
    await db_session.flush()
    ws = Workspace(name="W", owner_id=user.id)
    db_session.add(ws)
    await db_session.flush()
    db_session.add(Project(workspace_id=ws.id, name="A", created_by=user.id, api_code="x"))
    await db_session.commit()
    db_session.add(Project(workspace_id=ws.id, name="B", created_by=user.id, api_code="x"))
    with pytest.raises(Exception):
        await db_session.commit()
```

- [ ] **Step 2: Run — expect ImportError**

Run: `cd backend && uv run pytest tests/test_project_model.py -v`
Expected: `ModuleNotFoundError: app.models.project`.

- [ ] **Step 3: Implement `app/models/project.py`**

```python
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class Project(Base, TimestampMixin):
    __tablename__ = "projects"
    __table_args__ = (
        UniqueConstraint("workspace_id", "api_code", name="uq_project_workspace_api_code"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    workspace_id: Mapped[int] = mapped_column(
        ForeignKey("workspaces.id"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)

    template_id: Mapped[int | None] = mapped_column(nullable=True)  # FK added in R7
    active_version_id: Mapped[int | None] = mapped_column(nullable=True)  # FK added in R3
    api_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    api_published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
```

Re-export in `app/models/__init__.py`:

```python
from app.models.project import Project
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/test_project_model.py -v`
Expected: `2 passed`.

- [ ] **Step 5: Generate + apply migration**

```bash
cd backend && uv run alembic revision --autogenerate -m "project table"
# rename to 0003_project.py, set revision="0003" down_revision="0002"
uv run alembic upgrade head
```

- [ ] **Step 6: Commit**

```bash
git add backend/app/models/project.py backend/app/models/__init__.py backend/alembic/versions/0003_project.py backend/tests/test_project_model.py
git commit -m "feat(backend): add Project model + 0003 migration"
```

---

## Task 2: Project create + list endpoints

**Files:**
- Create: `backend/app/schemas/project.py`
- Create: `backend/app/api/routes/projects.py`
- Modify: `backend/app/api/v1.py` (mount projects router)
- Create: `backend/tests/test_project_routes.py`

- [ ] **Step 1: Write the failing tests**

```python
import pytest


async def _auth(client, email="p@p.com"):
    await client.post("/api/v1/auth/register", json={"email": email, "password": "hunter22"})
    tok = (
        await client.post("/api/v1/auth/login", json={"email": email, "password": "hunter22"})
    ).json()["access_token"]
    return {"Authorization": f"Bearer {tok}"}


@pytest.mark.asyncio
async def test_create_project(client):
    h = await _auth(client)
    resp = await client.post("/api/v1/projects", json={"name": "Receipts"}, headers=h)
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["name"] == "Receipts"
    assert body["api_code"] is None


@pytest.mark.asyncio
async def test_list_projects_returns_only_my_workspace(client):
    h1 = await _auth(client, "a@a.com")
    h2 = await _auth(client, "b@b.com")
    await client.post("/api/v1/projects", json={"name": "P-A"}, headers=h1)
    await client.post("/api/v1/projects", json={"name": "P-B"}, headers=h2)

    r1 = await client.get("/api/v1/projects", headers=h1)
    r2 = await client.get("/api/v1/projects", headers=h2)
    assert [p["name"] for p in r1.json()] == ["P-A"]
    assert [p["name"] for p in r2.json()] == ["P-B"]


@pytest.mark.asyncio
async def test_get_project_404_for_other_workspace(client):
    h1 = await _auth(client, "a@a.com")
    h2 = await _auth(client, "b@b.com")
    pid = (await client.post("/api/v1/projects", json={"name": "P"}, headers=h1)).json()["id"]
    resp = await client.get(f"/api/v1/projects/{pid}", headers=h2)
    assert resp.status_code == 404
```

- [ ] **Step 2: Run — expect 404 / import error**

Run: `cd backend && uv run pytest tests/test_project_routes.py -v`

- [ ] **Step 3: Implement `app/schemas/project.py`**

```python
from datetime import datetime

from pydantic import BaseModel, Field


class ProjectIn(BaseModel):
    name: str = Field(min_length=1, max_length=255)


class ProjectOut(BaseModel):
    id: int
    workspace_id: int
    name: str
    created_at: datetime
    created_by: int
    template_id: int | None = None
    active_version_id: int | None = None
    api_code: str | None = None
    api_published_at: datetime | None = None

    model_config = {"from_attributes": True}
```

- [ ] **Step 4: Implement `app/api/routes/projects.py`**

```python
from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import current_user, current_workspace_id
from app.db import get_session
from app.errors import EmergeError, ErrorCode
from app.models.project import Project
from app.models.user import User
from app.schemas.project import ProjectIn, ProjectOut

router = APIRouter(prefix="/projects", tags=["projects"])


@router.post("", response_model=ProjectOut, status_code=status.HTTP_201_CREATED)
async def create_project(
    payload: ProjectIn,
    user: User = Depends(current_user),
    workspace_id: int = Depends(current_workspace_id),
    session: AsyncSession = Depends(get_session),
) -> ProjectOut:
    p = Project(workspace_id=workspace_id, name=payload.name, created_by=user.id)
    session.add(p)
    await session.commit()
    await session.refresh(p)
    return ProjectOut.model_validate(p)


@router.get("", response_model=list[ProjectOut])
async def list_projects(
    workspace_id: int = Depends(current_workspace_id),
    session: AsyncSession = Depends(get_session),
) -> list[ProjectOut]:
    rows = (
        await session.execute(
            select(Project).where(Project.workspace_id == workspace_id).order_by(Project.id.desc())
        )
    ).scalars().all()
    return [ProjectOut.model_validate(p) for p in rows]


@router.get("/{project_id}", response_model=ProjectOut)
async def get_project(
    project_id: int,
    workspace_id: int = Depends(current_workspace_id),
    session: AsyncSession = Depends(get_session),
) -> ProjectOut:
    p = (
        await session.execute(
            select(Project).where(
                Project.id == project_id, Project.workspace_id == workspace_id
            )
        )
    ).scalar_one_or_none()
    if p is None:
        raise EmergeError(ErrorCode.NOT_FOUND, status_code=404)
    return ProjectOut.model_validate(p)
```

- [ ] **Step 5: Mount in `app/api/v1.py`**

```python
from app.api.routes import auth, me, projects

api_v1.include_router(projects.router)
```

- [ ] **Step 6: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/test_project_routes.py -v`
Expected: `3 passed`.

- [ ] **Step 7: Commit**

```bash
git add backend/app/schemas/project.py backend/app/api/routes/projects.py backend/app/api/v1.py backend/tests/test_project_routes.py
git commit -m "feat(backend): add Project create/list/get endpoints with workspace scoping"
```

---

## Task 3: Document model + migration

**Files:**
- Create: `backend/app/models/document.py`
- Modify: `backend/app/models/__init__.py`
- Create: `backend/alembic/versions/0004_document.py`
- Create: `backend/tests/test_document_model.py`

`status` is a string with a CHECK constraint; values: `uploaded | extracting | extracted | errored | archived` (spec §3.1). `data` is JSONB-style — SQLite stores as JSON string but SQLAlchemy `JSON` type round-trips dicts.

- [ ] **Step 1: Write the failing test**

```python
import pytest

from app.models.document import Document, DocumentStatus
from app.models.project import Project
from app.models.user import User
from app.models.workspace import Workspace


async def _make_project(db_session) -> tuple[int, int]:
    user = User(email="d@d.com", password_hash="x")
    db_session.add(user)
    await db_session.flush()
    ws = Workspace(name="W", owner_id=user.id)
    db_session.add(ws)
    await db_session.flush()
    p = Project(workspace_id=ws.id, name="P", created_by=user.id)
    db_session.add(p)
    await db_session.flush()
    return p.id, user.id


@pytest.mark.asyncio
async def test_document_persists_with_default_status(db_session):
    pid, uid = await _make_project(db_session)
    d = Document(
        project_id=pid,
        filename="r.pdf",
        file_path="/tmp/r.pdf",
        mime_type="application/pdf",
        page_count=2,
        byte_size=1024,
        uploaded_by=uid,
    )
    db_session.add(d)
    await db_session.commit()
    await db_session.refresh(d)
    assert d.status == DocumentStatus.UPLOADED.value
    assert d.data == {}


@pytest.mark.asyncio
async def test_document_invalid_status_rejected(db_session):
    pid, uid = await _make_project(db_session)
    d = Document(
        project_id=pid,
        filename="x.pdf",
        file_path="/tmp/x.pdf",
        mime_type="application/pdf",
        page_count=1,
        byte_size=10,
        uploaded_by=uid,
        status="bogus",
    )
    db_session.add(d)
    with pytest.raises(Exception):
        await db_session.commit()
```

- [ ] **Step 2: Run — expect ImportError**

Run: `cd backend && uv run pytest tests/test_document_model.py -v`

- [ ] **Step 3: Implement `app/models/document.py`**

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


_VALID_STATUSES = ",".join(f"'{s.value}'" for s in DocumentStatus)


class Document(Base, TimestampMixin):
    __tablename__ = "documents"
    __table_args__ = (
        CheckConstraint(f"status IN ({_VALID_STATUSES})", name="ck_document_status"),
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
```

Re-export in `app/models/__init__.py`.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/test_document_model.py -v`
Expected: `2 passed`.

- [ ] **Step 5: Generate + apply migration**

```bash
cd backend && uv run alembic revision --autogenerate -m "document table"
# rename to 0004_document.py
uv run alembic upgrade head
```

- [ ] **Step 6: Commit**

```bash
git add backend/app/models/document.py backend/app/models/__init__.py backend/alembic/versions/0004_document.py backend/tests/test_document_model.py
git commit -m "feat(backend): add Document model + 0004 migration"
```

---

## Task 4: Storage helper

**Files:**
- Create: `backend/app/services/__init__.py` (empty)
- Create: `backend/app/services/storage.py`
- Create: `backend/tests/test_storage.py`

Storage layout: `<storage_root>/projects/<project_id>/<uuid>-<sanitized_filename>`. UUID prefix prevents collisions across re-uploads of the same filename. Sanitization strips path separators.

- [ ] **Step 1: Write the failing test**

```python
import io

import pytest
from fastapi import UploadFile

from app.services.storage import save_upload


@pytest.mark.asyncio
async def test_save_upload_writes_file(tmp_path, monkeypatch):
    monkeypatch.setattr("app.services.storage.settings.storage_root", str(tmp_path))
    f = UploadFile(filename="my.pdf", file=io.BytesIO(b"PDFDATA"))
    rec = await save_upload(f, project_id=42)
    assert rec.byte_size == 7
    assert rec.mime_type == "application/pdf"
    with open(rec.file_path, "rb") as fh:
        assert fh.read() == b"PDFDATA"
    assert "/projects/42/" in rec.file_path


@pytest.mark.asyncio
async def test_save_upload_strips_path_traversal(tmp_path, monkeypatch):
    monkeypatch.setattr("app.services.storage.settings.storage_root", str(tmp_path))
    f = UploadFile(filename="../../etc/passwd", file=io.BytesIO(b"x"))
    rec = await save_upload(f, project_id=1)
    assert ".." not in rec.file_path
    assert "passwd" in rec.filename
```

- [ ] **Step 2: Run — expect ImportError**

- [ ] **Step 3: Implement `app/services/storage.py`**

```python
import asyncio
import os
import uuid
from dataclasses import dataclass
from pathlib import Path

from fastapi import UploadFile

from app.settings import settings


@dataclass
class StoredFile:
    file_path: str
    filename: str
    mime_type: str
    byte_size: int


def _sanitize(name: str) -> str:
    name = os.path.basename(name)  # strip path separators
    return name.replace("\0", "")[:255] or "unnamed"


async def save_upload(file: UploadFile, *, project_id: int) -> StoredFile:
    safe = _sanitize(file.filename or "unnamed")
    target_dir = Path(settings.storage_root) / "projects" / str(project_id)
    target_dir.mkdir(parents=True, exist_ok=True)
    stored_name = f"{uuid.uuid4().hex}-{safe}"
    target_path = target_dir / stored_name

    def _write_sync(data: bytes) -> int:
        with open(target_path, "wb") as fh:
            return fh.write(data)

    raw = await file.read()
    size = await asyncio.to_thread(_write_sync, raw)
    return StoredFile(
        file_path=str(target_path),
        filename=safe,
        mime_type=file.content_type or "application/octet-stream",
        byte_size=size,
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/test_storage.py -v`
Expected: `2 passed`.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/__init__.py backend/app/services/storage.py backend/tests/test_storage.py
git commit -m "feat(backend): add disk storage helper for uploaded documents"
```

---

## Task 5: Document upload + list endpoints

**Files:**
- Create: `backend/app/schemas/document.py`
- Create: `backend/app/api/routes/documents.py`
- Modify: `backend/app/api/v1.py` (mount documents router)
- Create: `backend/tests/test_document_routes.py`

**Note on page_count**: Counting PDF pages requires a PDF lib. To avoid a heavy dep here, R2 stores `page_count = 0` and lets R3 backfill it as part of the extraction pipeline (or use PyPDF2 if added in R3). This keeps R2 dep-light.

- [ ] **Step 1: Write the failing tests**

```python
import io

import pytest


async def _auth_and_project(client) -> tuple[dict, int]:
    await client.post("/api/v1/auth/register", json={"email": "d@d.com", "password": "hunter22"})
    tok = (
        await client.post("/api/v1/auth/login", json={"email": "d@d.com", "password": "hunter22"})
    ).json()["access_token"]
    h = {"Authorization": f"Bearer {tok}"}
    pid = (await client.post("/api/v1/projects", json={"name": "P"}, headers=h)).json()["id"]
    return h, pid


@pytest.mark.asyncio
async def test_upload_two_files(client, tmp_path, monkeypatch):
    monkeypatch.setattr("app.services.storage.settings.storage_root", str(tmp_path))
    h, pid = await _auth_and_project(client)
    files = [
        ("files", ("a.pdf", io.BytesIO(b"AAA"), "application/pdf")),
        ("files", ("b.pdf", io.BytesIO(b"BB"), "application/pdf")),
    ]
    resp = await client.post(f"/api/v1/projects/{pid}/documents", files=files, headers=h)
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert len(body) == 2
    assert {d["filename"] for d in body} == {"a.pdf", "b.pdf"}
    assert all(d["status"] == "uploaded" for d in body)


@pytest.mark.asyncio
async def test_list_documents_for_project(client, tmp_path, monkeypatch):
    monkeypatch.setattr("app.services.storage.settings.storage_root", str(tmp_path))
    h, pid = await _auth_and_project(client)
    await client.post(
        f"/api/v1/projects/{pid}/documents",
        files=[("files", ("a.pdf", io.BytesIO(b"AAA"), "application/pdf"))],
        headers=h,
    )
    resp = await client.get(f"/api/v1/projects/{pid}/documents", headers=h)
    assert resp.status_code == 200
    assert len(resp.json()) == 1


@pytest.mark.asyncio
async def test_upload_into_other_workspace_404(client, tmp_path, monkeypatch):
    monkeypatch.setattr("app.services.storage.settings.storage_root", str(tmp_path))
    h1, pid = await _auth_and_project(client)
    # second user
    await client.post("/api/v1/auth/register", json={"email": "z@z.com", "password": "hunter22"})
    tok = (
        await client.post("/api/v1/auth/login", json={"email": "z@z.com", "password": "hunter22"})
    ).json()["access_token"]
    h2 = {"Authorization": f"Bearer {tok}"}
    resp = await client.post(
        f"/api/v1/projects/{pid}/documents",
        files=[("files", ("a.pdf", io.BytesIO(b"AAA"), "application/pdf"))],
        headers=h2,
    )
    assert resp.status_code == 404
```

- [ ] **Step 2: Run — expect 404**

- [ ] **Step 3: Implement `app/schemas/document.py`**

```python
from datetime import datetime

from pydantic import BaseModel


class DocumentOut(BaseModel):
    id: int
    project_id: int
    filename: str
    mime_type: str
    page_count: int
    byte_size: int
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}
```

- [ ] **Step 4: Implement `app/api/routes/documents.py`**

```python
from fastapi import APIRouter, Depends, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import current_user, current_workspace_id
from app.db import get_session
from app.errors import EmergeError, ErrorCode
from app.models.document import Document
from app.models.project import Project
from app.models.user import User
from app.schemas.document import DocumentOut
from app.services.storage import save_upload

router = APIRouter(prefix="/projects/{project_id}/documents", tags=["documents"])


async def _project_or_404(session: AsyncSession, project_id: int, workspace_id: int) -> Project:
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


@router.post("", response_model=list[DocumentOut], status_code=status.HTTP_201_CREATED)
async def upload_documents(
    project_id: int,
    files: list[UploadFile],
    user: User = Depends(current_user),
    workspace_id: int = Depends(current_workspace_id),
    session: AsyncSession = Depends(get_session),
) -> list[DocumentOut]:
    project = await _project_or_404(session, project_id, workspace_id)
    saved: list[Document] = []
    for f in files:
        rec = await save_upload(f, project_id=project.id)
        d = Document(
            project_id=project.id,
            filename=rec.filename,
            file_path=rec.file_path,
            mime_type=rec.mime_type,
            page_count=0,  # backfilled by R3 extraction pipeline
            byte_size=rec.byte_size,
            uploaded_by=user.id,
        )
        session.add(d)
        saved.append(d)
    await session.commit()
    for d in saved:
        await session.refresh(d)
    return [DocumentOut.model_validate(d) for d in saved]


@router.get("", response_model=list[DocumentOut])
async def list_documents(
    project_id: int,
    workspace_id: int = Depends(current_workspace_id),
    session: AsyncSession = Depends(get_session),
) -> list[DocumentOut]:
    await _project_or_404(session, project_id, workspace_id)
    rows = (
        await session.execute(
            select(Document).where(Document.project_id == project_id).order_by(Document.id.desc())
        )
    ).scalars().all()
    return [DocumentOut.model_validate(d) for d in rows]
```

- [ ] **Step 5: Mount router**

In `app/api/v1.py`:

```python
from app.api.routes import auth, documents, me, projects

api_v1.include_router(documents.router)
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `cd backend && uv run pytest tests/test_document_routes.py -v`
Expected: `3 passed`.

- [ ] **Step 7: Commit**

```bash
git add backend/app/schemas/document.py backend/app/api/routes/documents.py backend/app/api/v1.py backend/tests/test_document_routes.py
git commit -m "feat(backend): add multi-file upload + document list endpoints"
```

---

## Task 6: Prediction model + migration (table only)

**Files:**
- Create: `backend/app/models/prediction.py`
- Modify: `backend/app/models/__init__.py`
- Create: `backend/alembic/versions/0005_prediction.py`
- Create: `backend/tests/test_prediction_model.py`

`project_version_id` is nullable in this migration; R3 will introduce ProjectVersion and create the FK relationship by adding a non-null constraint after backfill (or the table stays empty until R3, in which case we just rely on app-level non-null). To keep R2 self-contained, store as nullable now and tighten in R3.

- [ ] **Step 1: Write the failing test**

```python
import pytest

from app.models.document import Document
from app.models.prediction import Prediction, PredictionStatus
from app.models.project import Project
from app.models.user import User
from app.models.workspace import Workspace


@pytest.mark.asyncio
async def test_prediction_persists_with_json_output(db_session):
    user = User(email="pr@pr.com", password_hash="x")
    db_session.add(user)
    await db_session.flush()
    ws = Workspace(name="W", owner_id=user.id)
    db_session.add(ws)
    await db_session.flush()
    p = Project(workspace_id=ws.id, name="P", created_by=user.id)
    db_session.add(p)
    await db_session.flush()
    d = Document(
        project_id=p.id,
        filename="x.pdf",
        file_path="/tmp/x",
        mime_type="application/pdf",
        page_count=1,
        byte_size=10,
        uploaded_by=user.id,
    )
    db_session.add(d)
    await db_session.flush()

    pred = Prediction(
        document_id=d.id,
        model_id="claude-opus-4-7",
        prompt_hash="abc",
        output=[{"shop_name": "X"}],
        per_field_confidence={},
        tokens_used=100,
        latency_ms=200,
        cost_estimate=0.0,
        status=PredictionStatus.SUCCESS.value,
    )
    db_session.add(pred)
    await db_session.commit()
    await db_session.refresh(pred)
    assert pred.id is not None
    assert pred.output == [{"shop_name": "X"}]
```

- [ ] **Step 2: Run — expect ImportError**

- [ ] **Step 3: Implement `app/models/prediction.py`**

```python
from enum import Enum

from sqlalchemy import JSON, CheckConstraint, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class PredictionStatus(str, Enum):
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"


class Prediction(Base, TimestampMixin):
    __tablename__ = "predictions"
    __table_args__ = (
        CheckConstraint(
            "status IN ('success','partial','failed')", name="ck_prediction_status"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    document_id: Mapped[int] = mapped_column(
        ForeignKey("documents.id"), nullable=False, index=True
    )
    project_version_id: Mapped[int | None] = mapped_column(nullable=True)  # FK in R3
    model_id: Mapped[str] = mapped_column(String(128), nullable=False)
    prompt_hash: Mapped[str] = mapped_column(String(64), nullable=False)

    output: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    per_field_confidence: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)

    tokens_used: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cost_estimate: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    status: Mapped[str] = mapped_column(String(16), nullable=False)
    error_message: Mapped[str | None] = mapped_column(String(2000), nullable=True)
```

Re-export.

- [ ] **Step 4: Run test to verify it passes**

- [ ] **Step 5: Generate + apply migration**

```bash
cd backend && uv run alembic revision --autogenerate -m "prediction table"
uv run alembic upgrade head
```

- [ ] **Step 6: Commit**

```bash
git add backend/app/models/prediction.py backend/app/models/__init__.py backend/alembic/versions/0005_prediction.py backend/tests/test_prediction_model.py
git commit -m "feat(backend): add Prediction model + 0005 migration"
```

---

## Task 7: Annotation model + migration (table only)

**Files:**
- Create: `backend/app/models/annotation.py`
- Modify: `backend/app/models/__init__.py`
- Create: `backend/alembic/versions/0006_annotation.py`
- Create: `backend/tests/test_annotation_model.py`

`role` is `counterexample | none` (spec §3.2 invariant) — DB CHECK constraint enforces this. `status` is `draft | saved | cancelled` for soft-delete semantics.

- [ ] **Step 1: Write the failing test**

```python
import pytest

from app.models.annotation import Annotation, AnnotationRole, AnnotationStatus
from app.models.document import Document
from app.models.project import Project
from app.models.user import User
from app.models.workspace import Workspace


@pytest.mark.asyncio
async def test_annotation_persists_with_role_none(db_session):
    user = User(email="a@a.com", password_hash="x")
    db_session.add(user)
    await db_session.flush()
    ws = Workspace(name="W", owner_id=user.id)
    db_session.add(ws)
    await db_session.flush()
    p = Project(workspace_id=ws.id, name="P", created_by=user.id)
    db_session.add(p)
    await db_session.flush()
    d = Document(
        project_id=p.id,
        filename="x.pdf",
        file_path="/tmp/x",
        mime_type="application/pdf",
        page_count=1,
        byte_size=10,
        uploaded_by=user.id,
    )
    db_session.add(d)
    await db_session.flush()

    ann = Annotation(
        document_id=d.id,
        output=[{"shop": "ABC"}],
        role=AnnotationRole.NONE.value,
        status=AnnotationStatus.SAVED.value,
        created_by=user.id,
        last_modified_by=user.id,
    )
    db_session.add(ann)
    await db_session.commit()
    await db_session.refresh(ann)
    assert ann.id is not None


@pytest.mark.asyncio
async def test_annotation_invalid_role_rejected(db_session):
    user = User(email="b@b.com", password_hash="x")
    db_session.add(user)
    await db_session.flush()
    ws = Workspace(name="W", owner_id=user.id)
    db_session.add(ws)
    await db_session.flush()
    p = Project(workspace_id=ws.id, name="P", created_by=user.id)
    db_session.add(p)
    await db_session.flush()
    d = Document(
        project_id=p.id,
        filename="x.pdf",
        file_path="/tmp/x",
        mime_type="application/pdf",
        page_count=1,
        byte_size=10,
        uploaded_by=user.id,
    )
    db_session.add(d)
    await db_session.flush()

    ann = Annotation(
        document_id=d.id,
        output=[],
        role="growth",  # not allowed
        status="saved",
        created_by=user.id,
        last_modified_by=user.id,
    )
    db_session.add(ann)
    with pytest.raises(Exception):
        await db_session.commit()
```

- [ ] **Step 2: Run — expect ImportError**

- [ ] **Step 3: Implement `app/models/annotation.py`**

```python
from datetime import datetime
from enum import Enum

from sqlalchemy import JSON, CheckConstraint, DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class AnnotationRole(str, Enum):
    COUNTEREXAMPLE = "counterexample"
    NONE = "none"


class AnnotationStatus(str, Enum):
    DRAFT = "draft"
    SAVED = "saved"
    CANCELLED = "cancelled"


class Annotation(Base, TimestampMixin):
    __tablename__ = "annotations"
    __table_args__ = (
        CheckConstraint(
            "role IN ('counterexample','none')", name="ck_annotation_role"
        ),
        CheckConstraint(
            "status IN ('draft','saved','cancelled')", name="ck_annotation_status"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    document_id: Mapped[int] = mapped_column(
        ForeignKey("documents.id"), nullable=False, index=True
    )
    parent_prediction_id: Mapped[int | None] = mapped_column(
        ForeignKey("predictions.id"), nullable=True
    )

    output: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    role: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default=AnnotationStatus.SAVED.value)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    last_modified_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    last_modified_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
```

Re-export.

- [ ] **Step 4: Run test to verify it passes**

- [ ] **Step 5: Generate + apply migration**

```bash
cd backend && uv run alembic revision --autogenerate -m "annotation table"
uv run alembic upgrade head
```

- [ ] **Step 6: Commit**

```bash
git add backend/app/models/annotation.py backend/app/models/__init__.py backend/alembic/versions/0006_annotation.py backend/tests/test_annotation_model.py
git commit -m "feat(backend): add Annotation model + 0006 migration with role/status checks"
```

---

## Task 8: Get-document detail endpoint

**Files:**
- Modify: `backend/app/api/routes/documents.py` (add `GET /{document_id}`)
- Modify: `backend/app/schemas/document.py` (add `DocumentDetailOut` with latest prediction + annotation summary stubs — fields populated in R3/R4)
- Modify: `backend/tests/test_document_routes.py` (append detail test)

Detail endpoint exists in R2 with placeholders for `latest_prediction` and `latest_annotation` fields. R3 fills in `latest_prediction`, R4 fills in `latest_annotation`. This avoids re-shaping the API response in subsequent slices.

- [ ] **Step 1: Append failing test**

```python
@pytest.mark.asyncio
async def test_get_document_detail(client, tmp_path, monkeypatch):
    monkeypatch.setattr("app.services.storage.settings.storage_root", str(tmp_path))
    h, pid = await _auth_and_project(client)
    did = (
        await client.post(
            f"/api/v1/projects/{pid}/documents",
            files=[("files", ("a.pdf", io.BytesIO(b"AAA"), "application/pdf"))],
            headers=h,
        )
    ).json()[0]["id"]
    resp = await client.get(f"/api/v1/projects/{pid}/documents/{did}", headers=h)
    assert resp.status_code == 200
    body = resp.json()
    assert body["filename"] == "a.pdf"
    assert body["latest_prediction"] is None
    assert body["latest_annotation"] is None
```

- [ ] **Step 2: Run — expect 404**

- [ ] **Step 3: Add `DocumentDetailOut` to `app/schemas/document.py`**

```python
class DocumentDetailOut(DocumentOut):
    latest_prediction: dict | None = None
    latest_annotation: dict | None = None
```

- [ ] **Step 4: Add detail endpoint to `app/api/routes/documents.py`**

```python
from app.schemas.document import DocumentDetailOut


@router.get("/{document_id}", response_model=DocumentDetailOut)
async def get_document(
    project_id: int,
    document_id: int,
    workspace_id: int = Depends(current_workspace_id),
    session: AsyncSession = Depends(get_session),
) -> DocumentDetailOut:
    await _project_or_404(session, project_id, workspace_id)
    d = (
        await session.execute(
            select(Document).where(
                Document.id == document_id, Document.project_id == project_id
            )
        )
    ).scalar_one_or_none()
    if d is None:
        raise EmergeError(ErrorCode.NOT_FOUND, status_code=404)
    payload = DocumentOut.model_validate(d).model_dump()
    payload["latest_prediction"] = None  # populated in R3
    payload["latest_annotation"] = None  # populated in R4
    return DocumentDetailOut(**payload)
```

- [ ] **Step 5: Run test to verify it passes**

- [ ] **Step 6: Run full backend suite**

Run: `cd backend && uv run pytest -v`
Expected: every R1 + R2 test passes.

- [ ] **Step 7: Commit**

```bash
git add backend/app/api/routes/documents.py backend/app/schemas/document.py backend/tests/test_document_routes.py
git commit -m "feat(backend): add document detail endpoint with R3/R4 placeholders"
```

---

## R2 exit criteria

End-to-end: register → create project → upload 3 PDFs → list documents (returns 3 rows, all `status=uploaded`) → fetch one document detail (returns shape with `latest_prediction=null`, `latest_annotation=null`). Tables `projects`, `documents`, `predictions`, `annotations` exist in the DB. No extraction or correction logic yet — that lands in R3 and R4.

R3 hooks into the `Document` lifecycle (sets `status=extracting/extracted`, writes `Prediction` rows) and adds `ProjectVersion`. R4 fills the `Annotation` write path. R7 fills `template_id` (Template table) and `api_code` (publish flow).
