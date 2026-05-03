from enum import Enum

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


class ErrorCode(str, Enum):
    UNAUTHORIZED = "UNAUTHORIZED"
    FORBIDDEN = "FORBIDDEN"
    NOT_FOUND = "NOT_FOUND"
    VALIDATION_FAILED = "VALIDATION_FAILED"
    CONFLICT = "CONFLICT"
    INTERNAL_ERROR = "INTERNAL_ERROR"


_MESSAGES: dict[ErrorCode, str] = {
    ErrorCode.UNAUTHORIZED: "Authentication required.",
    ErrorCode.FORBIDDEN: "You do not have permission to perform this action.",
    ErrorCode.NOT_FOUND: "Resource not found.",
    ErrorCode.VALIDATION_FAILED: "Request validation failed.",
    ErrorCode.CONFLICT: "Resource state conflict.",
    ErrorCode.INTERNAL_ERROR: "An internal error occurred.",
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


def register_error_handler(app: FastAPI) -> None:
    @app.exception_handler(EmergeError)
    async def _handle_emerge(_: Request, exc: EmergeError):
        return JSONResponse(
            status_code=exc.status_code,
            content={"error_code": exc.code.value, "error_message_en": exc.message},
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
