"""Execution engine: build a broker order intent from a risk decision.

Pure: turns an approved ``RiskDecision`` into a deterministic ``Order``. No I/O,
no broker calls (those live in ExecutionService). Limit orders are used for
volatility spikes, market orders otherwise (TRADING_ENGINE.md section 10).
"""

from __future__ import annotations

from app.models.entities import Position, RiskDecision
from app.models.enums import OrderAction, TradeSide
from app.services.broker import Order
from app.utils.ids import exit_order_id, order_id

_VOLATILITY_SPIKE_RELATIVE_VOLUME = 3.0


def build_order(
    decision: RiskDecision,
    reference_price: float,
    relative_volume: float,
) -> Order:
    """Construct an idempotent order from an approved risk decision."""
    if not decision.approved:
        raise ValueError(f"cannot build order for unapproved risk decision {decision.id}")

    use_limit = relative_volume >= _VOLATILITY_SPIKE_RELATIVE_VOLUME
    return Order(
        client_order_id=order_id(decision.ticker, decision.timestamp),
        ticker=decision.ticker,
        side=decision.side,
        action=OrderAction.BUY,
        quantity=decision.quantity,
        order_type="LIMIT" if use_limit else "MARKET",
        reference_price=reference_price,
        limit_price=reference_price if use_limit else None,
    )


def build_exit_order(position: Position, reference_price: float) -> Order:
    """Construct an idempotent sell-to-close order for an open long position.

    Market order at the current reference price (swing exits are not latency
    sensitive, TRADING_ENGINE.md section 10). ``side`` carries the position's
    direction; the close intent is implied by the exit order id.
    """
    return Order(
        client_order_id=exit_order_id(position.ticker, position.opened_at),
        ticker=position.ticker,
        side=TradeSide.LONG,
        action=OrderAction.SELL,
        quantity=position.quantity,
        order_type="MARKET",
        reference_price=reference_price,
    )
