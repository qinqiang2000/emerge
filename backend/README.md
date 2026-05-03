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
