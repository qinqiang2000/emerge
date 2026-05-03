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
