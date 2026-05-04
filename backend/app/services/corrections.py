import copy
import re
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.annotation import Annotation, AnnotationRole, AnnotationStatus
from app.models.document import Document
from app.models.prediction import Prediction


class PredictionScopeError(Exception):
    """Prediction does not belong to the supplied project or document."""


class FeedbackPatchError(Exception):
    """Partial feedback path could not be applied to the original prediction output."""


_SEG = re.compile(r"^([a-zA-Z_][a-zA-Z0-9_]*)((?:\[\d+\])*)$")


def _parse_path(path: str) -> list[str | int]:
    """Parse a dotted/indexed path like `line_items[2].price` into segments."""
    parts: list[str | int] = []
    for chunk in path.split("."):
        m = _SEG.match(chunk)
        if not m:
            raise FeedbackPatchError(f"invalid field_path segment '{chunk}'")
        parts.append(m.group(1))
        idx_part = m.group(2)
        if idx_part:
            for raw in re.findall(r"\[(\d+)\]", idx_part):
                parts.append(int(raw))
    return parts


def apply_feedback_corrections(
    base_output: list[dict], corrections: list[dict]
) -> list[dict]:
    """Apply partial corrections to a copy of `base_output`.

    Each correction is `{ entity_index, field_path, correct_value }` where
    `field_path` is dotted with optional `[n]` indices. Raises
    FeedbackPatchError if any correction targets a missing entity or path.
    """
    merged: list[dict] = copy.deepcopy(base_output)
    for c in corrections:
        ent_idx = int(c["entity_index"])
        if ent_idx < 0 or ent_idx >= len(merged):
            raise FeedbackPatchError(
                f"entity_index {ent_idx} out of range (have {len(merged)} entities)"
            )
        segments = _parse_path(c["field_path"])
        cursor: Any = merged[ent_idx]
        for seg in segments[:-1]:
            if isinstance(seg, int):
                if not isinstance(cursor, list) or seg >= len(cursor):
                    raise FeedbackPatchError(
                        f"path index {seg} cannot traverse {type(cursor).__name__}"
                    )
                cursor = cursor[seg]
            else:
                if not isinstance(cursor, dict):
                    raise FeedbackPatchError(
                        f"path key '{seg}' cannot traverse {type(cursor).__name__}"
                    )
                # Permit creating intermediate dicts only when key already exists.
                if seg not in cursor:
                    raise FeedbackPatchError(f"path key '{seg}' not present in entity")
                cursor = cursor[seg]
        last = segments[-1]
        if isinstance(last, int):
            if not isinstance(cursor, list) or last >= len(cursor):
                raise FeedbackPatchError(
                    f"final index {last} cannot apply to {type(cursor).__name__}"
                )
            cursor[last] = c["correct_value"]
        else:
            if not isinstance(cursor, dict):
                raise FeedbackPatchError(
                    f"final key '{last}' cannot apply to {type(cursor).__name__}"
                )
            cursor[last] = c["correct_value"]
    return merged


async def save_correction(
    *,
    session: AsyncSession,
    document_id: int,
    output: list[dict],
    user_id: int,
    notes: str | None = None,
    parent_prediction_id: int | None = None,
) -> Annotation:
    if parent_prediction_id is not None:
        # Symmetry with save_counterexample: never let an Annotation reference
        # a prediction belonging to a different document. Even though the
        # current API path scopes by document_id, callers reaching this
        # service layer directly (R5/R6) must not bypass the guard.
        pred = (
            await session.execute(
                select(Prediction).where(Prediction.id == parent_prediction_id)
            )
        ).scalar_one_or_none()
        if pred is None or pred.document_id != document_id:
            raise PredictionScopeError(
                f"prediction {parent_prediction_id} does not belong to document {document_id}"
            )
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
