from datetime import datetime

from pydantic import BaseModel

from app.schemas.schema_field import SchemaField


class TemplateOut(BaseModel):
    id: int
    workspace_id: int | None
    name: str
    description: str
    version: int
    schema: list[SchemaField]
    global_notes: str
    recommended_model_id: str
    builtin: bool
    created_at: datetime

    @classmethod
    def from_orm_row(cls, row) -> "TemplateOut":
        return cls(
            id=row.id,
            workspace_id=row.workspace_id,
            name=row.name,
            description=row.description,
            version=row.version,
            schema=[SchemaField(**f) for f in row.schema_json],
            global_notes=row.global_notes,
            recommended_model_id=row.recommended_model_id,
            builtin=row.builtin,
            created_at=row.created_at,
        )


class TemplateSaveAsIn(BaseModel):
    name: str
    description: str = ""
    create_new_version: bool = False
