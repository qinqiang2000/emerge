from collections import deque

from app.engine.prompt import ChatRequest
from app.engine.provider import ExtractionResult


class FakeProvider:
    """Test double. `canned` is a queue of either result lists or Exceptions."""

    def __init__(self, *, canned: list):
        self._queue = deque(canned)
        self.calls: list[ChatRequest] = []

    async def extract(
        self, request: ChatRequest, *, file_bytes: bytes, mime_type: str
    ) -> ExtractionResult:
        self.calls.append(request)
        if not self._queue:
            raise RuntimeError("FakeProvider out of canned responses")
        nxt = self._queue.popleft()
        if isinstance(nxt, BaseException):
            raise nxt
        return ExtractionResult(output=nxt, tokens_used=0, latency_ms=0)
