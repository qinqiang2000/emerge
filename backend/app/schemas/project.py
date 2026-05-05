from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_serializer

from app.schemas._datetime import utc_aware


class ProjectIn(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    template_id: int | None = None
    # v1 only accepts "extraction"; matching/verification reserved for future project types.
    project_type: Literal["extraction"] = "extraction"


class ProjectOut(BaseModel):
    id: int
    workspace_id: int
    name: str
    created_at: datetime
    created_by: int
    project_type: str = "extraction"
    template_id: int | None = None
    active_version_id: int | None = None
    published_version_id: int | None = None
    api_code: str | None = None
    api_published_at: datetime | None = None

    model_config = {"from_attributes": True}

    @field_serializer("created_at", "api_published_at")
    def _serialize_dt(self, v: datetime | None) -> str | None:
        aware = utc_aware(v)
        return aware.isoformat() if aware else None
