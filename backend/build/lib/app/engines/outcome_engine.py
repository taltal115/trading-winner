"""Pure outcome metrics for the learning loop (PROJECT.md section 10).

Given a closed trade and its traceability references, computes deterministic
attribution fields (return %, hold duration, win/loss) used to build the
``outcomes/`` training record. No I/O — the service layer gathers inputs and
persists the result.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class OutcomeInputs:
    """Everything needed to materialize one learning-loop outcome record."""

    trade_id: str
    ticker: str
    signal_id: str
    feature_snapshot_id: str
    ai_analysis_id: str | None
    risk_decision_id: str | None
    fundamental_id: str | None
    market_regime_id: str | None
    entry_time: datetime
    exit_time: datetime
    entry_price: float
    exit_price: float
    quantity: float
    realized_pnl: float
    fees: float
    exit_reason: str
    entry_score: float
    ai_bias: float | None
    ai_confidence_adjustment: float | None


@dataclass(frozen=True)
class OutcomeMetrics:
    return_pct: float
    hold_days: int
    is_winner: bool


def compute_outcome_metrics(
    *,
    entry_price: float,
    exit_price: float,
    entry_time: datetime,
    exit_time: datetime,
    realized_pnl: float,
) -> OutcomeMetrics:
    """Deterministic outcome labels for the learning dataset."""
    if entry_price <= 0:
        raise ValueError(f"entry_price must be positive, got {entry_price}")
    return_pct = round((exit_price - entry_price) / entry_price, 6)
    hold_days = max(0, (exit_time - entry_time).days)
    return OutcomeMetrics(
        return_pct=return_pct,
        hold_days=hold_days,
        is_winner=realized_pnl > 0,
    )
