from typing import Annotated, Literal, Union

from pydantic import BaseModel, Field, TypeAdapter

from app.schemas.schema_field import FieldType, SchemaField


class _ActionBase(BaseModel):
    kind: str


class EditFieldDescriptionAction(_ActionBase):
    kind: Literal["edit_field_description"] = "edit_field_description"
    field_name: str
    new_text: str


class AddFieldExamplesAction(_ActionBase):
    kind: Literal["add_field_examples"] = "add_field_examples"
    field_name: str
    examples: list[str]


class AddFieldAction(_ActionBase):
    kind: Literal["add_field"] = "add_field"
    name: str
    type: FieldType
    description: str
    required: bool = True


class RemoveFieldAction(_ActionBase):
    kind: Literal["remove_field"] = "remove_field"
    field_name: str


class MakeOptionalAction(_ActionBase):
    kind: Literal["make_optional"] = "make_optional"
    field_name: str


class MakeRequiredAction(_ActionBase):
    kind: Literal["make_required"] = "make_required"
    field_name: str


class EditGlobalNotesAction(_ActionBase):
    kind: Literal["edit_global_notes"] = "edit_global_notes"
    text: str


class AddFieldEnumAction(_ActionBase):
    kind: Literal["add_field_enum"] = "add_field_enum"
    field_name: str
    values: list[str]


Action = Annotated[
    Union[
        EditFieldDescriptionAction,
        AddFieldExamplesAction,
        AddFieldAction,
        RemoveFieldAction,
        MakeOptionalAction,
        MakeRequiredAction,
        EditGlobalNotesAction,
        AddFieldEnumAction,
    ],
    Field(discriminator="kind"),
]

_action_adapter = TypeAdapter(Action)


def parse_action(raw: dict) -> Action:
    return _action_adapter.validate_python(raw)


def _find(schema: list[SchemaField], name: str) -> int:
    for i, f in enumerate(schema):
        if f.name == name:
            return i
    raise ValueError(f"field {name!r} not in schema")


def _replace(schema: list[SchemaField], idx: int, new: SchemaField) -> list[SchemaField]:
    return [*schema[:idx], new, *schema[idx + 1:]]


def apply_action(
    schema: list[SchemaField], notes: str, action: Action
) -> tuple[list[SchemaField], str]:
    if isinstance(action, EditFieldDescriptionAction):
        i = _find(schema, action.field_name)
        return _replace(schema, i, schema[i].model_copy(update={"description": action.new_text})), notes
    if isinstance(action, AddFieldExamplesAction):
        i = _find(schema, action.field_name)
        merged = list(schema[i].examples) + [e for e in action.examples if e not in schema[i].examples]
        return _replace(schema, i, schema[i].model_copy(update={"examples": merged})), notes
    if isinstance(action, AddFieldAction):
        if any(f.name == action.name for f in schema):
            raise ValueError(f"field {action.name!r} already exists")
        return [
            *schema,
            SchemaField(
                name=action.name,
                type=action.type,
                description=action.description,
                required=action.required,
            ),
        ], notes
    if isinstance(action, RemoveFieldAction):
        i = _find(schema, action.field_name)
        return [*schema[:i], *schema[i + 1:]], notes
    if isinstance(action, MakeOptionalAction):
        i = _find(schema, action.field_name)
        return _replace(schema, i, schema[i].model_copy(update={"required": False})), notes
    if isinstance(action, MakeRequiredAction):
        i = _find(schema, action.field_name)
        return _replace(schema, i, schema[i].model_copy(update={"required": True})), notes
    if isinstance(action, EditGlobalNotesAction):
        return schema, action.text
    if isinstance(action, AddFieldEnumAction):
        i = _find(schema, action.field_name)
        if schema[i].type is not FieldType.STRING:
            raise ValueError(
                f"add_field_enum requires string field; '{action.field_name}' is {schema[i].type.value}"
            )
        return _replace(schema, i, schema[i].model_copy(update={"enum": action.values})), notes
    raise TypeError(f"unknown action {type(action)!r}")
