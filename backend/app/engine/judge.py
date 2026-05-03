import json
import logging
from collections import deque
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import Document
from app.models.prediction import Prediction
from app.models.project_version import ProjectVersion

log = logging.getLogger(__name__)


class JudgeProvider(Protocol):
    async def judge(
        self, *, system: str, predicted_output: list[dict], file_bytes: bytes, mime_type: str
    ) -> dict[str, dict[str, str]]:
        ...


JUDGE_SYSTEM_FRAME = """\
You are an evaluation auditor for emerge. You will see (a) the document image/PDF, (b) the
schema describing each expected field, (c) the predicted JSON. For each entity index and each
field present in the prediction, return a verdict:
- "up"        → the field value is correct given the document
- "down"      → the field value is wrong
- "uncertain" → you cannot confidently decide
Return ONLY a JSON object of shape: { "<entity_idx>": { "<field_name>": "up|down|uncertain" } }.
Do not include fields that are absent from the prediction.\
"""


def _judge_prompt(version: ProjectVersion, output: list[dict]) -> str:
    return (
        JUDGE_SYSTEM_FRAME
        + "\n\nSchema fields:\n"
        + json.dumps(version.schema_snapshot, ensure_ascii=False, indent=2)
        + "\n\nPredicted output:\n"
        + json.dumps(output, ensure_ascii=False, indent=2)
    )


class FakeJudgeProvider:
    def __init__(self, *, canned: list):
        self._queue = deque(canned)

    async def judge(self, *, system, predicted_output, file_bytes, mime_type):
        if not self._queue:
            raise RuntimeError("FakeJudgeProvider out of canned responses")
        nxt = self._queue.popleft()
        if isinstance(nxt, BaseException):
            raise nxt
        return nxt


def get_judge_provider() -> JudgeProvider:
    """FastAPI dep. Default raises — production wiring (gemini-3.1-pro-preview-backed
    JudgeProvider) lands with R6's `default_model_pro` settings split per CLAUDE.md.
    Tests substitute via `app.dependency_overrides[get_judge_provider] = lambda: fake`.
    """
    raise NotImplementedError("configure judge provider via dependency_overrides or settings")


async def run_judge(
    prediction_id: int,
    *,
    session: AsyncSession,
    judge: JudgeProvider,
) -> Prediction:
    pred = (
        await session.execute(select(Prediction).where(Prediction.id == prediction_id))
    ).scalar_one()
    doc = (await session.execute(select(Document).where(Document.id == pred.document_id))).scalar_one()
    version = (
        await session.execute(
            select(ProjectVersion).where(ProjectVersion.id == pred.project_version_id)
        )
    ).scalar_one()

    system = _judge_prompt(version, pred.output)
    try:
        with open(doc.file_path, "rb") as fh:
            body = fh.read()
        verdicts = await judge.judge(
            system=system,
            predicted_output=pred.output,
            file_bytes=body,
            mime_type=doc.mime_type,
        )
        pred.per_field_confidence = verdicts
    except Exception:
        log.exception("judge failed for prediction %d", pred.id)
        pred.per_field_confidence = {}
    await session.commit()
    await session.refresh(pred)
    return pred
