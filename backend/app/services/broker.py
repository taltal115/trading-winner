"""Broker abstraction (external execution boundary).

This is the seam where the IBKR client plugs in. Submissions are idempotent by
``client_order_id`` (ARCHITECTURE.md 3.6: execution must be idempotent,
retry-safe, logged). The paper broker fills deterministically at the order's
reference price.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Protocol

from pydantic import BaseModel, ConfigDict

from app.models.enums import OrderAction, TradeSide


class Order(BaseModel):
    model_config = ConfigDict(extra="forbid")

    client_order_id: str
    ticker: str
    side: TradeSide
    action: OrderAction
    quantity: float
    order_type: str  # "MARKET" | "LIMIT"
    reference_price: float
    limit_price: float | None = None


class Fill(BaseModel):
    model_config = ConfigDict(extra="forbid")

    client_order_id: str
    ticker: str
    side: TradeSide
    quantity: float
    fill_price: float
    filled_at: datetime
    status: str = "FILLED"


class BrokerPosition(BaseModel):
    """A position as reported by the broker (the source of truth for sync)."""

    model_config = ConfigDict(extra="forbid")

    ticker: str
    quantity: float
    avg_price: float


class BrokerClient(Protocol):
    def submit_order(self, order: Order) -> Fill: ...

    def get_positions(self) -> list[BrokerPosition]: ...


class MockBroker:
    """Deterministic paper broker. Idempotent by client_order_id.

    Tracks net positions from filled orders so it can report broker-side truth
    for reconciliation. BUY fills add quantity (weighting the average price),
    SELL fills reduce it; flat positions are dropped.
    """

    def __init__(self) -> None:
        self._fills: dict[str, Fill] = {}
        self._positions: dict[str, BrokerPosition] = {}

    def submit_order(self, order: Order) -> Fill:
        existing = self._fills.get(order.client_order_id)
        if existing is not None:
            return existing  # idempotent: never re-apply to positions
        fill = Fill(
            client_order_id=order.client_order_id,
            ticker=order.ticker,
            side=order.side,
            quantity=order.quantity,
            fill_price=order.limit_price or order.reference_price,
            filled_at=datetime.now(UTC),
        )
        self._fills[order.client_order_id] = fill
        self._apply_to_positions(order.action, fill)
        return fill

    def get_positions(self) -> list[BrokerPosition]:
        return list(self._positions.values())

    def _apply_to_positions(self, action: OrderAction, fill: Fill) -> None:
        current = self._positions.get(fill.ticker)
        prior_qty = current.quantity if current is not None else 0.0
        if action == OrderAction.BUY:
            new_qty = prior_qty + fill.quantity
            prior_notional = (current.avg_price * prior_qty) if current is not None else 0.0
            avg_price = (prior_notional + fill.fill_price * fill.quantity) / new_qty
        else:  # SELL reduces the position; average entry price is unchanged
            new_qty = prior_qty - fill.quantity
            avg_price = current.avg_price if current is not None else fill.fill_price

        if new_qty <= 0:
            self._positions.pop(fill.ticker, None)
            return
        self._positions[fill.ticker] = BrokerPosition(
            ticker=fill.ticker, quantity=new_qty, avg_price=round(avg_price, 4)
        )
