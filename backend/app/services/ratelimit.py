from fastapi import Request
from slowapi import Limiter
from slowapi.util import get_remote_address

# Module-level limit string — tests can monkeypatch this to tighten the limit.
EXTRACT_RATE_LIMIT = "60/minute"


def key_or_remote(request: Request) -> str:
    """Rate-limit bucket: prefer X-Api-Key, fall back to IP for unauthenticated calls."""
    return request.headers.get("X-Api-Key") or get_remote_address(request)


def _extract_limit() -> str:
    return EXTRACT_RATE_LIMIT


limiter = Limiter(key_func=key_or_remote)
