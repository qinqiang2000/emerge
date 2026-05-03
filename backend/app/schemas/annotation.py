from datetime import datetime

from pydantic import BaseModel, Field, field_validator


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


class FeedbackIn(BaseModel):
    request_id: int = Field(description="prediction_id returned by /extract")
    correct_output: list[dict]
    notes: str | None = None

    @field_validator("correct_output", mode="before")
    @classmethod
    def _check(cls, v):
        return _validate_array_of_object(v)
