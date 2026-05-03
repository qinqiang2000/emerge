from app.engine.derive_schema import derive_schema_candidate
from app.schemas.schema_field import FieldType


def test_simple_object_round_trip():
    fields = derive_schema_candidate([[{"shop_name": "X", "total": 100, "open": True}]])
    by = {f.name: f for f in fields}
    assert by["shop_name"].type is FieldType.STRING
    assert by["total"].type is FieldType.NUMBER
    assert by["open"].type is FieldType.BOOLEAN
    assert all("refine description" in f.description for f in fields)


def test_nested_array_of_object():
    fields = derive_schema_candidate(
        [
            [
                {
                    "line_items": [
                        {"qty": 1, "name": "Coffee"},
                        {"qty": 2, "name": "Tea"},
                    ]
                }
            ]
        ]
    )
    li = next(f for f in fields if f.name == "line_items")
    assert li.type is FieldType.ARRAY
    by_child = {c.name for c in li.child_fields}
    assert by_child == {"qty", "name"}


def test_field_required_only_if_present_in_all_entities():
    fields = derive_schema_candidate(
        [
            [{"a": "x", "b": "y"}],
            [{"a": "x"}],
        ]
    )
    by = {f.name: f for f in fields}
    assert by["a"].required is True
    assert by["b"].required is False


def test_integer_inferred_when_all_numbers_are_integers():
    fields = derive_schema_candidate([[{"qty": 1}], [{"qty": 2}]])
    by = {f.name: f for f in fields}
    assert by["qty"].type is FieldType.INTEGER


def test_skips_non_snake_case_keys():
    fields = derive_schema_candidate([[{"shopName": "X", "shop_name": "Y"}]])
    names = {f.name for f in fields}
    assert "shop_name" in names
    assert "shopName" not in names
