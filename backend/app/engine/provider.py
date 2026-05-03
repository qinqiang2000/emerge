from dataclasses import dataclass
from typing import Protocol

from app.engine.prompt import ChatRequest


@dataclass
class ExtractionResult:
    output: list[dict]
    tokens_used: int
    latency_ms: int
    raw_response: dict | None = None
    cost_estimate: float = 0.0


class Provider(Protocol):
    async def extract(
        self,
        request: ChatRequest,
        *,
        file_bytes: bytes,
        mime_type: str,
    ) -> ExtractionResult:
        ...
