import io

import pytest


@pytest.mark.asyncio
async def test_rate_limit_returns_429(client, db_session, app, tmp_path, monkeypatch):
    import app.services.ratelimit as rl_module
    from tests.test_public_extract import _setup_published_project

    api_code, key = await _setup_published_project(client, db_session, monkeypatch, tmp_path)

    # Tighten the limit to 2/minute via monkeypatch (callable reads this at request time).
    monkeypatch.setattr(rl_module, "EXTRACT_RATE_LIMIT", "2/minute")

    from app.engine.providers import get_provider_dep
    from app.engine.providers.fake import FakeProvider

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
