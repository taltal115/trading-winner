"""AI provider abstraction (external LLM boundary).

This is the seam where the real GPT-5 client plugs in. Providers return a raw
JSON-like dict; the AIService is responsible for validating it against
``AIReasoningOutput``. Providers may raise on failure; the service handles
fallback (quant-only) per AI_PIPELINE.md section 12.
"""

from __future__ import annotations

from typing import Protocol

from app.models.ai import AIPromptContext
from app.models.enums import CatalystDirection, Sentiment


class AIProvider(Protocol):
    reasoning_version: str
    prompt_version: str

    def analyze(self, context: AIPromptContext) -> dict[str, object]: ...


class MockAIProvider:
    """Deterministic provider for dev/tests.

    Derives a structured response from the prompt context so the full pipeline
    runs offline without API cost or nondeterminism.
    """

    reasoning_version = "mock-v1"
    prompt_version = "1.0"

    def analyze(self, context: AIPromptContext) -> dict[str, object]:
        positives = sum(1 for n in context.news if n.sentiment == Sentiment.POSITIVE)
        negatives = sum(1 for n in context.news if n.sentiment == Sentiment.NEGATIVE)

        if positives > negatives:
            direction, sentiment, bias = CatalystDirection.BULLISH, Sentiment.POSITIVE, 0.3
        elif negatives > positives:
            direction, sentiment, bias = CatalystDirection.BEARISH, Sentiment.NEGATIVE, -0.3
        else:
            direction, sentiment, bias = CatalystDirection.NEUTRAL, Sentiment.NEUTRAL, 0.0

        summary = (
            f"{context.ticker}: {direction.value} catalyst " f"({context.catalyst_type.value})"
        )
        return {
            "ticker": context.ticker,
            "catalyst_type": context.catalyst_type.value,
            "catalyst_direction": direction.value,
            "ai_bias": bias,
            "sentiment": sentiment.value,
            "summary": summary,
            "key_insights": [n.headline for n in context.news[:3]],
            "risk_factors": ["macro_sensitivity"],
            "confidence": 0.6 + 0.1 * abs(bias) * 10 / 3,
            # Bounded nudge; clamped again by the service to the configured max.
            "confidence_adjustment": round(bias * 0.2, 4),
        }
