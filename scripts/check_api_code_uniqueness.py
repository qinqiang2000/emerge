"""Pre-migration check: assert global api_code uniqueness before alembic 0015.

Alembic 0015 (`0015_global_api_code.py`) drops `UniqueConstraint(workspace_id, api_code)`
and replaces it with a global `UniqueConstraint(api_code)`. The public route
`/extract/{api_code}` has no workspace context (spec §7.1), so two workspaces
publishing the same code would be ambiguous. Before running `alembic upgrade head`
on production / staging, confirm there are no duplicate non-null `api_code` rows
in `projects`.

Usage:

    cd backend && uv run python ../scripts/check_api_code_uniqueness.py

Reads `settings.database_url` from `app.settings` (the same URL the backend uses).
Read-only: opens an async session, runs one SELECT, prints results, exits.

Exit codes:
    0  no duplicates  → safe to run alembic upgrade
    2  duplicates found → resolve before migrating (script prints the offending codes)
    1  unexpected error
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

# Always run as if cwd were backend/ so the default relative SQLite URL
# (sqlite+aiosqlite:///./data/emerge.db) resolves to backend/data/emerge.db
# and a colocated backend/.env (if any) is the one Settings() reads.
BACKEND = Path(__file__).resolve().parent.parent / "backend"
os.chdir(BACKEND)
sys.path.insert(0, str(BACKEND))

from sqlalchemy import text  # noqa: E402
from sqlalchemy.ext.asyncio import create_async_engine  # noqa: E402

from app.settings import settings  # noqa: E402


async def main() -> int:
    engine = create_async_engine(settings.database_url, future=True)
    try:
        async with engine.connect() as conn:
            result = await conn.execute(
                text(
                    "SELECT api_code, COUNT(*) AS n "
                    "FROM projects "
                    "WHERE api_code IS NOT NULL "
                    "GROUP BY api_code "
                    "HAVING COUNT(*) > 1 "
                    "ORDER BY n DESC, api_code"
                )
            )
            rows = result.all()
    finally:
        await engine.dispose()

    if not rows:
        print("OK  no duplicate non-null api_code rows in projects")
        print("    safe to run: cd backend && uv run alembic upgrade head")
        return 0

    print(f"FAIL  {len(rows)} duplicate api_code value(s) found in projects")
    print("       resolve before alembic 0015 (see backend/alembic/versions/0015_global_api_code.py)")
    print()
    print(f"  {'api_code':<48}  count")
    print(f"  {'-' * 48}  -----")
    for api_code, n in rows:
        print(f"  {api_code:<48}  {n}")
    return 2


if __name__ == "__main__":
    try:
        sys.exit(asyncio.run(main()))
    except KeyboardInterrupt:
        sys.exit(130)
