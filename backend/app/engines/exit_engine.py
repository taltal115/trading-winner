"""Shared exit logic (TRADING_ENGINE.md section 8).

Single source of truth for exits and stop sizing, reused by both the backtest
engine and live position management so historical and live behavior are
identical (no duplicated trading logic, .cursor/rules.md 3.2).
"""

from __future__ import annotations

from app.models.enums import ExitReason


def compute_stop_distance(
    entry_price: float,
    atr: float,
    atr_multiple: float = 2.0,
    max_stop_pct: float = 0.05,
) -> float:
    """Stop distance = the tighter of N*ATR or max_stop_pct*entry.

    Implements "−2 ATR or −5% (whichever smaller [loss])".
    """
    return min(atr_multiple * atr, max_stop_pct * entry_price)


def evaluate_exit(
    *,
    current_close: float,
    stop_price: float,
    target_price: float,
    sma_20: float,
    sma_50: float,
    holding_days: int,
    max_hold_days: int,
) -> ExitReason | None:
    """Return the triggered exit reason for an open long, or None to hold."""
    if current_close <= stop_price:
        return ExitReason.STOP_LOSS
    if current_close >= target_price:
        return ExitReason.PROFIT_TARGET
    if holding_days >= max_hold_days:
        return ExitReason.TIME
    if sma_20 < sma_50:
        return ExitReason.MOMENTUM_FAILURE
    return None
