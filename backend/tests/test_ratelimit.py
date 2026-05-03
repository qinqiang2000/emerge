import io

import pytest

import app.services.ratelimit as rl_module
from app.engine.providers import get_provider_dep
from app.engine.providers.fake import FakeProvider
from tests.conftest import _setup_published_project


@pytest.mark.asyncio
async def test_rate_limit_returns_429(client, db_session, app, tmp_path, monkeypatch):
    api_code, key = await _setup_published_project(client, db_session, monkeypatch, tmp_path)

    # Tighten the limit to 2/minute via monkeypatch (callable reads this at request time).
    monkeypatch.setattr(rl_module, "EXTRACT_RATE_LIMIT", "2/minute")

    fake = FakeProvider(canned=[[{"x": "1"}]] * 10)
    app.dependency_overrides[get_provider_dep] = lambda: fake

    # Reset any accumulated hits before the test.
    rl_module.limiter.reset()
    try:
        for _ in range(2):
            r = await client.post(
                f"/extract/{api_code}",
                files=[("file", ("a.pdf", io.BytesIO(b"PDF"), "application/pdf"))],
                headers={"X-Api-Key": key},
            )
            assert r.status_code == 200, r.text
        resp = await client.post(
            f"/extract/{api_code}",
            files=[("file", ("a.pdf", io.BytesIO(b"PDF"), "application/pdf"))],
            headers={"X-Api-Key": key},
        )
        assert resp.status_code == 429
        assert resp.json()["error_code"] == "RATE_LIMITED"
    finally:
        rl_module.limiter.reset()
