from datetime import datetime

from app.config.settings import RiskLimits
from app.engines.risk_engine import RiskInputs, assess_risk
from app.models.entities import MarketRegimeSnapshot
from app.models.enums import ExposureRecommendation, RegimeState, TradeSide
from app.services.risk_service import RiskService

LIMITS = RiskLimits()


def _inputs(regime_risk_multiplier: float) -> RiskInputs:
    # A modest, below-cap trade so the regime multiplier visibly scales sizing.
    return RiskInputs(
        ticker="NVDA",
        sector="Technology",
        side=TradeSide.LONG,
        entry_price=200.0,
        atr=50.0,
        score=0.0,  # confidence_multiplier == 0.5
        account_equity=100_000.0,
        cash=100_000.0,
        open_positions_count=0,
        sector_exposure=0.0,
        holding_ticker=False,
        regime_risk_multiplier=regime_risk_multiplier,
    )


def test_default_multiplier_is_noop() -> None:
    assert _inputs(1.0).regime_risk_multiplier == 1.0
    assert (
        RiskInputs.model_validate(
            {
                "ticker": "NVDA",
                "sector": "Technology",
                "side": TradeSide.LONG,
                "entry_price": 200.0,
                "atr": 50.0,
                "score": 0.0,
                "account_equity": 100_000.0,
                "cash": 100_000.0,
                "open_positions_count": 0,
                "sector_exposure": 0.0,
                "holding_ticker": False,
            }
        ).regime_risk_multiplier
        == 1.0
    )


def test_regime_multiplier_scales_position_size() -> None:
    full = assess_risk(_inputs(1.0), LIMITS)
    throttled = assess_risk(_inputs(0.5), LIMITS)
    assert full.quantity == 50.0
    assert throttled.quantity == 25.0  # exactly halved by the 0.5 multiplier


def _regime(exposure: ExposureRecommendation, multiplier: float) -> MarketRegimeSnapshot:
    return MarketRegimeSnapshot(
        id="regime_2026-07-28",
        date=datetime(2026, 7, 28).date(),
        timestamp=datetime(2026, 7, 28, 16, 0, 0),
        regime_state=RegimeState.HIGH_VOLATILITY,
        risk_multiplier=multiplier,
        exposure_recommendation=exposure,
    )


def _service(ratio: float = 0.5) -> RiskService:
    # _effective_limits depends only on limits + ratio; collaborators are unused.
    return RiskService(None, None, None, None, LIMITS, ratio)  # type: ignore[arg-type]


def test_low_exposure_tightens_open_position_cap() -> None:
    service = _service(0.5)
    capped = service._effective_limits(_regime(ExposureRecommendation.LOW, 0.5))
    assert capped.max_open_positions == 7  # floor(15 * 0.5)


def test_non_low_exposure_keeps_limits_unchanged() -> None:
    service = _service()
    same = service._effective_limits(_regime(ExposureRecommendation.MEDIUM, 1.0))
    assert same.max_open_positions == LIMITS.max_open_positions


def test_no_regime_keeps_limits_unchanged() -> None:
    service = _service()
    assert service._effective_limits(None).max_open_positions == LIMITS.max_open_positions
