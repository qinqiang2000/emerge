from app.engine.response_schema import build_response_schema
from app.schemas.schema_field import FieldType, SchemaField


def test_top_level_is_array_of_object():
    schema = build_response_schema(
        [SchemaField(name="x", type=FieldType.STRING, description="d")]
    )
    assert schema["type"] == "array"
    assert schema["items"]["type"] == "object"
    assert "x" in schema["items"]["properties"]


def test_required_only_listed_when_required():
    schema = build_response_schema(
        [
            SchemaField(name="a", type=FieldType.STRING, required=True, description="d"),
            SchemaField(name="b", type=FieldType.STRING, required=False, description="d"),
        ]
    )
    assert set(schema["items"]["required"]) == {"a"}


def test_enum_passes_through():
    schema = build_response_schema(
        [
            SchemaField(
                name="ccy",
                type=FieldType.STRING,
                description="d",
                enum=["JPY", "USD"],
            )
        ]
    )
    assert schema["items"]["properties"]["ccy"]["enum"] == ["JPY", "USD"]


def test_nested_array_of_object():
    schema = build_response_schema(
        [
            SchemaField(
                name="line_items",
                type=FieldType.ARRAY,
                description="d",
                child_fields=[
                    SchemaField(name="qty", type=FieldType.INTEGER, description="d"),
                ],
            )
        ]
    )
    li = schema["items"]["properties"]["line_items"]
    assert li["type"] == "array"
    assert li["items"]["type"] == "object"
    assert "qty" in li["items"]["properties"]


def test_empty_fields_returns_array_of_object_with_no_props():
    schema = build_response_schema([])
    assert schema == {
        "type": "array",
        "items": {"type": "object", "properties": {}, "required": []},
    }
