import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.errors import EmergeError, ErrorCode, register_error_handler


@pytest.mark.asyncio
async def test_emerge_error_returns_envelope():
    app = FastAPI()
    register_error_handler(app)

    @app.get("/boom")
    async def boom():
        raise EmergeError(ErrorCode.UNAUTHORIZED, status_code=401)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://t") as client:
        resp = await client.get("/boom")
    assert resp.status_code == 401
    body = resp.json()
    assert body == {
        "error_code": "UNAUTHORIZED",
        "error_message_en": "Authentication required.",
    }


@pytest.mark.asyncio
async def test_unhandled_exception_returns_internal_envelope():
    app = FastAPI()
    register_error_handler(app)

    @app.get("/crash")
    async def crash():
        raise ValueError("boom")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://t") as client:
        resp = await client.get("/crash")
    assert resp.status_code == 500
    assert resp.json()["error_code"] == "INTERNAL_ERROR"


@pytest.mark.asyncio
async def test_request_validation_error_returns_envelope():
    """spec §11.1: every error response uses {error_code, error_message_en}.

    pydantic body-validation must not leak FastAPI's default
    {"detail": [...]} shape to the client.
    """
    from pydantic import BaseModel, EmailStr

    app = FastAPI()
    register_error_handler(app)

    class Payload(BaseModel):
        email: EmailStr

    @app.post("/echo")
    async def echo(p: Payload):
        return {"ok": True}

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://t") as client:
        resp = await client.post("/echo", json={"email": "not-an-email"})
    assert resp.status_code == 422
    body = resp.json()
    assert body["error_code"] == "VALIDATION_FAILED"
    assert "email" in body["error_message_en"].lower()
    assert set(body.keys()) == {"error_code", "error_message_en"}
