import pytest
from pydantic import ValidationError

from app.schemas.schema_field import FieldType, SchemaField


def test_basic_string_field():
    f = SchemaField(name="shop_name", type=FieldType.STRING, required=True, description="店名")
    assert f.name == "shop_name"
    assert f.examples == []


def test_array_field_must_have_child_fields():
    with pytest.raises(ValidationError):
        SchemaField(name="line_items", type=FieldType.ARRAY, description="x")


def test_array_field_with_children_ok():
    f = SchemaField(
        name="line_items",
        type=FieldType.ARRAY,
        description="x",
        child_fields=[SchemaField(name="qty", type=FieldType.NUMBER, description="quantity")],
    )
    assert f.child_fields[0].name == "qty"


def test_field_name_must_be_snake_case():
    with pytest.raises(ValidationError):
        SchemaField(name="ShopName", type=FieldType.STRING, description="bad")
    with pytest.raises(ValidationError):
        SchemaField(name="shop-name", type=FieldType.STRING, description="bad")


def test_enum_only_for_string():
    with pytest.raises(ValidationError):
        SchemaField(
            name="amount", type=FieldType.NUMBER, description="d", enum=["a", "b"]
        )
