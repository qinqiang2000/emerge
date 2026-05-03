from app.engine.prompt import compose_extraction_prompt
from app.engine.system_frame import SYSTEM_FRAME
from app.schemas.schema_field import FieldType, SchemaField


def test_system_frame_is_present():
    req = compose_extraction_prompt(
        fields=[SchemaField(name="x", type=FieldType.STRING, description="d")],
        global_notes="",
        model_id="claude-opus-4-7",
    )
    assert SYSTEM_FRAME in req.system


def test_each_field_description_appears_once():
    req = compose_extraction_prompt(
        fields=[
            SchemaField(name="a", type=FieldType.STRING, description="alpha"),
            SchemaField(name="b", type=FieldType.STRING, description="beta"),
        ],
        global_notes="",
        model_id="x",
    )
    assert req.system.count("alpha") == 1
    assert req.system.count("beta") == 1


def test_global_notes_appended_after_per_field():
    req = compose_extraction_prompt(
        fields=[SchemaField(name="a", type=FieldType.STRING, description="alpha")],
        global_notes="all amounts in JPY",
        model_id="x",
    )
    a_idx = req.system.find("alpha")
    g_idx = req.system.find("all amounts in JPY")
    assert g_idx > a_idx > 0


def test_examples_inlined_in_field_description():
    req = compose_extraction_prompt(
        fields=[
            SchemaField(
                name="ccy",
                type=FieldType.STRING,
                description="ISO 4217",
                examples=["JPY", "USD"],
            )
        ],
        global_notes="",
        model_id="x",
    )
    assert "JPY" in req.system and "USD" in req.system


def test_no_image_few_shot_path():
    """Spec §1: there is no path that injects example image / output pairs."""
    req = compose_extraction_prompt(
        fields=[SchemaField(name="x", type=FieldType.STRING, description="d")],
        global_notes="",
        model_id="x",
    )
    assert req.image_few_shots == []  # explicit empty; field exists for type clarity
