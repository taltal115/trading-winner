"""Interactive Brokers (IBKR) execution adapter — the production ``BrokerClient``.

Concrete implementation of the execution seam in ``broker.py`` over the
``ib_insync`` SDK. Services and engines are unchanged: they depend only on the
``BrokerClient`` protocol, so swapping the paper ``MockBroker`` for IBKR is a
wiring decision (``broker_backend = "ibkr"``).

Design (mirrors the Firestore / OpenAI adapters):
- ``ib_insync`` is imported lazily so the package is only required when this
  backend is selected (dev/tests use the deterministic ``MockBroker``). A
  helpful ``RuntimeError`` is raised if the SDK is missing.
- The SDK factory bundle (``IB``/``Stock``/``MarketOrder``/``LimitOrder``) and a
  connected client may both be injected for testing, so the full adapter is
  exercised offline with an in-file fake mimicking the ``ib_insync`` surface.
- Submissions stay idempotent by ``client_order_id`` (ARCHITECTURE.md 3.6): the
  id is sent as the IBKR ``orderRef`` for traceability and a process-local cache
  guarantees a re-submission never places a second order. SDK failures are
  normalized to ``RuntimeError`` so the execution path logs and stops cleanly.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from app.models.enums import OrderAction
from app.services.broker import BrokerPosition, Fill, Order


def _import_sdk() -> Any:
    try:
        import ib_insync
    except ImportError as exc:  # pragma: no cover - exercised only without the SDK
        raise RuntimeError(
            "broker_backend='ibkr' requires the ib_insync package. "
            "Install it with: pip install '.[ibkr]'"
        ) from exc
    return ib_insync


class IBKRBroker:
    """Adapts the IBKR TWS/Gateway API (``ib_insync``) to the ``BrokerClient``."""

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 7497,
        client_id: int = 1,
        client: Any = None,
        sdk: Any = None,
    ) -> None:
        self._sdk = sdk if sdk is not None else _import_sdk()
        self._fills: dict[str, Fill] = {}
        if client is not None:
            self._ib = client
            return
        self._ib = self._sdk.IB()
        self._ib.connect(host, port, clientId=client_id)

    def submit_order(self, order: Order) -> Fill:
        cached = self._fills.get(order.client_order_id)
        if cached is not None:
            return cached  # idempotent: never place the order twice

        contract = self._sdk.Stock(order.ticker, "SMART", "USD")
        ib_order = self._build_order(order)
        ib_order.orderRef = order.client_order_id

        try:
            trade = self._ib.placeOrder(contract, ib_order)
            while not trade.isDone():
                self._ib.waitOnUpdate(timeout=1)
            status = trade.orderStatus
        except Exception as exc:  # normalize SDK errors for the execution path
            raise RuntimeError(f"IBKR order submission failed: {exc}") from exc

        if status.status != "Filled":
            raise RuntimeError(
                f"IBKR order {order.client_order_id} not filled (status={status.status!r})"
            )

        fill = Fill(
            client_order_id=order.client_order_id,
            ticker=order.ticker,
            side=order.side,
            quantity=float(status.filled),
            fill_price=float(status.avgFillPrice),
            filled_at=datetime.now(UTC),
        )
        self._fills[order.client_order_id] = fill
        return fill

    def get_positions(self) -> list[BrokerPosition]:
        positions: list[BrokerPosition] = []
        for raw in self._ib.positions():
            quantity = float(raw.position)
            if quantity <= 0:  # long-only swing system: ignore flat/short rows
                continue
            positions.append(
                BrokerPosition(
                    ticker=raw.contract.symbol,
                    quantity=quantity,
                    avg_price=round(float(raw.avgCost), 4),
                )
            )
        return positions

    def _build_order(self, order: Order) -> Any:
        action = "BUY" if order.action == OrderAction.BUY else "SELL"
        if order.order_type == "LIMIT":
            if order.limit_price is None:
                raise RuntimeError("LIMIT order requires a limit_price")
            return self._sdk.LimitOrder(action, order.quantity, order.limit_price)
        return self._sdk.MarketOrder(action, order.quantity)
