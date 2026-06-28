from datetime import date, datetime, timedelta

import pytest

from app.engines.backtest_engine import run_backtest
from app.engines.feature_engine import compute_features
from app.engines.scoring_engine import score_features
from app.models.entities import PriceBar


def _series(ticker: str, n: int, start: float, growth: float) -> list[PriceBar]:
    base = datetime(2025, 1, 1, 16, 0, 0)
    bars: list[PriceBar] = []
    for i in range(n):
        close = max(1.0, start * (1.0 + growth) ** i)
        band = close * 0.01
        bars.append(
            PriceBar(
                ticker=ticker,
                timestamp=base + timedelta(days=i),
                open=close - band,
                high=close + band,
                low=close - band,
                close=close,
                volume=1_500_000,
            )
        )
    return bars


def _index_for_date(bars: list[PriceBar], day: date) -> int:
    for i, bar in enumerate(bars):
        if bar.timestamp.date() == day:
            return i
    raise AssertionError(f"no bar for {day}")


def test_uptrend_produces_winning_trades() -> None:
    bars = _series("UP", 320, 100.0, 0.01)
    result = run_backtest("UP", bars)
    assert len(result.trades) >= 1
    assert all(t.return_pct > 0 for t in result.trades)


def test_downtrend_produces_no_trades() -> None:
    bars = _series("DN", 320, 300.0, -0.01)
    result = run_backtest("DN", bars)
    assert result.trades == []


def test_backtest_entry_score_matches_live_scoring() -> None:
    """The backtest must score identically to the live feature+scoring engines."""
    bars = _series("UP", 320, 100.0, 0.01)
    result = run_backtest("UP", bars)
    assert result.trades

    trade = result.trades[0]
    entry_index = _index_for_date(bars, trade.entry_date)
    window = bars[: entry_index + 1]
    features = compute_features("UP", window)
    live_score = score_features(features)

    assert trade.entry_score == pytest.approx(live_score.adjusted_score)
    assert live_score.decision.value != "IGNORE"


def test_daily_returns_align_with_trade_returns() -> None:
    bars = _series("UP", 320, 100.0, 0.01)
    result = run_backtest("UP", bars)
    # Every bar gets a daily return entry (flat days contribute 0.0).
    assert len(result.daily_returns) == len(bars)
