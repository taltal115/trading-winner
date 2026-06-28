"""Pure performance-metric math for backtests.

Operates on a series of period (daily) returns. No I/O, deterministic.
"""

from __future__ import annotations

from math import sqrt
from statistics import fmean, pstdev

TRADING_DAYS_PER_YEAR = 252


def equity_curve(returns: list[float], starting_equity: float = 1.0) -> list[float]:
    """Cumulative equity from a series of period returns."""
    curve: list[float] = []
    value = starting_equity
    for r in returns:
        value *= 1.0 + r
        curve.append(value)
    return curve


def total_return(returns: list[float]) -> float:
    value = 1.0
    for r in returns:
        value *= 1.0 + r
    return value - 1.0


def max_drawdown(returns: list[float]) -> float:
    """Largest peak-to-trough decline as a positive fraction (0.18 == 18%)."""
    curve = equity_curve(returns)
    peak = float("-inf")
    worst = 0.0
    for value in curve:
        peak = max(peak, value)
        if peak > 0:
            drawdown = (value - peak) / peak
            worst = min(worst, drawdown)
    return abs(worst)


def sharpe_ratio(returns: list[float], periods_per_year: int = TRADING_DAYS_PER_YEAR) -> float:
    """Annualized Sharpe (risk-free rate assumed 0). Returns 0 when undefined."""
    if len(returns) < 2:
        return 0.0
    std = pstdev(returns)
    if std == 0:
        return 0.0
    return fmean(returns) / std * sqrt(periods_per_year)
