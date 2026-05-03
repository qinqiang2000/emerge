import time

from openai import AsyncOpenAI

from app.engine.prompt import ChatRequest
from app.engine.provider import ExtractionResult
from app.settings import settings


class OpenAIProvider:
    def __init__(self, client: AsyncOpenAI | None = None):
        self.client = client or AsyncOpenAI(api_key=settings.openai_api_key)

    async def extract(
        self, request: ChatRequest, *, file_bytes: bytes, mime_type: str
    ) -> ExtractionResult:
        import base64
        import json

        b64 = base64.b64encode(file_bytes).decode()
        data_url = f"data:{mime_type};base64,{b64}"

        started = time.perf_counter()
        resp = await self.client.chat.completions.create(
            model=request.model_id,
            messages=[
                {"role": "system", "content": request.system},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": request.user_text},
                        {"type": "image_url", "image_url": {"url": data_url}},
                    ],
                },
            ],
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "emerge_extract",
                    "schema": {
                        "type": "object",
                        "properties": {"entities": request.response_schema},
                        "required": ["entities"],
                    },
                    "strict": True,
                },
            },
        )
        elapsed = int((time.perf_counter() - started) * 1000)
        wrapped = json.loads(resp.choices[0].message.content)
        return ExtractionResult(
            output=wrapped["entities"],
            tokens_used=resp.usage.total_tokens if resp.usage else 0,
            latency_ms=elapsed,
            raw_response={"id": resp.id, "model": resp.model},
        )
