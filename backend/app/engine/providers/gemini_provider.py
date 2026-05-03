import time

from google import genai

from app.engine.prompt import ChatRequest
from app.engine.provider import ExtractionResult
from app.settings import settings


class GeminiProvider:
    def __init__(self, client: genai.Client | None = None):
        self.client = client or genai.Client(api_key=settings.google_api_key)

    async def extract(
        self, request: ChatRequest, *, file_bytes: bytes, mime_type: str
    ) -> ExtractionResult:
        import json

        from google.genai import types

        started = time.perf_counter()
        resp = await self.client.aio.models.generate_content(
            model=request.model_id,
            contents=[
                types.Content(
                    role="user",
                    parts=[
                        types.Part.from_bytes(data=file_bytes, mime_type=mime_type),
                        types.Part.from_text(text=request.user_text),
                    ],
                )
            ],
            config=types.GenerateContentConfig(
                system_instruction=request.system,
                response_mime_type="application/json",
                response_schema=request.response_schema,
            ),
        )
        elapsed = int((time.perf_counter() - started) * 1000)
        return ExtractionResult(
            output=json.loads(resp.text),
            tokens_used=(
                getattr(resp.usage_metadata, "total_token_count", 0)
                if resp.usage_metadata
                else 0
            ),
            latency_ms=elapsed,
            raw_response={"model": request.model_id},
        )
