"""AI transport + validation schemas.

These are NOT Firestore entities. ``AIPromptContext`` is the structured input
handed to a provider; ``AIReasoningOutput`` is the strict schema every provider
response must validate against before it is allowed anywhere near a signal
(CODING_STANDARDS.md 8.2: never use free-text AI output in production logic).
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import CatalystDirection, CatalystType, Sentiment


class NewsContext(BaseModel):
    model_config = ConfigDict(extra="forbid")
    headline: str
    source: str
    sentiment: Sentiment


class AIPromptContext(BaseModel):
    """Structured input for the reasoning model (GPT-5 prompt template)."""

    model_config = ConfigDict(extra="forbid")

    ticker: str
    news: list[NewsContext]
    price_change: float
    volume_spike: float
    sector_trend: str
    feature_summary: dict[str, float]
    catalyst_type: CatalystType
    retrieved_context: list[str] = Field(default_factory=list)  # RAG seam (Phase 3b)
    # Read-only deterministic context from the new engines (AI_PIPELINE.md 4.5).
    # Provided for explanation only; AI must NOT override the fundamental hard
    # filter or the market regime constraints.
    fundamental_score: float | None = None
    regime_state: str | None = None


class AIReasoningOutput(BaseModel):
    """Strict schema for a single AI reasoning response.

    ``catalyst_direction`` and ``ai_bias`` are advisory only and carry no
    execution authority (.cursor/rules.md 3.3).
    """

    model_config = ConfigDict(extra="forbid")

    ticker: str
    catalyst_type: CatalystType
    catalyst_direction: CatalystDirection
    ai_bias: float = Field(ge=-1.0, le=1.0)
    sentiment: Sentiment
    summary: str
    key_insights: list[str] = Field(default_factory=list)
    risk_factors: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)
    confidence_adjustment: float = Field(ge=-1.0, le=1.0)
