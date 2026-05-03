# R1 — Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stand up the backend skeleton (FastAPI + async SQLAlchemy + alembic), the User / Workspace / Membership data model, and a working JWT auth stack — the minimum substrate every later slice depends on.

**Architecture:** Single-process FastAPI app, async SQLAlchemy 2.x ORM over aiosqlite (SQLite is the v1 default per spec §13.1; PostgreSQL deferred), alembic for migrations, pydantic-settings for env config. Auth is JWT (HS256, 7-day expiry). Errors are returned as a uniform `{ error_code, error_message_en }` envelope (spec §11.1) so the frontend can translate by code. The repo is monorepo-style: `backend/` and `frontend/` siblings; this plan only sets up `backend/`.

**Tech Stack:** Python 3.11+, FastAPI, SQLAlchemy 2.x async, aiosqlite, alembic, pydantic v2, pydantic-settings, bcrypt, python-jose, pytest + pytest-asyncio, httpx (test client), ruff. Versions pinned to match doc-intel-legacy's `pyproject.toml` (already validated stack).

**Spec sections covered:** §3.1 (User / Workspace / WorkspaceMembership), §11.1 (i18n error envelope), §13.1 (FastAPI + async SQLAlchemy + SQLite default), §13.6 (JWT auth default).

**Depends on:** nothing. This is the bottom of the dependency tree.

---

## File Structure

All paths relative to `emerge/backend/` unless noted. The initial scaffold creates:

```
backend/
├── pyproject.toml                  # deps + tool config (ruff, pytest)
├── .gitignore                      # python + sqlite + venv
├── alembic.ini                     # alembic config
├── alembic/
│   ├── env.py                      # async-aware alembic env
│   ├── script.py.mako
│   └── versions/                   # migration files (one per task that adds a table)
├── app/
│   ├── __init__.py
│   ├── main.py                     # FastAPI app factory + router registration
│   ├── settings.py                 # pydantic-settings env loader
│   ├── db.py                       # async engine + session factory + get_session dep
│   ├── errors.py                   # ErrorCode enum + EmergeError + handler
│   ├── models/
│   │   ├── __init__.py             # re-exports + Base
│   │   ├── base.py                 # declarative Base + common mixins
│   │   ├── user.py                 # User table
│   │   └── workspace.py            # Workspace + WorkspaceMembership
│   ├── core/
│   │   ├── __init__.py
│   │   ├── security.py             # password hash + JWT encode/decode
│   │   └── deps.py                 # FastAPI dependencies (current_user, etc.)
│   ├── schemas/
│   │   ├── __init__.py
│   │   ├── auth.py                 # RegisterIn, LoginIn, TokenOut
│   │   └── user.py                 # UserOut
│   └── api/
│       ├── __init__.py
│       ├── v1.py                   # APIRouter prefix=/api/v1
│       └── routes/
│           ├── __init__.py
│           ├── auth.py             # /auth/register, /auth/login
│           └── me.py               # /me
└── tests/
    ├── __init__.py
    ├── conftest.py                 # pytest fixtures: in-memory engine, async client
    ├── test_health.py              # smoke
    ├── test_errors.py              # error envelope contract
    ├── test_security.py            # password + JWT unit tests
    ├── test_auth.py                # register / login flow
    └── test_me.py                  # auth dependency e2e
```

Each file has one responsibility. Models are split per aggregate (user / workspace) so future slices add tables next to their domain. Routes are per-resource files; `v1.py` only assembles. Tests mirror the source layout.

---

## Task 1: Bootstrap repo skeleton

**Files:**
- Create: `backend/pyproject.toml`
- Create: `backend/.gitignore`
- Create: `backend/app/__init__.py` (empty)
- Create: `backend/tests/__init__.py` (empty)

- [ ] **Step 1: Write the failing smoke test**

Create `backend/tests/test_health.py`:

```python
def test_smoke():
    """Confirms pytest discovers tests under backend/."""
    assert 1 + 1 == 2
```

- [ ] **Step 2: Run test to verify discovery (will fail because env not set up)**

Run: `cd backend && uv run pytest tests/test_health.py -v`
Expected: error — `pyproject.toml not found` or `uv: command not found`. This is the trigger to set up the environment.

- [ ] **Step 3: Write `backend/pyproject.toml`**

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "emerge-backend"
version = "0.1.0"
description = "emerge — Software 3.0 document extraction platform"
requires-python = ">=3.11"

dependencies = [
    "fastapi>=0.115.0",
    "uvicorn[standard]>=0.30.0",
    "python-multipart>=0.0.12",
    "sqlalchemy[asyncio]>=2.0.30",
    "aiosqlite>=0.20.0",
    "alembic>=1.13.0",
    "pydantic[email]>=2.7.0",
    "pydantic-settings>=2.3.0",
    "bcrypt>=4.0.0",
    "python-jose[cryptography]>=3.3.0",
    "httpx>=0.27.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0.0",
    "pytest-asyncio>=0.23.0",
    "ruff>=0.6.0",
]

[tool.hatch.build.targets.wheel]
packages = ["app"]

[tool.ruff]
line-length = 100
target-version = "py311"
[tool.ruff.lint]
select = ["E", "F", "I", "UP"]
ignore = ["E501"]

[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "auto"
```

- [ ] **Step 4: Write `backend/.gitignore`**

```
__pycache__/
*.py[cod]
*.egg-info/
.venv/
.pytest_cache/
.ruff_cache/
*.db
*.db-journal
*.db-wal
*.db-shm
.env
.env.local
data/
```

- [ ] **Step 5: Install env and run smoke test**

Run:
```bash
cd backend && uv sync --extra dev
uv run pytest tests/test_health.py -v
```
Expected: `1 passed`.

- [ ] **Step 6: Commit**

```bash
git add backend/pyproject.toml backend/.gitignore backend/app/__init__.py backend/tests/__init__.py backend/tests/test_health.py
git commit -m "chore(backend): bootstrap pyproject and pytest skeleton"
```

---

## Task 2: Settings + DB engine

**Files:**
- Create: `backend/app/settings.py`
- Create: `backend/app/db.py`
- Create: `backend/app/models/__init__.py`
- Create: `backend/app/models/base.py`
- Create: `backend/tests/conftest.py`
- Create: `backend/tests/test_db.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_db.py`:

```python
import pytest
from sqlalchemy import text


@pytest.mark.asyncio
async def test_engine_returns_session(db_session):
    result = await db_session.execute(text("SELECT 1"))
    assert result.scalar() == 1
```

And `backend/tests/conftest.py`:

```python
import asyncio
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.models.base import Base


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture
async def db_engine():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(db_engine) -> AsyncIterator[AsyncSession]:
    factory = async_sessionmaker(db_engine, expire_on_commit=False)
    async with factory() as session:
        yield session
```

- [ ] **Step 2: Run — expect collection error (`app.models.base` missing)**

Run: `cd backend && uv run pytest tests/test_db.py -v`
Expected: `ModuleNotFoundError: app.models.base`.

- [ ] **Step 3: Write `app/settings.py`**

```python
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = Field(default="sqlite+aiosqlite:///./data/emerge.db")
    jwt_secret: str = Field(default="change-me-in-prod")
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60 * 24 * 7  # 7 days

    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:5173"])

    storage_root: str = "./data/uploads"


settings = Settings()
```

- [ ] **Step 4: Write `app/models/base.py`**

```python
from datetime import datetime

from sqlalchemy import DateTime, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
```

- [ ] **Step 5: Write `app/models/__init__.py`**

```python
from app.models.base import Base, TimestampMixin

__all__ = ["Base", "TimestampMixin"]
```

- [ ] **Step 6: Write `app/db.py`**

```python
from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.settings import settings

engine = create_async_engine(settings.database_url, future=True)
SessionFactory = async_sessionmaker(engine, expire_on_commit=False)


async def get_session() -> AsyncIterator[AsyncSession]:
    async with SessionFactory() as session:
        yield session
```

- [ ] **Step 7: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/test_db.py -v`
Expected: `1 passed`.

- [ ] **Step 8: Commit**

```bash
git add backend/app/settings.py backend/app/db.py backend/app/models/ backend/tests/conftest.py backend/tests/test_db.py
git commit -m "feat(backend): add settings, async engine, and db_session fixture"
```

---

## Task 3: Error envelope

**Files:**
- Create: `backend/app/errors.py`
- Create: `backend/tests/test_errors.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_errors.py`:

```python
import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.errors import EmergeError, ErrorCode, register_error_handler


@pytest.mark.asyncio
async def test_emerge_error_returns_envelope():
    app = FastAPI()
    register_error_handler(app)

    @app.get("/boom")
    async def boom():
        raise EmergeError(ErrorCode.UNAUTHORIZED, status_code=401)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://t") as client:
        resp = await client.get("/boom")
    assert resp.status_code == 401
    body = resp.json()
    assert body == {
        "error_code": "UNAUTHORIZED",
        "error_message_en": "Authentication required.",
    }


@pytest.mark.asyncio
async def test_unhandled_exception_returns_internal_envelope():
    app = FastAPI()
    register_error_handler(app)

    @app.get("/crash")
    async def crash():
        raise ValueError("boom")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://t") as client:
        resp = await client.get("/crash")
    assert resp.status_code == 500
    assert resp.json()["error_code"] == "INTERNAL_ERROR"
```

- [ ] **Step 2: Run — expect ImportError**

Run: `cd backend && uv run pytest tests/test_errors.py -v`
Expected: `ImportError: cannot import name 'EmergeError' from 'app.errors'`.

- [ ] **Step 3: Implement `app/errors.py`**

```python
from enum import Enum

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


class ErrorCode(str, Enum):
    UNAUTHORIZED = "UNAUTHORIZED"
    FORBIDDEN = "FORBIDDEN"
    NOT_FOUND = "NOT_FOUND"
    VALIDATION_FAILED = "VALIDATION_FAILED"
    CONFLICT = "CONFLICT"
    INTERNAL_ERROR = "INTERNAL_ERROR"


_MESSAGES: dict[ErrorCode, str] = {
    ErrorCode.UNAUTHORIZED: "Authentication required.",
    ErrorCode.FORBIDDEN: "You do not have permission to perform this action.",
    ErrorCode.NOT_FOUND: "Resource not found.",
    ErrorCode.VALIDATION_FAILED: "Request validation failed.",
    ErrorCode.CONFLICT: "Resource state conflict.",
    ErrorCode.INTERNAL_ERROR: "An internal error occurred.",
}


class EmergeError(Exception):
    def __init__(
        self,
        code: ErrorCode,
        *,
        status_code: int = 400,
        message_override: str | None = None,
    ):
        self.code = code
        self.status_code = status_code
        self.message = message_override or _MESSAGES[code]
        super().__init__(self.message)


def register_error_handler(app: FastAPI) -> None:
    @app.exception_handler(EmergeError)
    async def _handle_emerge(_: Request, exc: EmergeError):
        return JSONResponse(
            status_code=exc.status_code,
            content={"error_code": exc.code.value, "error_message_en": exc.message},
        )

    @app.exception_handler(Exception)
    async def _handle_unhandled(_: Request, exc: Exception):
        return JSONResponse(
            status_code=500,
            content={
                "error_code": ErrorCode.INTERNAL_ERROR.value,
                "error_message_en": _MESSAGES[ErrorCode.INTERNAL_ERROR],
            },
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/test_errors.py -v`
Expected: `2 passed`.

- [ ] **Step 5: Commit**

```bash
git add backend/app/errors.py backend/tests/test_errors.py
git commit -m "feat(backend): add EmergeError envelope with error_code/error_message_en"
```

---

## Task 4: User model + first migration

**Files:**
- Create: `backend/app/models/user.py`
- Create: `backend/alembic.ini`
- Create: `backend/alembic/env.py`
- Create: `backend/alembic/script.py.mako`
- Create: `backend/alembic/versions/0001_user.py` (generated, then committed)
- Create: `backend/tests/test_user_model.py`

- [ ] **Step 1: Write the failing model test**

Create `backend/tests/test_user_model.py`:

```python
import pytest

from app.models.user import User


@pytest.mark.asyncio
async def test_user_can_be_inserted_and_queried(db_session):
    user = User(email="alice@example.com", password_hash="x")
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    assert user.id is not None
    assert user.created_at is not None


@pytest.mark.asyncio
async def test_user_email_is_unique(db_session):
    db_session.add(User(email="a@a.com", password_hash="x"))
    await db_session.commit()
    db_session.add(User(email="a@a.com", password_hash="y"))
    with pytest.raises(Exception):
        await db_session.commit()
```

- [ ] **Step 2: Run — expect ImportError**

Run: `cd backend && uv run pytest tests/test_user_model.py -v`
Expected: `ModuleNotFoundError: app.models.user`.

- [ ] **Step 3: Implement `app/models/user.py`**

```python
from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
```

- [ ] **Step 4: Re-export in `app/models/__init__.py`**

```python
from app.models.base import Base, TimestampMixin
from app.models.user import User

__all__ = ["Base", "TimestampMixin", "User"]
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/test_user_model.py -v`
Expected: `2 passed`.

- [ ] **Step 6: Initialise alembic + first migration**

Create `backend/alembic.ini`:

```ini
[alembic]
script_location = alembic
prepend_sys_path = .
sqlalchemy.url = sqlite+aiosqlite:///./data/emerge.db

[loggers]
keys = root,sqlalchemy,alembic

[handlers]
keys = console

[formatters]
keys = generic

[logger_root]
level = WARN
handlers = console
qualname =

[logger_sqlalchemy]
level = WARN
handlers =
qualname = sqlalchemy.engine

[logger_alembic]
level = INFO
handlers =
qualname = alembic

[handler_console]
class = StreamHandler
args = (sys.stderr,)
level = NOTSET
formatter = generic

[formatter_generic]
format = %(levelname)-5.5s [%(name)s] %(message)s
datefmt = %H:%M:%S
```

Create `backend/alembic/env.py`:

```python
import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from app.models import Base  # noqa: F401 — needed for autogenerate
from app.settings import settings

config = context.config
config.set_main_option("sqlalchemy.url", settings.database_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
```

Create `backend/alembic/script.py.mako` (standard template — copy from any alembic-init project; one-liner if generating):

```mako
"""${message}

Revision ID: ${up_revision}
Revises: ${down_revision | comma,n}
Create Date: ${create_date}
"""
from alembic import op
import sqlalchemy as sa
${imports if imports else ""}

revision = ${repr(up_revision)}
down_revision = ${repr(down_revision)}
branch_labels = ${repr(branch_labels)}
depends_on = ${repr(depends_on)}


def upgrade() -> None:
    ${upgrades if upgrades else "pass"}


def downgrade() -> None:
    ${downgrades if downgrades else "pass"}
```

Generate the first migration:

```bash
cd backend && mkdir -p alembic/versions data
uv run alembic revision --autogenerate -m "user table"
```

Expected: file `alembic/versions/<hash>_user_table.py` is created with `op.create_table("users", ...)`. Rename to `0001_user.py` for ordering clarity (edit the `revision = "..."` to `"0001"`).

- [ ] **Step 7: Apply migration and verify**

```bash
cd backend && uv run alembic upgrade head
```
Expected: `INFO ... Running upgrade -> 0001, user table`.

Verify schema:

```bash
sqlite3 backend/data/emerge.db ".schema users"
```
Expected: `CREATE TABLE users (id INTEGER PRIMARY KEY, email VARCHAR(255) NOT NULL, password_hash VARCHAR(255) NOT NULL, created_at DATETIME NOT NULL DEFAULT (CURRENT_TIMESTAMP));` (or alembic equivalent).

- [ ] **Step 8: Commit**

```bash
git add backend/app/models/user.py backend/app/models/__init__.py backend/alembic.ini backend/alembic/ backend/tests/test_user_model.py
git commit -m "feat(backend): add User model and alembic 0001 migration"
```

---

## Task 5: Workspace + WorkspaceMembership models

**Files:**
- Create: `backend/app/models/workspace.py`
- Modify: `backend/app/models/__init__.py`
- Create: `backend/alembic/versions/0002_workspace.py` (autogenerated)
- Create: `backend/tests/test_workspace_model.py`

- [ ] **Step 1: Write the failing test**

```python
import pytest

from app.models.user import User
from app.models.workspace import Workspace, WorkspaceMembership, WorkspaceRole


@pytest.mark.asyncio
async def test_workspace_with_owner_membership(db_session):
    user = User(email="owner@example.com", password_hash="x")
    db_session.add(user)
    await db_session.flush()
    ws = Workspace(name="Team A", owner_id=user.id)
    db_session.add(ws)
    await db_session.flush()
    db_session.add(
        WorkspaceMembership(workspace_id=ws.id, user_id=user.id, role=WorkspaceRole.OWNER)
    )
    await db_session.commit()
    assert ws.id is not None
```


@pytest.mark.asyncio
async def test_membership_role_check(db_session):
    user = User(email="u@u.com", password_hash="x")
    db_session.add(user)
    await db_session.flush()
    ws = Workspace(name="W", owner_id=user.id)
    db_session.add(ws)
    await db_session.flush()
    db_session.add(WorkspaceMembership(workspace_id=ws.id, user_id=user.id, role="bogus"))
    with pytest.raises(Exception):
        await db_session.commit()
```

- [ ] **Step 2: Run — expect ImportError**

Run: `cd backend && uv run pytest tests/test_workspace_model.py -v`
Expected: `ModuleNotFoundError: app.models.workspace`.

- [ ] **Step 3: Implement `app/models/workspace.py`**

```python
from enum import Enum

from sqlalchemy import CheckConstraint, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class WorkspaceRole(str, Enum):
    OWNER = "owner"
    ADMIN = "admin"
    MEMBER = "member"


class Workspace(Base, TimestampMixin):
    __tablename__ = "workspaces"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)


class WorkspaceMembership(Base, TimestampMixin):
    __tablename__ = "workspace_memberships"
    __table_args__ = (
        CheckConstraint(
            "role IN ('owner','admin','member')",
            name="ck_workspace_membership_role",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    workspace_id: Mapped[int] = mapped_column(
        ForeignKey("workspaces.id"), nullable=False, index=True
    )
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(16), nullable=False)
```

Add to `app/models/__init__.py`:

```python
from app.models.workspace import Workspace, WorkspaceMembership, WorkspaceRole

__all__ = [..., "Workspace", "WorkspaceMembership", "WorkspaceRole"]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/test_workspace_model.py -v`
Expected: `2 passed`.

- [ ] **Step 5: Generate migration + apply**

```bash
cd backend && uv run alembic revision --autogenerate -m "workspace tables"
# rename to 0002_workspace.py and set revision="0002", down_revision="0001"
uv run alembic upgrade head
```

- [ ] **Step 6: Commit**

```bash
git add backend/app/models/workspace.py backend/app/models/__init__.py backend/alembic/versions/0002_workspace.py backend/tests/test_workspace_model.py
git commit -m "feat(backend): add Workspace/Membership models with role check"
```

---

## Task 6: Password hashing util

**Files:**
- Create: `backend/app/core/__init__.py` (empty)
- Create: `backend/app/core/security.py` (password half only this task)
- Create: `backend/tests/test_security.py`

- [ ] **Step 1: Write the failing test**

```python
from app.core.security import hash_password, verify_password


def test_hash_password_round_trip():
    h = hash_password("hunter2")
    assert h != "hunter2"
    assert verify_password("hunter2", h) is True
    assert verify_password("wrong", h) is False


def test_hash_password_is_random():
    assert hash_password("same") != hash_password("same")
```

- [ ] **Step 2: Run — expect ImportError**

Run: `cd backend && uv run pytest tests/test_security.py -v`
Expected: `ImportError: cannot import name 'hash_password' from 'app.core.security'`.

- [ ] **Step 3: Implement password half of `app/core/security.py`**

```python
import bcrypt


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/test_security.py -v`
Expected: `2 passed`.

- [ ] **Step 5: Commit**

```bash
git add backend/app/core/__init__.py backend/app/core/security.py backend/tests/test_security.py
git commit -m "feat(backend): add bcrypt password hash helpers"
```

---

## Task 7: JWT encode / decode

**Files:**
- Modify: `backend/app/core/security.py` (append JWT helpers)
- Modify: `backend/tests/test_security.py` (append JWT tests)

- [ ] **Step 1: Append failing JWT tests**

```python
from datetime import timedelta

import pytest

from app.core.security import create_access_token, decode_access_token
from app.errors import EmergeError


def test_jwt_round_trip():
    token = create_access_token(subject="42")
    payload = decode_access_token(token)
    assert payload["sub"] == "42"


def test_jwt_expired_raises():
    token = create_access_token(subject="1", expires_delta=timedelta(seconds=-1))
    with pytest.raises(EmergeError):
        decode_access_token(token)


def test_jwt_tampered_raises():
    token = create_access_token(subject="1") + "garbage"
    with pytest.raises(EmergeError):
        decode_access_token(token)
```

- [ ] **Step 2: Run — expect ImportError**

Run: `cd backend && uv run pytest tests/test_security.py -v`
Expected: import error on `create_access_token`.

- [ ] **Step 3: Append JWT helpers to `app/core/security.py`**

```python
from datetime import datetime, timedelta, timezone
from typing import Any

from jose import JWTError, jwt

from app.errors import EmergeError, ErrorCode
from app.settings import settings


def create_access_token(*, subject: str, expires_delta: timedelta | None = None) -> str:
    expire = datetime.now(tz=timezone.utc) + (
        expires_delta or timedelta(minutes=settings.jwt_expire_minutes)
    )
    payload: dict[str, Any] = {"sub": subject, "exp": expire}
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict[str, Any]:
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except JWTError as e:
        raise EmergeError(ErrorCode.UNAUTHORIZED, status_code=401) from e
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/test_security.py -v`
Expected: `5 passed`.

- [ ] **Step 5: Commit**

```bash
git add backend/app/core/security.py backend/tests/test_security.py
git commit -m "feat(backend): add JWT encode/decode helpers"
```

---

## Task 8: Auth schemas + register endpoint

**Files:**
- Create: `backend/app/schemas/__init__.py` (empty)
- Create: `backend/app/schemas/auth.py`
- Create: `backend/app/schemas/user.py`
- Create: `backend/app/api/__init__.py` (empty)
- Create: `backend/app/api/v1.py`
- Create: `backend/app/api/routes/__init__.py` (empty)
- Create: `backend/app/api/routes/auth.py`
- Create: `backend/app/main.py`
- Modify: `backend/tests/conftest.py` (add `client` fixture)
- Create: `backend/tests/test_auth.py`

- [ ] **Step 1: Add `client` fixture in `conftest.py`**

Append to `backend/tests/conftest.py`:

```python
from httpx import ASGITransport, AsyncClient

from app.db import get_session
from app.main import create_app


@pytest_asyncio.fixture
async def app(db_session):
    app = create_app()

    async def _override_session():
        yield db_session

    app.dependency_overrides[get_session] = _override_session
    return app


@pytest_asyncio.fixture
async def client(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://t") as c:
        yield c
```

- [ ] **Step 2: Write failing register test**

Create `backend/tests/test_auth.py`:

```python
import pytest


@pytest.mark.asyncio
async def test_register_creates_user_and_workspace(client, db_session):
    resp = await client.post(
        "/api/v1/auth/register",
        json={"email": "alice@example.com", "password": "hunter22"},
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["email"] == "alice@example.com"
    assert "id" in body

    # exactly one Workspace + Membership owner row created
    from sqlalchemy import select

    from app.models.user import User
    from app.models.workspace import Workspace, WorkspaceMembership

    user = (await db_session.execute(select(User))).scalar_one()
    ws = (await db_session.execute(select(Workspace))).scalar_one()
    mem = (await db_session.execute(select(WorkspaceMembership))).scalar_one()
    assert ws.owner_id == user.id
    assert mem.role == "owner"


@pytest.mark.asyncio
async def test_register_duplicate_email_returns_conflict(client):
    payload = {"email": "dup@example.com", "password": "hunter22"}
    r1 = await client.post("/api/v1/auth/register", json=payload)
    assert r1.status_code == 201
    r2 = await client.post("/api/v1/auth/register", json=payload)
    assert r2.status_code == 409
    assert r2.json()["error_code"] == "CONFLICT"
```

- [ ] **Step 3: Run — expect 404 / app boot fail**

Run: `cd backend && uv run pytest tests/test_auth.py -v`
Expected: ImportError on `app.main.create_app`.

- [ ] **Step 4: Implement `app/schemas/auth.py`**

```python
from pydantic import BaseModel, EmailStr, Field


class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
```

- [ ] **Step 5: Implement `app/schemas/user.py`**

```python
from pydantic import BaseModel, EmailStr


class UserOut(BaseModel):
    id: int
    email: EmailStr

    model_config = {"from_attributes": True}
```

- [ ] **Step 6: Implement `app/api/routes/auth.py` (register only)**

```python
from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.db import get_session
from app.errors import EmergeError, ErrorCode
from app.models.user import User
from app.models.workspace import Workspace, WorkspaceMembership, WorkspaceRole
from app.schemas.auth import RegisterIn
from app.schemas.user import UserOut

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def register(payload: RegisterIn, session: AsyncSession = Depends(get_session)) -> UserOut:
    existing = (
        await session.execute(select(User).where(User.email == payload.email))
    ).scalar_one_or_none()
    if existing:
        raise EmergeError(ErrorCode.CONFLICT, status_code=409)

    user = User(email=payload.email, password_hash=hash_password(payload.password))
    session.add(user)
    await session.flush()

    ws = Workspace(name=f"{payload.email}'s workspace", owner_id=user.id)
    session.add(ws)
    await session.flush()

    session.add(
        WorkspaceMembership(workspace_id=ws.id, user_id=user.id, role=WorkspaceRole.OWNER.value)
    )
    await session.commit()
    await session.refresh(user)
    return UserOut.model_validate(user)
```

- [ ] **Step 7: Implement `app/api/v1.py`**

```python
from fastapi import APIRouter

from app.api.routes import auth

api_v1 = APIRouter(prefix="/api/v1")
api_v1.include_router(auth.router)
```

- [ ] **Step 8: Implement `app/main.py`**

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1 import api_v1
from app.errors import register_error_handler
from app.settings import settings


def create_app() -> FastAPI:
    app = FastAPI(title="emerge", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    register_error_handler(app)
    app.include_router(api_v1)
    return app


app = create_app()
```

- [ ] **Step 9: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/test_auth.py -v`
Expected: `2 passed`.

- [ ] **Step 10: Commit**

```bash
git add backend/app/schemas/ backend/app/api/ backend/app/main.py backend/tests/conftest.py backend/tests/test_auth.py
git commit -m "feat(backend): add register endpoint + app factory"
```

---

## Task 9: Login endpoint

**Files:**
- Modify: `backend/app/api/routes/auth.py` (add `login`)
- Modify: `backend/tests/test_auth.py` (append login tests)

- [ ] **Step 1: Append failing login tests**

```python
@pytest.mark.asyncio
async def test_login_returns_token(client):
    await client.post(
        "/api/v1/auth/register", json={"email": "l@l.com", "password": "hunter22"}
    )
    resp = await client.post(
        "/api/v1/auth/login", json={"email": "l@l.com", "password": "hunter22"}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["token_type"] == "bearer"
    assert isinstance(body["access_token"], str) and len(body["access_token"]) > 20


@pytest.mark.asyncio
async def test_login_wrong_password_returns_unauthorized(client):
    await client.post(
        "/api/v1/auth/register", json={"email": "x@x.com", "password": "hunter22"}
    )
    resp = await client.post(
        "/api/v1/auth/login", json={"email": "x@x.com", "password": "WRONG"}
    )
    assert resp.status_code == 401
    assert resp.json()["error_code"] == "UNAUTHORIZED"
```

- [ ] **Step 2: Run — expect 404 on /login**

Run: `cd backend && uv run pytest tests/test_auth.py -v`
Expected: 404.

- [ ] **Step 3: Append `login` to `app/api/routes/auth.py`**

```python
from app.core.security import create_access_token, verify_password
from app.schemas.auth import LoginIn, TokenOut


@router.post("/login", response_model=TokenOut)
async def login(payload: LoginIn, session: AsyncSession = Depends(get_session)) -> TokenOut:
    user = (
        await session.execute(select(User).where(User.email == payload.email))
    ).scalar_one_or_none()
    if not user or not verify_password(payload.password, user.password_hash):
        raise EmergeError(ErrorCode.UNAUTHORIZED, status_code=401)
    return TokenOut(access_token=create_access_token(subject=str(user.id)))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/test_auth.py -v`
Expected: `4 passed`.

- [ ] **Step 5: Commit**

```bash
git add backend/app/api/routes/auth.py backend/tests/test_auth.py
git commit -m "feat(backend): add login endpoint returning JWT"
```

---

## Task 10: `current_user` + `current_workspace_id` dependencies

**Files:**
- Create: `backend/app/core/deps.py`
- Create: `backend/app/api/routes/me.py`
- Modify: `backend/app/api/v1.py` (mount `me` router)
- Create: `backend/tests/test_me.py`

The `current_workspace_id` dep resolves the user's **single membership** in v1; multi-workspace switching is deferred. This satisfies spec §8.0 (普通用户的 URL 不带 workspace_id; 后端隐式解析).

- [ ] **Step 1: Write failing tests**

```python
import pytest


@pytest.mark.asyncio
async def test_me_requires_auth(client):
    resp = await client.get("/api/v1/me")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_me_returns_user_and_workspace(client):
    await client.post(
        "/api/v1/auth/register", json={"email": "m@m.com", "password": "hunter22"}
    )
    tok = (
        await client.post(
            "/api/v1/auth/login", json={"email": "m@m.com", "password": "hunter22"}
        )
    ).json()["access_token"]
    resp = await client.get("/api/v1/me", headers={"Authorization": f"Bearer {tok}"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["email"] == "m@m.com"
    assert isinstance(body["workspace_id"], int)


@pytest.mark.asyncio
async def test_me_with_bad_token_returns_unauthorized(client):
    resp = await client.get("/api/v1/me", headers={"Authorization": "Bearer garbage"})
    assert resp.status_code == 401
```

- [ ] **Step 2: Run — expect 404**

Run: `cd backend && uv run pytest tests/test_me.py -v`

- [ ] **Step 3: Implement `app/core/deps.py`**

```python
from fastapi import Depends, Header
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decode_access_token
from app.db import get_session
from app.errors import EmergeError, ErrorCode
from app.models.user import User
from app.models.workspace import WorkspaceMembership


async def current_user(
    authorization: str | None = Header(default=None),
    session: AsyncSession = Depends(get_session),
) -> User:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise EmergeError(ErrorCode.UNAUTHORIZED, status_code=401)
    token = authorization.split(" ", 1)[1].strip()
    payload = decode_access_token(token)
    user_id = int(payload["sub"])
    user = (
        await session.execute(select(User).where(User.id == user_id))
    ).scalar_one_or_none()
    if user is None:
        raise EmergeError(ErrorCode.UNAUTHORIZED, status_code=401)
    return user


async def current_workspace_id(
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> int:
    """Resolve the user's single workspace. v1 assumes one membership per user."""
    rows = (
        await session.execute(
            select(WorkspaceMembership.workspace_id).where(WorkspaceMembership.user_id == user.id)
        )
    ).scalars().all()
    if not rows:
        raise EmergeError(ErrorCode.FORBIDDEN, status_code=403)
    return rows[0]
```

- [ ] **Step 4: Implement `app/api/routes/me.py`**

```python
from fastapi import APIRouter, Depends
from pydantic import BaseModel, EmailStr

from app.core.deps import current_user, current_workspace_id
from app.models.user import User

router = APIRouter(tags=["me"])


class MeOut(BaseModel):
    id: int
    email: EmailStr
    workspace_id: int


@router.get("/me", response_model=MeOut)
async def me(
    user: User = Depends(current_user),
    workspace_id: int = Depends(current_workspace_id),
) -> MeOut:
    return MeOut(id=user.id, email=user.email, workspace_id=workspace_id)
```

- [ ] **Step 5: Mount router in `app/api/v1.py`**

```python
from app.api.routes import auth, me

api_v1.include_router(me.router)
```

- [ ] **Step 6: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/test_me.py -v`
Expected: `3 passed`.

- [ ] **Step 7: Run full suite**

Run: `cd backend && uv run pytest -v`
Expected: every test from tasks 1–10 passes (no regressions).

- [ ] **Step 8: Commit**

```bash
git add backend/app/core/deps.py backend/app/api/routes/me.py backend/app/api/v1.py backend/tests/test_me.py
git commit -m "feat(backend): add current_user/current_workspace_id deps + /me endpoint"
```

---

## Task 11: README + dev runbook

**Files:**
- Create: `backend/README.md`

Plan-only task: documents how a fresh contributor boots the backend. No tests; this is pure operational docs.

- [ ] **Step 1: Write `backend/README.md`**

```markdown
# emerge backend

## Setup

```
cd backend
uv sync --extra dev
mkdir -p data
uv run alembic upgrade head
uv run uvicorn app.main:app --reload --port 8000
```

## Test

```
uv run pytest -v
```

## Migrations

```
uv run alembic revision --autogenerate -m "<message>"
uv run alembic upgrade head
```

## Layout

- `app/api/routes/` — one file per resource (auth, me, projects, …)
- `app/models/` — SQLAlchemy models, one file per aggregate
- `app/schemas/` — pydantic request/response models
- `app/core/` — security (hash + JWT), FastAPI deps
- `tests/` — mirrors `app/`; uses in-memory aiosqlite
```

- [ ] **Step 2: Commit**

```bash
git add backend/README.md
git commit -m "docs(backend): add setup runbook"
```

---

## R1 exit criteria

Run `cd backend && uv run pytest -v` — all tests in `tests/test_health.py`, `tests/test_db.py`, `tests/test_errors.py`, `tests/test_user_model.py`, `tests/test_workspace_model.py`, `tests/test_security.py`, `tests/test_auth.py`, `tests/test_me.py` pass. End-to-end: register → login → call `/me` with the bearer token → receive `{id, email, workspace_id}`.

This is the foundation R2 builds on. R2 adds Project / Document / Prediction / Annotation tables and upload/list endpoints, all reading `current_workspace_id` for tenant scoping.
