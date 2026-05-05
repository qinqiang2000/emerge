from datetime import datetime

from pydantic import BaseModel, field_serializer

from app.schemas._datetime import utc_aware


class DocumentOut(BaseModel):
    id: int
    project_id: int
    filename: str
    mime_type: str
    page_count: int
    byte_size: int
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}

    @field_serializer("created_at")
    def _serialize_dt(self, v: datetime | None) -> str | None:
        aware = utc_aware(v)
        return aware.isoformat() if aware else None


class DocumentDetailOut(DocumentOut):
    latest_prediction: dict | None = None
    latest_annotation: dict | None = None
