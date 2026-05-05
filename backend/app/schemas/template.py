from datetime import datetime

from pydantic import BaseModel, Field, field_serializer, field_validator

from app.schemas._datetime import utc_aware
from app.schemas.schema_field import SchemaField


class TemplateOut(BaseModel):
    id: int
    workspace_id: int | None
    name: str
    description: str
    version: int
    schema: list[SchemaField] = Field(validation_alias="schema_json")
    global_notes: str
    recommended_model_id: str
    builtin: bool
    created_at: datetime

    model_config = {"from_attributes": True, "populate_by_name": True, "protected_namespaces": ()}

    @field_validator("schema", mode="before")
    @classmethod
    def _coerce_schema(cls, v):
        if isinstance(v, list) and v and isinstance(v[0], dict):
            return [SchemaField(**f) for f in v]
        return v

    @field_serializer("created_at")
    def _serialize_dt(self, v: datetime | None) -> str | None:
        aware = utc_aware(v)
        return aware.isoformat() if aware else None


class TemplateSaveAsIn(BaseModel):
    name: str
    description: str = ""
    create_new_version: bool = False
