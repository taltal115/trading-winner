import pytest

from app.config.settings import RiskLimits
from app.engines.risk_engine import (
    RiskInputs,
    assess_risk,
    compute_confidence_multiplier,
)
from app.models.enums import TradeSide

LIMITS = RiskLimits()


def _inputs(**overrides: object) -> RiskInputs:
    base: dict[str, object] = dict(
        ticker="NVDA",
        sector="Technology",
        side=TradeSide.LONG,
        entry_price=100.0,
        atr=2.0,
        score=70.0,
        account_equity=100_000.0,
        cash=100_000.0,
        open_positions_count=0,
        sector_exposure=0.0,
        holding_ticker=False,
    )
    base.update(overrides)
    return RiskInputs(**base)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "score,expected",
    [(0, 0.5), (70, 1.2), (100, 1.5), (200, 1.5)],
)
def test_confidence_multiplier_bounds(score: float, expected: float) -> None:
    assert compute_confidence_multiplier(score) == pytest.approx(expected)


def test_position_sizing_and_single_position_cap() -> None:
    result = assess_risk(_inputs(), LIMITS)
    assert result.approved
    assert result.confidence_multiplier == pytest.approx(1.2)
    assert result.stop_distance == pytest.approx(4.0)  # min(2*ATR=4, 5% of 100=5)
    assert result.stop_price == pytest.approx(96.0)
    # raw size 300 shares (notional 30k) capped to 10% equity -> 100 shares.
    assert result.quantity == 100
    assert result.notional == pytest.approx(10_000.0)


def test_duplicate_position_rejected_even_with_max_score() -> None:
    result = assess_risk(_inputs(score=100, holding_ticker=True), LIMITS)
    assert not result.approved
    assert any("duplicate" in r for r in result.rejection_reasons)


def test_max_open_positions_rejected() -> None:
    result = assess_risk(_inputs(open_positions_count=15), LIMITS)
    assert not result.approved
    assert any("max open positions" in r for r in result.rejection_reasons)


def test_sector_exposure_rejected() -> None:
    result = assess_risk(_inputs(sector_exposure=20_000.0), LIMITS)
    assert not result.approved
    assert any("sector exposure" in r for r in result.rejection_reasons)


def test_cash_buffer_rejected() -> None:
    result = assess_risk(_inputs(cash=15_000.0), LIMITS)
    assert not result.approved
    assert any("cash buffer" in r for r in result.rejection_reasons)


def test_pdt_round_trip_limit_rejected() -> None:
    result = assess_risk(_inputs(intraday_round_trips_this_week=3), LIMITS)
    assert not result.approved
    assert any("PDT" in r for r in result.rejection_reasons)
