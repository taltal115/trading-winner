"""Scoring engine (TRADING_ENGINE.md sections 4 & 6).

Deterministic, pure scoring. AI may later supply a bounded confidence
adjustment, but it can never approve a trade; the decision thresholds here are
the authority. Phase 1 runs with ``ai_confidence_adjustment = 0``.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from app.models.entities import FeatureSnapshot, ScoreBreakdown
from app.models.enums import SignalDecision

# FinalScore component weights (must sum to 1.0).
WEIGHT_MOMENTUM = 0.30
WEIGHT_VOLUME = 0.20
WEIGHT_CATALYST = 0.20
WEIGHT_SECTOR = 0.15
WEIGHT_VOLATILITY = 0.10
WEIGHT_MACRO = 0.05

STRONG_BUY_THRESHOLD = 85.0
BUY_THRESHOLD = 70.0
WATCH_THRESHOLD = 50.0

_NEUTRAL = 50.0
_MAX_EXPECTED_RETURN = 0.08


class ScoreResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    breakdown: ScoreBreakdown
    final_score: float
    quality_biased_score: float
    adjusted_score: float
    decision: SignalDecision
    expected_return: float
    risk_score: float


def _clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, value))


def compute_momentum_score(features: FeatureSnapshot) -> float:
    """Blend recent return strength with moving-average trend alignment."""
    return_component = _clamp(_NEUTRAL + features.momentum.weekly_return * 500)
    trend_component = (50.0 if features.technical.sma_20 > features.technical.sma_50 else 0.0) + (
        50.0 if features.technical.sma_50 > features.technical.sma_200 else 0.0
    )
    return _clamp(0.6 * return_component + 0.4 * trend_component)


def compute_volume_score(features: FeatureSnapshot) -> float:
    return _clamp(features.volume.relative_volume / 3.0 * 100.0)


def compute_volatility_breakout_score(features: FeatureSnapshot) -> float:
    return _clamp(features.volatility.bollinger_width / 0.2 * 100.0)


def decide(score: float) -> SignalDecision:
    if score >= STRONG_BUY_THRESHOLD:
        return SignalDecision.STRONG_BUY
    if score >= BUY_THRESHOLD:
        return SignalDecision.BUY
    if score >= WATCH_THRESHOLD:
        return SignalDecision.WATCH
    return SignalDecision.IGNORE


def score_features(
    features: FeatureSnapshot,
    *,
    catalyst_score: float = 0.0,
    sector_strength: float = _NEUTRAL,
    macro_alignment: float = _NEUTRAL,
    ai_confidence_adjustment: float = 0.0,
    quality_bias: float = 1.0,
    fundamental_veto: bool = False,
) -> ScoreResult:
    """Produce the full deterministic score result for a feature snapshot.

    ``quality_bias`` (default 1.0) is the bounded Fundamental quality bias
    (TRADING_ENGINE.md 4.4 / 6.1), applied to FinalScore BEFORE the AI
    adjustment. ``fundamental_veto`` (default False) is the hard fundamental
    filter that forces IGNORE. Both default to no-ops so the base scoring is
    byte-for-byte unchanged when the Fundamental Engine is disabled.
    """
    breakdown = ScoreBreakdown(
        momentum_score=compute_momentum_score(features),
        volume_score=compute_volume_score(features),
        catalyst_score=_clamp(catalyst_score),
        sector_strength=_clamp(sector_strength),
        volatility_breakout=compute_volatility_breakout_score(features),
        macro_alignment=_clamp(macro_alignment),
    )
    final_score = (
        WEIGHT_MOMENTUM * breakdown.momentum_score
        + WEIGHT_VOLUME * breakdown.volume_score
        + WEIGHT_CATALYST * breakdown.catalyst_score
        + WEIGHT_SECTOR * breakdown.sector_strength
        + WEIGHT_VOLATILITY * breakdown.volatility_breakout
        + WEIGHT_MACRO * breakdown.macro_alignment
    )
    quality_biased_score = final_score * quality_bias
    adjusted_score = _clamp(quality_biased_score * (1.0 + ai_confidence_adjustment))
    expected_return = round(adjusted_score / 100.0 * _MAX_EXPECTED_RETURN, 4)
    risk_score = min(1.0, features.volatility.std_dev * 10.0)
    decision = SignalDecision.IGNORE if fundamental_veto else decide(adjusted_score)

    return ScoreResult(
        breakdown=breakdown,
        final_score=round(final_score, 4),
        quality_biased_score=round(quality_biased_score, 4),
        adjusted_score=round(adjusted_score, 4),
        decision=decision,
        expected_return=expected_return,
        risk_score=round(risk_score, 4),
    )
