from typing import Any

import pytest

from app.engines.fundamental_engine import (
    BANKRUPTCY_RISK,
    DILUTION_RISK,
    FUNDAMENTAL_VETO_SCORE,
    FundamentalInputs,
    compute_quality_bias,
    evaluate_fundamentals,
    is_vetoed,
    shares_outstanding_trend,
)

# A healthy, growing, low-leverage, cash-generative profile.
_HEALTHY: dict[str, Any] = dict(
    ticker="NVDA",
    revenue_ttm=1.15e11,
    revenue_prior_ttm=9.0e10,
    earnings_ttm=5.6e10,
    earnings_prior_ttm=4.0e10,
    operating_cashflow_ttm=6.4e10,
    free_cashflow_ttm=5.0e10,
    total_debt=1.0e10,
    total_equity=7.0e10,
    debt_to_equity=0.21,
    current_ratio=3.5,
    net_margin=0.48,
    return_on_equity=0.60,
    shares_outstanding=2.46e9,
    shares_outstanding_prior=2.50e9,
)

# A distressed, shrinking, over-levered, cash-burning profile.
_DISTRESSED: dict[str, Any] = dict(
    ticker="XYZ",
    revenue_ttm=8.0e8,
    revenue_prior_ttm=1.0e9,
    earnings_ttm=-1.5e8,
    earnings_prior_ttm=-5.0e7,
    operating_cashflow_ttm=-5.0e7,
    free_cashflow_ttm=-1.0e8,
    total_debt=9.0e8,
    total_equity=1.0e8,
    debt_to_equity=3.0,
    current_ratio=0.8,
    net_margin=-0.19,
    return_on_equity=-1.5,
    shares_outstanding=2.2e8,
    shares_outstanding_prior=2.0e8,
)


def _inputs(**overrides: Any) -> FundamentalInputs:
    return FundamentalInputs(**{**_HEALTHY, **overrides})


def test_score_and_subscores_in_range() -> None:
    result = evaluate_fundamentals(_inputs())
    assert 0.0 <= result.fundamental_score <= 100.0
    for value in result.quality_subscores.model_dump().values():
        assert 0.0 <= value <= 100.0


def test_healthy_scores_higher_than_distressed() -> None:
    healthy = evaluate_fundamentals(_inputs())
    distressed = evaluate_fundamentals(FundamentalInputs(**_DISTRESSED))
    assert healthy.fundamental_score > distressed.fundamental_score
    assert healthy.fundamental_score > 80.0
    assert distressed.fundamental_score < FUNDAMENTAL_VETO_SCORE


def test_profitability_is_monotonic_in_margin() -> None:
    low = evaluate_fundamentals(_inputs(net_margin=0.02, return_on_equity=0.05))
    high = evaluate_fundamentals(_inputs(net_margin=0.30, return_on_equity=0.40))
    assert high.quality_subscores.profitability_score > low.quality_subscores.profitability_score


def test_leverage_is_monotonic_in_debt() -> None:
    low_debt = evaluate_fundamentals(_inputs(debt_to_equity=0.1))
    high_debt = evaluate_fundamentals(_inputs(debt_to_equity=2.0))
    assert low_debt.quality_subscores.leverage_score > high_debt.quality_subscores.leverage_score


def test_growth_is_monotonic() -> None:
    shrinking = evaluate_fundamentals(
        _inputs(revenue_ttm=8.0e10, earnings_ttm=3.0e10)  # below prior periods
    )
    growing = evaluate_fundamentals(_inputs())
    assert growing.quality_subscores.growth_score > shrinking.quality_subscores.growth_score


def test_dilution_risk_flag() -> None:
    diluting = evaluate_fundamentals(
        _inputs(shares_outstanding=2.8e9, shares_outstanding_prior=2.5e9)
    )
    assert DILUTION_RISK in diluting.risk_flags
    assert BANKRUPTCY_RISK not in diluting.risk_flags


def test_bankruptcy_risk_flag_on_negative_equity() -> None:
    insolvent = evaluate_fundamentals(_inputs(total_equity=-1.0e9))
    assert BANKRUPTCY_RISK in insolvent.risk_flags


def test_distressed_triggers_both_flags() -> None:
    result = evaluate_fundamentals(FundamentalInputs(**_DISTRESSED))
    assert BANKRUPTCY_RISK in result.risk_flags
    assert DILUTION_RISK in result.risk_flags


@pytest.mark.parametrize(
    "score,expected",
    [(0.0, 0.9), (50.0, 1.0), (100.0, 1.1)],
)
def test_quality_bias_bounds(score: float, expected: float) -> None:
    assert compute_quality_bias(score) == pytest.approx(expected)
    assert 0.9 <= compute_quality_bias(score) <= 1.1


def test_veto_on_bankruptcy_or_low_score() -> None:
    distressed = evaluate_fundamentals(FundamentalInputs(**_DISTRESSED))
    assert is_vetoed(distressed) is True
    healthy = evaluate_fundamentals(_inputs())
    assert is_vetoed(healthy) is False


def test_shares_outstanding_trend() -> None:
    # Within +/-5% counts as stable (NVDA's mild buyback is only -1.6%).
    assert shares_outstanding_trend(_inputs()) == "stable"
    assert (
        shares_outstanding_trend(_inputs(shares_outstanding=2.2e9, shares_outstanding_prior=2.5e9))
        == "falling"
    )
    assert (
        shares_outstanding_trend(_inputs(shares_outstanding=2.8e9, shares_outstanding_prior=2.5e9))
        == "rising"
    )
