"""Tests for the OpenAI provider adapter.

A fake client mimics the ``openai`` Chat Completions surface
(client.chat.completions.create -> .choices[0].message.content) so we can verify
the adapter renders context, parses strict JSON, validates end-to-end through the
AIService, and surfaces failures as the documented quant-only fallback — all
without the SDK or any network call.
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from app.config.settings import Settings
from app.models.ai import AIPromptContext, NewsContext
from app.models.enums import CatalystType, Sentiment
from app.services.openai_provider import OpenAIProvider

_VALID_RESPONSE = {
    "ticker": "NVDA",
    "catalyst_type": "news",
    "catalyst_direction": "bullish",
    "ai_bias": 0.4,
    "sentiment": "positive",
    "summary": "AI chip demand catalyst",
    "key_insights": ["partnership announced"],
    "risk_factors": ["valuation"],
    "confidence": 0.7,
    "confidence_adjustment": 0.08,
}


class _FakeMessage:
    def __init__(self, content: str | None) -> None:
        self.content = content


class _FakeChoice:
    def __init__(self, content: str | None) -> None:
        self.message = _FakeMessage(content)


class _FakeResponse:
    def __init__(self, content: str | None) -> None:
        self.choices = [_FakeChoice(content)]


class _FakeCompletions:
    def __init__(self, content: str | None, raise_exc: Exception | None) -> None:
        self._content = content
        self._raise = raise_exc
        self.last_kwargs: dict[str, Any] = {}

    def create(self, **kwargs: Any) -> _FakeResponse:
        self.last_kwargs = kwargs
        if self._raise is not None:
            raise self._raise
        return _FakeResponse(self._content)


class _FakeChat:
    def __init__(self, completions: _FakeCompletions) -> None:
        self.completions = completions


class _FakeOpenAI:
    def __init__(self, content: str | None = None, raise_exc: Exception | None = None) -> None:
        self.chat = _FakeChat(_FakeCompletions(content, raise_exc))


def _context() -> AIPromptContext:
    return AIPromptContext(
        ticker="NVDA",
        news=[NewsContext(headline="AI chip deal", source="Wire", sentiment=Sentiment.POSITIVE)],
        price_change=0.03,
        volume_spike=2.4,
        sector_trend="up",
        feature_summary={"rsi": 61.0},
        catalyst_type=CatalystType.NEWS,
    )


def test_exposes_ai_provider_interface() -> None:
    provider = OpenAIProvider(client=_FakeOpenAI(json.dumps(_VALID_RESPONSE)))
    assert callable(provider.analyze)
    assert provider.reasoning_version.endswith("-v1")
    assert provider.prompt_version == "1.0"


def test_analyze_parses_json_response() -> None:
    provider = OpenAIProvider(client=_FakeOpenAI(json.dumps(_VALID_RESPONSE)))
    result = provider.analyze(_context())
    assert result["catalyst_direction"] == "bullish"
    assert result["ai_bias"] == 0.4


def test_response_validates_against_strict_schema() -> None:
    # The adapter's dict must satisfy the schema the AIService enforces.
    from app.models.ai import AIReasoningOutput

    provider = OpenAIProvider(client=_FakeOpenAI(json.dumps(_VALID_RESPONSE)))
    output = AIReasoningOutput.model_validate(provider.analyze(_context()))
    assert output.ticker == "NVDA"
    assert output.catalyst_direction.value == "bullish"


def test_analyze_requests_json_object_format() -> None:
    fake = _FakeOpenAI(json.dumps(_VALID_RESPONSE))
    OpenAIProvider(model="gpt-5", client=fake).analyze(_context())
    kwargs = fake.chat.completions.last_kwargs
    assert kwargs["model"] == "gpt-5"
    assert kwargs["response_format"] == {"type": "json_object"}
    assert kwargs["temperature"] == 0


def test_empty_response_raises_runtime_error() -> None:
    provider = OpenAIProvider(client=_FakeOpenAI(content=None))
    with pytest.raises(RuntimeError, match="empty"):
        provider.analyze(_context())


def test_sdk_error_is_normalized_to_runtime_error() -> None:
    provider = OpenAIProvider(client=_FakeOpenAI(raise_exc=ValueError("boom")))
    with pytest.raises(RuntimeError, match="OpenAI request failed"):
        provider.analyze(_context())


def test_missing_sdk_raises_helpful_error() -> None:
    with pytest.raises(RuntimeError, match="openai package"):
        OpenAIProvider()


def test_build_ai_provider_selects_backend() -> None:
    from app.api.dependencies import _build_ai_provider
    from app.services.ai_provider import MockAIProvider

    assert isinstance(_build_ai_provider(Settings(ai_provider_backend="mock")), MockAIProvider)
    with pytest.raises(RuntimeError, match="openai package"):
        _build_ai_provider(Settings(ai_provider_backend="openai"))
    with pytest.raises(NotImplementedError):
        _build_ai_provider(Settings(ai_provider_backend="anthropic"))
