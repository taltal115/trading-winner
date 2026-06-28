"""Market Regime Engine (ARCHITECTURE.md 3.2.2, TRADING_ENGINE.md 4.6/7.1).

Pure and deterministic: no I/O, no storage. Detects the macro market
environment once per cycle (market-wide, not per-ticker) and emits a
deterministic risk appetite. It can REDUCE activity (throttle sizing/exposure)
but NEVER places trades and NEVER overrides the Risk Engine. The
``risk_multiplier`` and ``exposure_recommendation`` are applied downstream,
deterministically and AFTER AI; AI can never override them.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import ExposureRecommendation, RegimeState

# risk_multiplier hard bounds (TRADING_ENGINE.md 4.6).
MIN_RISK_MULTIPLIER = 0.5
MAX_RISK_MULTIPLIER = 1.5

# VIX above this signals a high-volatility (stress) regime.
_VIX_HIGH = 28.0
# VIX level at/below which there is no volatility penalty.
_VIX_CALM = 15.0
# Cross-stock correlation above this signals crowded/stressed conditions.
_CORRELATION_STRESS = 0.8

# Sector breadth band separating bullish / bearish participation.
_BREADTH_BULLISH = 0.55
_BREADTH_BEARISH = 0.45


class MarketRegimeInputs(BaseModel):
    """Macro inputs for the regime computation (from the macro data seam)."""

    model_config = ConfigDict(extra="forbid")

    spy_trend: float  # SPY trend, return-like (positive = uptrend)
    vix: float  # volatility index level
    sector_breadth: float = Field(ge=0.0, le=1.0)  # fraction of sectors advancing
    market_momentum: float  # broad-market momentum, return-like
    cross_stock_correlation: float = Field(ge=0.0, le=1.0)


class MarketRegimeResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    regime_state: RegimeState
    risk_multiplier: float = Field(ge=MIN_RISK_MULTIPLIER, le=MAX_RISK_MULTIPLIER)
    exposure_recommendation: ExposureRecommendation


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def classify_regime(inputs: MarketRegimeInputs) -> RegimeState:
    """Deterministic regime classification.

    High volatility (VIX spike or crowded correlation) dominates; otherwise the
    SPY trend, breadth and momentum decide bullish / bearish / neutral.
    """
    if inputs.vix >= _VIX_HIGH or inputs.cross_stock_correlation >= _CORRELATION_STRESS:
        return RegimeState.HIGH_VOLATILITY
    if (
        inputs.spy_trend > 0.0
        and inputs.market_momentum > 0.0
        and inputs.sector_breadth >= _BREADTH_BULLISH
    ):
        return RegimeState.BULLISH
    if inputs.spy_trend < 0.0 and (
        inputs.market_momentum < 0.0 or inputs.sector_breadth < _BREADTH_BEARISH
    ):
        return RegimeState.BEARISH
    return RegimeState.NEUTRAL


def compute_risk_multiplier(inputs: MarketRegimeInputs, regime: RegimeState) -> float:
    """Continuous, deterministic risk multiplier clamped to [0.5, 1.5].

    Built additively from breadth and momentum (constructive) minus volatility
    and correlation penalties, then capped per regime so a defensive regime can
    only reduce risk, never expand it.
    """
    breadth_adjustment = (inputs.sector_breadth - 0.5) * 0.6
    momentum_adjustment = _clamp(inputs.market_momentum * 2.0, -0.3, 0.3)
    vix_penalty = max(0.0, (inputs.vix - _VIX_CALM) / 40.0)
    correlation_penalty = max(0.0, inputs.cross_stock_correlation - 0.5) * 0.4

    raw = 1.0 + breadth_adjustment + momentum_adjustment - vix_penalty - correlation_penalty

    if regime is RegimeState.HIGH_VOLATILITY:
        raw = min(raw, 0.75)
    elif regime is RegimeState.BEARISH:
        raw = min(raw, 1.0)

    return round(_clamp(raw, MIN_RISK_MULTIPLIER, MAX_RISK_MULTIPLIER), 4)


def recommend_exposure(regime: RegimeState, risk_multiplier: float) -> ExposureRecommendation:
    """Map regime + multiplier to a deterministic activity cap."""
    if regime in (RegimeState.HIGH_VOLATILITY, RegimeState.BEARISH) or risk_multiplier < 0.8:
        return ExposureRecommendation.LOW
    if regime is RegimeState.BULLISH and risk_multiplier >= 1.2:
        return ExposureRecommendation.HIGH
    return ExposureRecommendation.MEDIUM


def evaluate_regime(inputs: MarketRegimeInputs) -> MarketRegimeResult:
    """Produce the full deterministic market-regime result."""
    regime = classify_regime(inputs)
    risk_multiplier = compute_risk_multiplier(inputs, regime)
    return MarketRegimeResult(
        regime_state=regime,
        risk_multiplier=risk_multiplier,
        exposure_recommendation=recommend_exposure(regime, risk_multiplier),
    )
