from dataclasses import dataclass, field

from app.engine.system_frame import SYSTEM_FRAME
from app.schemas.schema_field import SchemaField


@dataclass
class ChatRequest:
    """Provider-agnostic prompt envelope. Providers translate to their SDK shapes."""

    system: str
    user_text: str
    model_id: str
    response_schema: dict
    image_few_shots: list = field(default_factory=list)  # always [] in v1 — invariant


def _format_field(idx: int, f: SchemaField) -> str:
    parts = [f"{idx}. `{f.name}` ({f.type.value}{', required' if f.required else ', optional'})"]
    parts.append(f"   description: {f.description}")
    if f.examples:
        parts.append(f"   examples: {', '.join(f.examples)}")
    if f.enum:
        parts.append(f"   enum: {', '.join(f.enum)}")
    if f.child_fields:
        parts.append("   child fields:")
        for j, cf in enumerate(f.child_fields, 1):
            parts.append(f"     {j}. `{cf.name}` ({cf.type.value}): {cf.description}")
    return "\n".join(parts)


def compose_extraction_prompt(
    *,
    fields: list[SchemaField],
    global_notes: str,
    model_id: str,
) -> ChatRequest:
    field_lines = "\n".join(_format_field(i, f) for i, f in enumerate(fields, 1))
    system = SYSTEM_FRAME
    if field_lines:
        system += "\n\nPer-field instructions:\n" + field_lines
    if global_notes.strip():
        system += "\n\nGlobal notes:\n" + global_notes.strip()
    from app.engine.response_schema import build_response_schema

    return ChatRequest(
        system=system,
        user_text="Extract structured data from the attached document.",
        model_id=model_id,
        response_schema=build_response_schema(fields),
        image_few_shots=[],
    )
