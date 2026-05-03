from datetime import datetime

from pydantic import BaseModel, Field


class ProjectIn(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    template_id: int | None = None


class ProjectOut(BaseModel):
    id: int
    workspace_id: int
    name: str
    created_at: datetime
    created_by: int
    template_id: int | None = None
    active_version_id: int | None = None
    api_code: str | None = None
    api_published_at: datetime | None = None

    model_config = {"from_attributes": True}
