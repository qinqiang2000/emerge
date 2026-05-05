"""Unit tests for GeminiJudgeProvider — assert request shape and response
parsing without hitting the network. The live network path is exercised by
the walking-skeleton E2E.
"""
from __future__ import annotations

import pytest

from app.engine.providers.gemini_judge_provider import GeminiJudgeProvider


class _FakeResponse:
    def __init__(self, text: str | None):
        self.text = text


class _FakeModels:
    def __init__(self, response_text: str | None):
        self._response_text = response_text
        self.calls: list[dict] = []

    async def generate_content(self, *, model, contents, config):
        # Capture the call so tests can assert request shape.
        self.calls.append({"model": model, "contents": contents, "config": config})
        return _FakeResponse(self._response_text)


class _FakeAio:
    def __init__(self, response_text: str | None):
        self.models = _FakeModels(response_text)


class _FakeClient:
    def __init__(self, response_text: str | None):
        self.aio = _FakeAio(response_text)


class _FakeSettings:
    """Minimal stand-in for app.settings.settings — the prod Settings model
    instantiates a network-touching provider client at import time, which
    we don't want in unit tests."""

    def __init__(self, *, provider: str):
        self.default_provider = provider
        self.default_model_pro = "test-pro"
        self.google_api_key = "test-key"


@pytest.mark.asyncio
async def test_judge_parses_well_formed_response_into_verdict_map():
    body = '{"0": {"shop_name": "up", "total": "down"}, "1": {"shop_name": "uncertain"}}'
    client = _FakeClient(body)
    provider = GeminiJudgeProvider(model_id="test-model", client=client)

    out = await provider.judge(
        system="SYSTEM_FRAME",
        predicted_output=[{"shop_name": "X"}],
        file_bytes=b"%PDF-1.4 fake",
        mime_type="application/pdf",
    )
    assert out == {
        "0": {"shop_name": "up", "total": "down"},
        "1": {"shop_name": "uncertain"},
    }


@pytest.mark.asyncio
async def test_judge_passes_system_to_system_instruction_not_user_content():
    """The protocol contract is that `system` carries the full prompt
    (system frame + schema + predicted_output). The provider must route it
    through Gemini's system_instruction, NOT a user-text part — otherwise
    the model treats the schema/predicted-output as conversation and the
    verdict structure drifts.
    """
    client = _FakeClient('{"0": {"a": "up"}}')
    provider = GeminiJudgeProvider(model_id="test-model", client=client)

    await provider.judge(
        system="THE_SYSTEM",
        predicted_output=[{"a": 1}],
        file_bytes=b"%PDF-1.4",
        mime_type="application/pdf",
    )
    call = client.aio.models.calls[0]
    assert call["model"] == "test-model"
    # system_instruction wired
    assert call["config"].system_instruction == "THE_SYSTEM"
    # response_mime_type pinned to JSON so we can json.loads downstream
    assert call["config"].response_mime_type == "application/json"
    # User content is the PDF only — no Part.from_text inside the contents
    user_parts = call["contents"][0].parts
    assert len(user_parts) == 1
    # The text-routing red line: no Part should carry the system text
    for part in user_parts:
        text_field = getattr(part, "text", None)
        assert text_field is None or text_field == ""


@pytest.mark.asyncio
async def test_judge_returns_empty_dict_on_invalid_json():
    client = _FakeClient("not json at all")
    provider = GeminiJudgeProvider(model_id="test-model", client=client)
    out = await provider.judge(
        system="x",
        predicted_output=[],
        file_bytes=b"x",
        mime_type="application/pdf",
    )
    assert out == {}


@pytest.mark.asyncio
async def test_judge_returns_empty_dict_on_none_response_text():
    """Gemini occasionally returns a response with text=None when the
    underlying model refused or returned empty. Must not crash run_judge.
    """
    client = _FakeClient(None)
    provider = GeminiJudgeProvider(model_id="test-model", client=client)
    out = await provider.judge(
        system="x",
        predicted_output=[],
        file_bytes=b"x",
        mime_type="application/pdf",
    )
    assert out == {}


@pytest.mark.asyncio
async def test_judge_drops_invalid_verdict_literals_and_wrong_shapes():
    """Defensive shape-check: a leaky model may return non-string verdicts,
    unknown literals, or non-dict per-entity values. All such entries must
    be dropped so JudgeCalibration downstream stays consistent.
    """
    body = (
        '{"0": {"a": "up", "b": "maybe", "c": 42},'
        ' "1": "not a dict",'
        ' "2": {"a": "uncertain"}}'
    )
    client = _FakeClient(body)
    provider = GeminiJudgeProvider(model_id="test-model", client=client)
    out = await provider.judge(
        system="x",
        predicted_output=[],
        file_bytes=b"x",
        mime_type="application/pdf",
    )
    # "0": only "a" survives ("maybe" not in literal set; 42 not a string)
    # "1": dropped entirely (not a dict)
    # "2": survives with {"a": "uncertain"}
    assert out == {"0": {"a": "up"}, "2": {"a": "uncertain"}}


@pytest.mark.asyncio
async def test_judge_returns_empty_dict_when_response_is_a_list_not_object():
    """Schema contract is `{"<entity_idx>": {"<field>": "verdict"}}`. A list
    at the top level violates the contract; reject defensively rather than
    coerce.
    """
    client = _FakeClient('[{"0": {"a": "up"}}]')
    provider = GeminiJudgeProvider(model_id="test-model", client=client)
    out = await provider.judge(
        system="x",
        predicted_output=[],
        file_bytes=b"x",
        mime_type="application/pdf",
    )
    assert out == {}


def test_get_judge_provider_returns_gemini_when_configured(monkeypatch):
    """get_judge_provider used to raise NotImplementedError unconditionally.
    R6 wiring (this commit) routes to GeminiJudgeProvider when
    settings.default_provider == "gemini". Pin the route so a future
    settings refactor doesn't silently revert.
    """
    from app.engine.judge import get_judge_provider

    monkeypatch.setattr("app.settings.settings", _FakeSettings(provider="gemini"))
    provider = get_judge_provider()
    assert isinstance(provider, GeminiJudgeProvider)


def test_get_judge_provider_raises_for_unsupported_provider(monkeypatch):
    """Until OpenAIJudgeProvider lands, default_provider="openai" must still
    raise — but with a more helpful message than the original
    NotImplementedError stub. Tests are encouraged to use
    dependency_overrides as the existing test_score_routes.py does.
    """
    from app.engine.judge import get_judge_provider

    monkeypatch.setattr("app.settings.settings", _FakeSettings(provider="openai"))
    with pytest.raises(NotImplementedError, match="default_provider='openai'"):
        get_judge_provider()
