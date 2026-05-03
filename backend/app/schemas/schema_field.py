import re
from enum import Enum

from pydantic import BaseModel, Field, model_validator

_SNAKE = re.compile(r"^[a-z][a-z0-9_]*$")


class FieldType(str, Enum):
    STRING = "string"
    NUMBER = "number"
    INTEGER = "integer"
    BOOLEAN = "boolean"
    ARRAY = "array"  # array<object>; uses child_fields


class SchemaField(BaseModel):
    name: str
    type: FieldType
    required: bool = True
    description: str
    examples: list[str] = Field(default_factory=list)
    enum: list[str] | None = None
    child_fields: list["SchemaField"] = Field(default_factory=list)

    @model_validator(mode="after")
    def _validate(self) -> "SchemaField":
        if not _SNAKE.match(self.name):
            raise ValueError(
                f"name '{self.name}' must be snake_case ASCII (lowercase letters, digits, underscores)"
            )
        if self.type is FieldType.ARRAY and not self.child_fields:
            raise ValueError(f"array field '{self.name}' must declare child_fields")
        if self.type is not FieldType.ARRAY and self.child_fields:
            raise ValueError(f"non-array field '{self.name}' cannot have child_fields")
        if self.enum is not None and self.type is not FieldType.STRING:
            raise ValueError(f"enum is only allowed on string fields ('{self.name}')")
        return self


SchemaField.model_rebuild()
