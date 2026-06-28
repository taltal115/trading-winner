"""Risk engine (TRADING_ENGINE.md sections 7, 9, 11).

HARD RULE layer. Pure and deterministic. AI may have already adjusted the score
upstream, but the risk engine consumes only quantitative inputs and can never be
overridden by AI (.cursor/rules.md 3.3 / 6). All limits are enforced here.

Position sizing:
    quantity = floor((equity * risk_per_trade * confidence_multiplier) / stop_distance)
capped so notional <= max_single_position * equity.
"""

from __future__ import annotations

from math import floor

from pydantic import BaseModel, ConfigDict

from app.config.settings import RiskLimits
from app.engines.exit_engine import compute_stop_distance
from app.models.enums import TradeSide

_MIN_MULTIPLIER = 0.5
_MAX_MULTIPLIER = 1.5


class RiskInputs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ticker: str
    sector: str
    side: TradeSide
    entry_price: float
    atr: float
    score: float
    account_equity: float
    cash: float
    open_positions_count: int
    sector_exposure: float  # current notional already held in this sector
    holding_ticker: bool
    intraday_round_trips_this_week: int = 0


class RiskAssessment(BaseModel):
    model_config = ConfigDict(extra="forbid")

    approved: bool
    rejection_reasons: list[str]
    confidence_multiplier: float
    stop_distance: float
    stop_price: float
    quantity: float
    notional: float


def compute_confidence_multiplier(score: float) -> float:
    """Map a 0-100 score to the documented 0.5-1.5 sizing multiplier."""
    return max(_MIN_MULTIPLIER, min(_MAX_MULTIPLIER, _MIN_MULTIPLIER + score / 100.0))


def assess_risk(inputs: RiskInputs, limits: RiskLimits) -> RiskAssessment:
    multiplier = compute_confidence_multiplier(inputs.score)
    stop_distance = compute_stop_distance(inputs.entry_price, inputs.atr)
    stop_price = inputs.entry_price - stop_distance

    risk_capital = inputs.account_equity * limits.risk_per_trade * multiplier
    raw_quantity = floor(risk_capital / stop_distance) if stop_distance > 0 else 0

    # Cap to the single-position notional limit (hard resize, not a rejection).
    max_notional = limits.max_single_position * inputs.account_equity
    if raw_quantity * inputs.entry_price > max_notional:
        raw_quantity = floor(max_notional / inputs.entry_price)

    quantity = float(max(raw_quantity, 0))
    notional = quantity * inputs.entry_price

    reasons = _collect_rejections(inputs, limits, quantity, notional)
    return RiskAssessment(
        approved=not reasons,
        rejection_reasons=reasons,
        confidence_multiplier=round(multiplier, 4),
        stop_distance=round(stop_distance, 4),
        stop_price=round(stop_price, 4),
        quantity=quantity,
        notional=round(notional, 2),
    )


def _collect_rejections(
    inputs: RiskInputs,
    limits: RiskLimits,
    quantity: float,
    notional: float,
) -> list[str]:
    reasons: list[str] = []
    if quantity <= 0:
        reasons.append("position size rounds to zero")
    if inputs.holding_ticker:
        reasons.append("duplicate position already open")
    if inputs.open_positions_count >= limits.max_open_positions:
        reasons.append(f"max open positions reached ({limits.max_open_positions})")
    if inputs.sector_exposure + notional > limits.max_sector_exposure * inputs.account_equity:
        reasons.append(f"sector exposure exceeds {limits.max_sector_exposure:.0%}")
    if inputs.cash - notional < limits.cash_buffer_minimum * inputs.account_equity:
        reasons.append(f"violates cash buffer minimum {limits.cash_buffer_minimum:.0%}")
    if inputs.intraday_round_trips_this_week >= limits.max_intraday_round_trips_per_week:
        reasons.append("PDT round-trip limit reached")
    return reasons
