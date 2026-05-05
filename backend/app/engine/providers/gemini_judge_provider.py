import json

from google import genai
from google.genai import types

from app.settings import settings


class GeminiJudgeProvider:
    """Production JudgeProvider backed by Gemini Pro (settings.default_model_pro
    per CLAUDE.md model-tier-split memory: runtime extraction uses the cheap
    flash model, judging needs the stronger pro model so the verdicts are
    actually informative).

    Mirrors GeminiProvider's client-injection pattern so tests can pass a fake
    `client` and avoid hitting the network. Unit-test scope: assert request
    shape + parsing + defensive shape-check on the response. The live network
    path is exercised by the walking-skeleton E2E.
    """

    def __init__(
        self, *, model_id: str | None = None, client: genai.Client | None = None
    ):
        self.model_id = model_id or settings.default_model_pro
        self.client = client or genai.Client(api_key=settings.google_api_key)

    async def judge(
        self,
        *,
        system: str,
        predicted_output: list[dict],
        file_bytes: bytes,
        mime_type: str,
    ) -> dict[str, dict[str, str]]:
        # Per the JudgeProvider protocol, `system` already carries the system
        # frame + schema_snapshot + predicted_output (built by
        # judge.py:_judge_prompt). The user content is therefore just the
        # document bytes — Gemini distinguishes system_instruction from user
        # parts, and routing the textual prompt through user content would
        # blur that contract.
        resp = await self.client.aio.models.generate_content(
            model=self.model_id,
            contents=[
                types.Content(
                    role="user",
                    parts=[
                        types.Part.from_bytes(data=file_bytes, mime_type=mime_type),
                    ],
                )
            ],
            config=types.GenerateContentConfig(
                system_instruction=system,
                response_mime_type="application/json",
            ),
        )
        try:
            parsed = json.loads(resp.text or "")
        except (json.JSONDecodeError, TypeError):
            return {}
        if not isinstance(parsed, dict):
            return {}
        # Defensive shape-check: drop anything that doesn't fit
        # {str: {str: str}} where the inner str is one of the three allowed
        # verdict literals. run_judge swallows exceptions and writes
        # per_field_confidence={}; returning malformed shapes here would
        # silently corrupt JudgeCalibration downstream (recompute consumes
        # the dict via `JudgeVerdict(verdict_str)` which raises ValueError on
        # garbage and is then dropped from per-doc averaging — but the
        # vibe-check `observation_count` would still tick down inconsistently).
        clean: dict[str, dict[str, str]] = {}
        for ent_idx, fields in parsed.items():
            if not isinstance(fields, dict):
                continue
            inner: dict[str, str] = {}
            for fname, verdict in fields.items():
                if isinstance(verdict, str) and verdict in (
                    "up",
                    "down",
                    "uncertain",
                ):
                    inner[str(fname)] = verdict
            if inner:
                clean[str(ent_idx)] = inner
        return clean
