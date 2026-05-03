import re

from app.schemas.schema_field import FieldType, SchemaField

_SNAKE = re.compile(r"^[a-z][a-z0-9_]*$")
_PLACEHOLDER = "value derived from document; refine description as needed"


def _infer_type(values: list) -> FieldType | None:
    types_seen = set()
    integer_count = 0
    for v in values:
        if isinstance(v, bool):
            types_seen.add("boolean")
        elif isinstance(v, int):
            types_seen.add("integer")
            integer_count += 1
        elif isinstance(v, float):
            types_seen.add("number")
        elif isinstance(v, str):
            types_seen.add("string")
        elif isinstance(v, list):
            types_seen.add("array")
        elif v is None:
            continue
        else:
            return None
    if not types_seen:
        return None
    if types_seen == {"integer"}:
        # Require at least 2 integer observations to commit to INTEGER;
        # a single integer sample is more safely typed as NUMBER (e.g. monetary totals).
        return FieldType.INTEGER if integer_count >= 2 else FieldType.NUMBER
    if types_seen <= {"integer", "number"}:
        return FieldType.NUMBER
    if types_seen == {"string"}:
        return FieldType.STRING
    if types_seen == {"boolean"}:
        return FieldType.BOOLEAN
    if types_seen == {"array"}:
        return FieldType.ARRAY
    return FieldType.STRING


def derive_schema_candidate(annotations: list[list[dict]]) -> list[SchemaField]:
    """`annotations` is a list of saved Annotation.output values (each is array<object>)."""
    field_values: dict[str, list] = {}
    field_presence_in_entity_count: dict[str, int] = {}
    total_entities = 0
    for ann in annotations:
        for entity in ann:
            total_entities += 1
            for k, v in entity.items():
                if not _SNAKE.match(k):
                    continue
                field_values.setdefault(k, []).append(v)
                field_presence_in_entity_count[k] = field_presence_in_entity_count.get(k, 0) + 1

    out: list[SchemaField] = []
    for name, vals in field_values.items():
        ftype = _infer_type(vals)
        if ftype is None:
            continue
        required = field_presence_in_entity_count[name] == total_entities
        if ftype is FieldType.ARRAY:
            children_values: dict[str, list] = {}
            children_presence: dict[str, int] = {}
            child_entity_count = 0
            for arr in vals:
                if not isinstance(arr, list):
                    continue
                for child in arr:
                    if not isinstance(child, dict):
                        continue
                    child_entity_count += 1
                    for ck, cv in child.items():
                        if not _SNAKE.match(ck):
                            continue
                        children_values.setdefault(ck, []).append(cv)
                        children_presence[ck] = children_presence.get(ck, 0) + 1
            child_fields: list[SchemaField] = []
            for ck, cv in children_values.items():
                ct = _infer_type(cv)
                if ct is None or ct is FieldType.ARRAY:
                    continue  # skip 2-level nesting in v1 derivation
                child_fields.append(
                    SchemaField(
                        name=ck,
                        type=ct,
                        required=children_presence[ck] == child_entity_count,
                        description=_PLACEHOLDER,
                    )
                )
            if not child_fields:
                continue
            out.append(
                SchemaField(
                    name=name,
                    type=FieldType.ARRAY,
                    required=required,
                    description=_PLACEHOLDER,
                    child_fields=child_fields,
                )
            )
        else:
            out.append(
                SchemaField(name=name, type=ftype, required=required, description=_PLACEHOLDER)
            )
    return out
