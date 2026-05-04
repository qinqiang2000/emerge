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


# Spec §3.2 hard rule: per_field_evidence stores page / quote / rationale /
# source_text_hash only — no bbox / coordinates / polygons / regions / spans.
# Allow-list rather than deny-list so any future provider key surprise is
# rejected by default, not silently persisted.
_ALLOWED_EVIDENCE_KEYS = frozenset({"page", "quote", "rationale", "source_text_hash"})


def _sanitize_evidence(evidence) -> dict | None:
    """Strip non-allow-listed keys from per_field_evidence.

    Cells whose only keys were forbidden are dropped entirely so callers see a
    coherent shape; entities reduced to no fields are also dropped. Returning
    None when nothing survives keeps the column nullable rather than {}.
    """
    if not isinstance(evidence, dict):
        return None
    cleaned: dict[str, dict] = {}
    for entity_idx, ent in evidence.items():
        if not isinstance(ent, dict):
            continue
        ent_cleaned: dict[str, dict] = {}
        for field_name, cell in ent.items():
            if not isinstance(cell, dict):
                continue
            allowed = {k: v for k, v in cell.items() if k in _ALLOWED_EVIDENCE_KEYS}
            if allowed:
                ent_cleaned[field_name] = allowed
        if ent_cleaned:
            cleaned[entity_idx] = ent_cleaned
    return cleaned or None


async def extract_document(
    document_id: int,
    *,
    session: AsyncSession,
    provider: Provider,
    project_version_id: int | None = None,
) -> Prediction:
    """Run extraction on a document.

    `project_version_id` overrides the project's active version. Public API
    passes `project.published_version_id` here so editing the Lab active
    version cannot accidentally change production behavior (spec §7.2).
    """
    d = (await session.execute(select(Document).where(Document.id == document_id))).scalar_one()
    p = (await session.execute(select(Project).where(Project.id == d.project_id))).scalar_one()
    version_id = project_version_id if project_version_id is not None else p.active_version_id
    if version_id is None:
        raise ValueError(f"project {p.id} has no active version")
    v = (
        await session.execute(
            select(ProjectVersion).where(ProjectVersion.id == version_id)
        )
    ).scalar_one_or_none()
    if v is None or v.project_id != p.id:
        raise ValueError(f"version {version_id} does not belong to project {p.id}")

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
        # Field-level evidence is optional; provider may surface it on raw_response.
        # Spec §3.2: page / quote / rationale / source_text_hash only — never bbox.
        evidence = None
        if result.raw_response and isinstance(result.raw_response, dict):
            ev = result.raw_response.get("per_field_evidence")
            evidence = _sanitize_evidence(ev)
        pred = Prediction(
            document_id=d.id,
            project_version_id=v.id,
            model_id=v.model_id_snapshot,
            prompt_hash=prompt_hash,
            output=result.output,
            per_field_confidence={},
            per_field_evidence=evidence,
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
