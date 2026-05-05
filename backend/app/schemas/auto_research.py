from datetime import datetime

from pydantic import BaseModel, Field, field_serializer

from app.schemas._datetime import utc_aware


class RunIn(BaseModel):
    max_turn: int = Field(default=10, ge=1, le=30)
    threshold: float = Field(default=0.9, ge=0.0, le=1.0)


class TurnOut(BaseModel):
    turn: int
    diagnosis: str
    actions_applied: list[dict]
    failed_actions: list[dict]
    score_before: float
    score_after: float


class AutoResearchRunOut(BaseModel):
    id: int
    project_id: int
    status: str
    starting_version_id: int | None
    output_version_id: int | None
    judge_model_id: str
    researcher_model_id: str
    turn_count: int
    max_turn: int
    turn_history: list[dict]
    termination_reason: str | None
    started_at: datetime | None
    completed_at: datetime | None

    model_config = {"from_attributes": True}

    @field_serializer("started_at", "completed_at")
    def _serialize_dt(self, v: datetime | None) -> str | None:
        aware = utc_aware(v)
        return aware.isoformat() if aware else None
