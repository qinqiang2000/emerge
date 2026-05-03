from enum import Enum

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


class ErrorCode(str, Enum):
    UNAUTHORIZED = "UNAUTHORIZED"
    FORBIDDEN = "FORBIDDEN"
    NOT_FOUND = "NOT_FOUND"
    VALIDATION_FAILED = "VALIDATION_FAILED"
    CONFLICT = "CONFLICT"
    INTERNAL_ERROR = "INTERNAL_ERROR"
    RATE_LIMITED = "RATE_LIMITED"


_MESSAGES: dict[ErrorCode, str] = {
    ErrorCode.UNAUTHORIZED: "Authentication required.",
    ErrorCode.FORBIDDEN: "You do not have permission to perform this action.",
    ErrorCode.NOT_FOUND: "Resource not found.",
    ErrorCode.VALIDATION_FAILED: "Request validation failed.",
    ErrorCode.CONFLICT: "Resource state conflict.",
    ErrorCode.INTERNAL_ERROR: "An internal error occurred.",
    ErrorCode.RATE_LIMITED: "Too many requests. Slow down and try again.",
}


class EmergeError(Exception):
    def __init__(
        self,
        code: ErrorCode,
        *,
        status_code: int = 400,
        message_override: str | None = None,
    ):
        self.code = code
        self.status_code = status_code
        self.message = message_override or _MESSAGES[code]
        super().__init__(self.message)


def _format_validation_summary(errors: list[dict]) -> str:
    """Flatten pydantic ValidationError list into a single human-readable string.

    Spec §11.1 fixes the envelope to {error_code, error_message_en} — no
    structured `details` field — so we surface the first validation error's
    location + message inside `error_message_en` for frontend hinting.
    """
    if not errors:
        return _MESSAGES[ErrorCode.VALIDATION_FAILED]
    first = errors[0]
    loc = ".".join(str(p) for p in first.get("loc", []) if p != "body")
    msg = first.get("msg", "invalid value")
    return f"{loc}: {msg}" if loc else msg


def register_error_handler(app: FastAPI) -> None:
    @app.exception_handler(EmergeError)
    async def _handle_emerge(_: Request, exc: EmergeError):
        return JSONResponse(
            status_code=exc.status_code,
            content={"error_code": exc.code.value, "error_message_en": exc.message},
        )

    @app.exception_handler(RequestValidationError)
    async def _handle_validation(_: Request, exc: RequestValidationError):
        return JSONResponse(
            status_code=422,
            content={
                "error_code": ErrorCode.VALIDATION_FAILED.value,
                "error_message_en": _format_validation_summary(exc.errors()),
            },
        )

    @app.middleware("http")
    async def _handle_unhandled(request: Request, call_next):
        try:
            return await call_next(request)
        except Exception:
            return JSONResponse(
                status_code=500,
                content={
                    "error_code": ErrorCode.INTERNAL_ERROR.value,
                    "error_message_en": _MESSAGES[ErrorCode.INTERNAL_ERROR],
                },
            )
