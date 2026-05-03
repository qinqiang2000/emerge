from datetime import datetime

from pydantic import BaseModel, Field, field_validator

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


class TemplateSaveAsIn(BaseModel):
    name: str
    description: str = ""
    create_new_version: bool = False
