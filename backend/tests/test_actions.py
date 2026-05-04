import pytest

from app.services.autoresearch.actions import (
    AddFieldAction,
    AddFieldEnumAction,
    AddFieldExamplesAction,
    EditFieldDescriptionAction,
    EditGlobalNotesAction,
    MakeOptionalAction,
    MakeRequiredAction,
    RemoveFieldAction,
    apply_action,
    parse_action,
)
from app.schemas.schema_field import FieldType, SchemaField


def _baseline() -> list[SchemaField]:
    return [
        SchemaField(name="shop_name", type=FieldType.STRING, description="店名"),
        SchemaField(name="total_amount", type=FieldType.NUMBER, description="金額"),
    ]


def test_edit_field_description():
    schema, notes = apply_action(
        _baseline(), "",
        EditFieldDescriptionAction(field_name="shop_name", new_text="店名（更新）"),
    )
    assert next(f for f in schema if f.name == "shop_name").description == "店名（更新）"


def test_add_field():
    schema, notes = apply_action(
        _baseline(), "",
        AddFieldAction(name="currency", type="string", description="ISO 4217", required=True),
    )
    assert any(f.name == "currency" for f in schema)


def test_remove_field():
    schema, notes = apply_action(
        _baseline(), "", RemoveFieldAction(field_name="shop_name")
    )
    assert all(f.name != "shop_name" for f in schema)


def test_make_optional_then_required():
    s1, _ = apply_action(_baseline(), "", MakeOptionalAction(field_name="shop_name"))
    assert next(f for f in s1 if f.name == "shop_name").required is False
    s2, _ = apply_action(s1, "", MakeRequiredAction(field_name="shop_name"))
    assert next(f for f in s2 if f.name == "shop_name").required is True


def test_add_field_examples():
    schema, _ = apply_action(
        _baseline(), "",
        AddFieldExamplesAction(field_name="shop_name", examples=["スターバックス", "Doutor"]),
    )
    assert "スターバックス" in next(f for f in schema if f.name == "shop_name").examples


def test_add_field_enum_only_on_string():
    with pytest.raises(ValueError):
        apply_action(
            _baseline(), "",
            AddFieldEnumAction(field_name="total_amount", values=["x", "y"]),
        )


def test_edit_global_notes():
    _, notes = apply_action(_baseline(), "old", EditGlobalNotesAction(text="new"))
    assert notes == "new"


def test_remove_unknown_field_raises():
    with pytest.raises(ValueError):
        apply_action(_baseline(), "", RemoveFieldAction(field_name="nope"))


def test_parse_action_round_trip():
    raw = {"kind": "edit_field_description", "field_name": "x", "new_text": "y"}
    action = parse_action(raw)
    assert isinstance(action, EditFieldDescriptionAction)
