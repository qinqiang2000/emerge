import json
from collections import deque
from dataclasses import dataclass, field
from typing import Protocol

from app.services.autoresearch.actions import Action, parse_action
from app.schemas.schema_field import SchemaField


@dataclass
class ResearcherState:
    """Snapshot of project state passed to the researcher each turn.

    counterexample_summary: summary statistics ONLY (e.g. miss count, pattern
    labels).  Raw (input, expected, wrong) triples MUST NEVER appear here —
    spec §1 hard rule: counterexamples never enter any LLM prompt.  Even
    AutoResearch uses them only as an evaluator regression set; the researcher
    only sees aggregated patterns, never raw I/O pairs.
    """

    schema: list[SchemaField]
    global_notes: str
    judge_results: dict
    counterexample_summary: dict
    turn_history: list[dict]


@dataclass
class DiagnosisResult:
    diagnosis: str
    actions: list[Action] = field(default_factory=list)


# Eight whitelisted actions — closed list per spec §5.2.
# No image few-shot, no bbox, no actions outside this list.
RESEARCHER_SYSTEM_FRAME = """\
You are emerge's AutoResearcher. Your job is to look at the current Project state — the schema,
global notes, judge results, and counterexample summary — and decide which whitelisted actions
to take to improve the schema.

The ONLY actions you may emit are exactly these 8:
  1. edit_field_description(field_name, new_text)
  2. add_field_examples(field_name, examples)
  3. add_field(name, type, description, required)
  4. remove_field(field_name)
  5. make_optional(field_name)
  6. make_required(field_name)
  7. edit_global_notes(text)
  8. add_field_enum(field_name, values)

HARD CONSTRAINTS — violating any of these makes your output invalid:
- You MUST NOT invent or emit any action outside the 8 listed above.
- You MUST NOT include image few-shot examples, image bytes, file paths, or any
  encoded image data anywhere in your response.
- You MUST NOT include raw (input, expected_output, wrong_output) pairs.
- The counterexample_summary field you receive contains only aggregated statistics
  and pattern labels — never reproduce or reference individual document contents.

Respond with ONLY a JSON object (no markdown fences):
{
  "diagnosis": "<concise explanation of what is wrong and why>",
  "actions": [
    {"kind": "<action_name>", <action-specific fields>},
    ...
  ]
}
Each action object must have a "kind" key matching exactly one of the 8 names above.\
"""


class ResearcherProvider(Protocol):
    async def diagnose_and_act(self, state: ResearcherState) -> DiagnosisResult:
        ...


class FakeResearcherProvider:
    """Deterministic stub for tests; pops pre-canned DiagnosisResult objects."""

    def __init__(self, *, canned: list):
        self._queue: deque = deque(canned)

    async def diagnose_and_act(self, state: ResearcherState) -> DiagnosisResult:
        if not self._queue:
            raise RuntimeError("FakeResearcherProvider out of canned responses")
        nxt = self._queue.popleft()
        if isinstance(nxt, BaseException):
            raise nxt
        return nxt


class GeminiResearcherProvider:
    """Concrete researcher backed by google-genai.

    Lazy-imports google.genai so that test modules using only FakeResearcherProvider
    can run without the SDK installed.
    """

    def __init__(self, model_id: str, client=None):
        from google import genai

        from app.settings import settings

        self.model_id = model_id
        self.client = client or genai.Client(api_key=settings.google_api_key)

    async def diagnose_and_act(self, state: ResearcherState) -> DiagnosisResult:
        from google.genai import types

        user_payload = json.dumps(
            {
                "schema": [f.model_dump() for f in state.schema],
                "global_notes": state.global_notes,
                "judge_results": state.judge_results,
                "counterexample_summary": state.counterexample_summary,
                "turn_history": state.turn_history,
            },
            ensure_ascii=False,
        )

        resp = await self.client.aio.models.generate_content(
            model=self.model_id,
            contents=[
                types.Content(
                    role="user",
                    parts=[types.Part.from_text(text=user_payload)],
                )
            ],
            config=types.GenerateContentConfig(
                system_instruction=RESEARCHER_SYSTEM_FRAME,
                response_mime_type="application/json",
                # No response_schema — researcher returns a dict with free-form
                # diagnosis text; system prompt enforces the shape.
            ),
        )

        body = json.loads(resp.text)
        actions = [parse_action(a) for a in body.get("actions", [])]
        return DiagnosisResult(diagnosis=body.get("diagnosis", ""), actions=actions)
