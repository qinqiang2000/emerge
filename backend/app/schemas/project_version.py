from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.schema_field import SchemaField


class ProjectVersionOut(BaseModel):
    id: int
    project_id: int
    version_number: int
    schema: list[SchemaField] = Field(serialization_alias="schema", validation_alias="schema_snapshot")
    global_notes: str = Field(serialization_alias="global_notes", validation_alias="global_notes_snapshot")
    model_id: str = Field(serialization_alias="model_id", validation_alias="model_id_snapshot")
    locked: bool
    source: str
    created_at: datetime

    model_config = {"from_attributes": True, "populate_by_name": True}


class SchemaPatchIn(BaseModel):
    schema: list[SchemaField] = Field(default_factory=list)
    global_notes: str = ""
    model_id: str
