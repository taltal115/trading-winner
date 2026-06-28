"""OpenAI (GPT-5) reasoning provider — the production ``AIProvider`` adapter.

Concrete implementation of the LLM seam in ``ai_provider.py``. The AIService is
unchanged: it still gates the call, validates the response against the strict
``AIReasoningOutput`` schema, clamps the adjustment, and falls back to quant-only
on any failure. AI remains enrichment only and never an execution authority
(.cursor/rules.md 3.3).

Design (mirrors the Firestore adapter):
- The ``openai`` SDK is imported lazily so the package is only required when this
  backend is selected (dev/tests use the deterministic MockAIProvider).
- A client may be injected for testing; production constructs a real client.
- The model is asked for a strict JSON object; any SDK/parse error is surfaced as
  ``RuntimeError`` so the AIService's documented fallback path engages.
"""

from __future__ import annotations

import json
from typing import Any, cast

from app.models.ai import AIPromptContext

_SYSTEM_PROMPT = (
    "You are a quantitative equity analyst. Interpret the catalyst behind a "
    "stock's move. You do NOT decide trades; you only describe the catalyst and "
    "a bounded bias. Respond with a SINGLE JSON object and nothing else, with "
    "exactly these keys: ticker (string), catalyst_type (one of earnings|news|"
    "macro|insider|unknown), catalyst_direction (one of bullish|neutral|"
    "bearish), ai_bias (number in [-1,1]), sentiment (one of positive|neutral|"
    "negative), summary (string), key_insights (array of strings), risk_factors "
    "(array of strings), confidence (number in [0,1]), confidence_adjustment "
    "(number in [-1,1])."
)


class OpenAIProvider:
    """Adapts the OpenAI Chat Completions API to the ``AIProvider`` protocol."""

    prompt_version = "1.0"

    def __init__(
        self,
        model: str = "gpt-5",
        api_key: str | None = None,
        client: Any = None,
    ) -> None:
        self._model = model
        self.reasoning_version = f"{model}-v1"
        if client is not None:
            self._client = client
            return
        try:
            from openai import OpenAI
        except ImportError as exc:  # pragma: no cover - exercised only without the SDK
            raise RuntimeError(
                "ai_provider_backend='openai' requires the openai package. "
                "Install it with: pip install '.[openai]'"
            ) from exc
        self._client = OpenAI(api_key=api_key) if api_key else OpenAI()

    def analyze(self, context: AIPromptContext) -> dict[str, object]:
        try:
            response = self._client.chat.completions.create(
                model=self._model,
                temperature=0,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": _SYSTEM_PROMPT},
                    {"role": "user", "content": self._render_context(context)},
                ],
            )
            content = response.choices[0].message.content
        except Exception as exc:  # normalize SDK errors -> service fallback path
            raise RuntimeError(f"OpenAI request failed: {exc}") from exc

        if not content:
            raise RuntimeError("OpenAI returned an empty response")
        return cast("dict[str, object]", json.loads(content))

    @staticmethod
    def _render_context(context: AIPromptContext) -> str:
        payload = {
            "ticker": context.ticker,
            "catalyst_type": context.catalyst_type.value,
            "price_change": context.price_change,
            "volume_spike": context.volume_spike,
            "sector_trend": context.sector_trend,
            "feature_summary": context.feature_summary,
            "news": [
                {"headline": n.headline, "source": n.source, "sentiment": n.sentiment.value}
                for n in context.news
            ],
            "retrieved_context": context.retrieved_context,
        }
        return json.dumps(payload)
