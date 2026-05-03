from datetime import datetime

from pydantic import BaseModel


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
