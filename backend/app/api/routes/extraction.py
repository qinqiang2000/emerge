import asyncio
import json

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import current_workspace_id
import app.db as db_module
from app.db import get_session
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
        async with db_module.SessionFactory() as own_session:
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
