from app.schemas.schema_field import FieldType, SchemaField

_PRIMITIVE: dict[FieldType, str] = {
    FieldType.STRING: "string",
    FieldType.NUMBER: "number",
    FieldType.INTEGER: "integer",
    FieldType.BOOLEAN: "boolean",
}


def _field_to_jsonschema(f: SchemaField) -> dict:
    if f.type is FieldType.ARRAY:
        return {
            "type": "array",
            "items": _object_from_fields(f.child_fields),
            "description": f.description,
        }
    spec: dict = {"type": _PRIMITIVE[f.type], "description": f.description}
    if f.enum:
        spec["enum"] = list(f.enum)
    return spec


def _object_from_fields(fields: list[SchemaField]) -> dict:
    return {
        "type": "object",
        "properties": {f.name: _field_to_jsonschema(f) for f in fields},
        "required": [f.name for f in fields if f.required],
    }


def build_response_schema(fields: list[SchemaField]) -> dict:
    """Top-level JSON Schema dict for a multi-entity extraction response."""
    return {"type": "array", "items": _object_from_fields(fields)}
