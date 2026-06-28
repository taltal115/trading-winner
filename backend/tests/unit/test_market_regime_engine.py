from typing import Any

from app.engines.market_regime_engine import (
    MAX_RISK_MULTIPLIER,
    MIN_RISK_MULTIPLIER,
    MarketRegimeInputs,
    classify_regime,
    evaluate_regime,
)
from app.models.enums import ExposureRecommendation, RegimeState

# Calm, neutral baseline (matches the deterministic mock macro source).
_NEUTRAL: dict[str, Any] = dict(
    spy_trend=0.004,
    vix=15.0,
    sector_breadth=0.50,
    market_momentum=0.0,
    cross_stock_correlation=0.42,
)


def _inputs(**overrides: Any) -> MarketRegimeInputs:
    return MarketRegimeInputs(**{**_NEUTRAL, **overrides})


def test_neutral_baseline() -> None:
    result = evaluate_regime(_inputs())
    assert result.regime_state is RegimeState.NEUTRAL
    assert result.risk_multiplier == 1.0
    assert result.exposure_recommendation is ExposureRecommendation.MEDIUM


def test_bullish_regime() -> None:
    result = evaluate_regime(_inputs(spy_trend=0.03, market_momentum=0.05, sector_breadth=0.7))
    assert result.regime_state is RegimeState.BULLISH
    assert result.risk_multiplier > 1.0
    assert result.exposure_recommendation is ExposureRecommendation.HIGH


def test_bearish_regime() -> None:
    result = evaluate_regime(_inputs(spy_trend=-0.03, market_momentum=-0.05, sector_breadth=0.35))
    assert result.regime_state is RegimeState.BEARISH
    assert result.risk_multiplier <= 1.0
    assert result.exposure_recommendation is ExposureRecommendation.LOW


def test_high_volatility_on_vix_spike() -> None:
    result = evaluate_regime(_inputs(vix=35.0))
    assert result.regime_state is RegimeState.HIGH_VOLATILITY
    assert result.risk_multiplier <= 0.75
    assert result.exposure_recommendation is ExposureRecommendation.LOW


def test_high_volatility_on_crowded_correlation() -> None:
    assert classify_regime(_inputs(cross_stock_correlation=0.85)) is RegimeState.HIGH_VOLATILITY


def test_multiplier_is_clamped() -> None:
    # Extreme stress can only drive the multiplier to its floor, never below.
    floor = evaluate_regime(_inputs(vix=80.0, cross_stock_correlation=0.99, sector_breadth=0.0))
    assert floor.risk_multiplier == MIN_RISK_MULTIPLIER
    # Extreme tailwinds can only drive it to its ceiling, never above.
    ceiling = evaluate_regime(
        _inputs(spy_trend=0.2, market_momentum=1.0, sector_breadth=1.0, vix=10.0)
    )
    assert ceiling.risk_multiplier == MAX_RISK_MULTIPLIER


def test_risk_multiplier_monotonic_in_vix() -> None:
    calm = evaluate_regime(_inputs(vix=12.0)).risk_multiplier
    elevated = evaluate_regime(_inputs(vix=22.0)).risk_multiplier
    assert calm >= elevated
