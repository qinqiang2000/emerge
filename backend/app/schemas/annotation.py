from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator


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
    last_modified_by: int | None
    created_at: datetime
    last_modified_at: datetime

    model_config = {"from_attributes": True}


class AnnotationPatchIn(BaseModel):
    output: list[dict] | None = None
    notes: str | None = None


class FeedbackCorrectionIn(BaseModel):
    """One field-level correction. `field_path` is dotted with optional [n]
    indices, e.g. `total` or `line_items[2].price`."""
    entity_index: int = 0
    field_path: str = Field(min_length=1)
    correct_value: Any = None
    comment: str | None = None


class FeedbackIn(BaseModel):
    request_id: int = Field(description="prediction_id returned by /extract")
    # Full feedback: caller supplies the entire correct_output blob.
    correct_output: list[dict] | None = None
    # Partial feedback (spec §7.1): caller patches individual fields.
    corrections: list[FeedbackCorrectionIn] | None = None
    issue_type: Literal[
        "wrong_value",
        "missing_field",
        "extra_field",
        "wrong_entity_count",
        "other",
    ] | None = None
    notes: str | None = None

    @field_validator("correct_output", mode="before")
    @classmethod
    def _check(cls, v):
        if v is None:
            return v
        return _validate_array_of_object(v)

    @model_validator(mode="after")
    def _require_full_or_partial(self):
        if self.correct_output is None and not self.corrections:
            raise ValueError("feedback requires correct_output or corrections")
        return self
