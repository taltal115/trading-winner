"""Tests for the IBKR broker adapter.

A fake SDK + client mimic the subset of the ``ib_insync`` surface the adapter
uses (``Stock``/``MarketOrder``/``LimitOrder`` factories,
``client.placeOrder`` -> trade with ``orderStatus``, ``client.positions``) so we
verify order mapping, fill parsing, idempotency, position mapping and the
missing-SDK / backend-selection behavior — all without the SDK or a TWS session.
"""

from __future__ import annotations

import pytest

from app.config.settings import Settings
from app.models.enums import OrderAction, TradeSide
from app.services.broker import Order
from app.services.ibkr_broker import IBKRBroker


class _FakeOrderStatus:
    def __init__(self, status: str, filled: float, avg_fill_price: float) -> None:
        self.status = status
        self.filled = filled
        self.avgFillPrice = avg_fill_price


class _FakeTrade:
    def __init__(self, order_status: _FakeOrderStatus) -> None:
        self.orderStatus = order_status

    def isDone(self) -> bool:
        return True


class _FakeIBOrder:
    def __init__(self, action: str, quantity: float, limit_price: float | None = None) -> None:
        self.action = action
        self.totalQuantity = quantity
        self.lmtPrice = limit_price
        self.orderRef = ""


class _FakeContract:
    def __init__(self, symbol: str) -> None:
        self.symbol = symbol


class _FakePosition:
    def __init__(self, symbol: str, position: float, avg_cost: float) -> None:
        self.contract = _FakeContract(symbol)
        self.position = position
        self.avgCost = avg_cost


class _FakeSDK:
    """Namespace exposing the ``ib_insync`` factories the adapter constructs."""

    @staticmethod
    def Stock(symbol: str, exchange: str, currency: str) -> _FakeContract:
        return _FakeContract(symbol)

    @staticmethod
    def MarketOrder(action: str, quantity: float) -> _FakeIBOrder:
        return _FakeIBOrder(action, quantity)

    @staticmethod
    def LimitOrder(action: str, quantity: float, limit_price: float) -> _FakeIBOrder:
        return _FakeIBOrder(action, quantity, limit_price)


class _FakeIB:
    def __init__(
        self,
        status: str = "Filled",
        filled: float = 10.0,
        avg_fill_price: float = 101.5,
        positions: list[_FakePosition] | None = None,
    ) -> None:
        self._status = _FakeOrderStatus(status, filled, avg_fill_price)
        self._positions = positions or []
        self.placed: list[tuple[_FakeContract, _FakeIBOrder]] = []

    def placeOrder(self, contract: _FakeContract, order: _FakeIBOrder) -> _FakeTrade:
        self.placed.append((contract, order))
        return _FakeTrade(self._status)

    def waitOnUpdate(self, timeout: float = 1) -> None:  # pragma: no cover - never hit
        raise AssertionError("fake trade is already done; should not wait")

    def positions(self) -> list[_FakePosition]:
        return self._positions


def _order(action: OrderAction = OrderAction.BUY, order_type: str = "MARKET") -> Order:
    return Order(
        client_order_id="order_NVDA_2026-07-28_093015",
        ticker="NVDA",
        side=TradeSide.LONG,
        action=action,
        quantity=10.0,
        order_type=order_type,
        reference_price=100.0,
        limit_price=99.0 if order_type == "LIMIT" else None,
    )


def _broker(client: _FakeIB) -> IBKRBroker:
    return IBKRBroker(client=client, sdk=_FakeSDK())


def test_submit_order_returns_fill_from_order_status() -> None:
    fill = _broker(_FakeIB()).submit_order(_order())
    assert fill.client_order_id == "order_NVDA_2026-07-28_093015"
    assert fill.ticker == "NVDA"
    assert fill.quantity == 10.0
    assert fill.fill_price == 101.5


def test_submit_order_sets_order_ref_for_traceability() -> None:
    ib = _FakeIB()
    _broker(ib).submit_order(_order())
    _, placed_order = ib.placed[0]
    assert placed_order.orderRef == "order_NVDA_2026-07-28_093015"
    assert placed_order.action == "BUY"


def test_limit_order_uses_limit_factory() -> None:
    ib = _FakeIB()
    _broker(ib).submit_order(_order(order_type="LIMIT"))
    _, placed_order = ib.placed[0]
    assert placed_order.lmtPrice == 99.0


def test_submit_order_is_idempotent() -> None:
    ib = _FakeIB()
    broker = _broker(ib)
    first = broker.submit_order(_order())
    second = broker.submit_order(_order())
    assert first == second
    assert len(ib.placed) == 1  # never placed twice


def test_unfilled_status_raises_runtime_error() -> None:
    broker = _broker(_FakeIB(status="Cancelled"))
    with pytest.raises(RuntimeError, match="not filled"):
        broker.submit_order(_order())


def test_sdk_error_is_normalized_to_runtime_error() -> None:
    class _ExplodingIB(_FakeIB):
        def placeOrder(self, contract: _FakeContract, order: _FakeIBOrder) -> _FakeTrade:
            raise ValueError("boom")

    with pytest.raises(RuntimeError, match="IBKR order submission failed"):
        _broker(_ExplodingIB()).submit_order(_order())


def test_get_positions_maps_long_rows_and_drops_non_long() -> None:
    ib = _FakeIB(
        positions=[
            _FakePosition("NVDA", 10.0, 100.1234),
            _FakePosition("FLAT", 0.0, 50.0),
            _FakePosition("SHRT", -5.0, 20.0),
        ]
    )
    positions = _broker(ib).get_positions()
    assert len(positions) == 1
    assert positions[0].ticker == "NVDA"
    assert positions[0].quantity == 10.0
    assert positions[0].avg_price == 100.1234


def test_missing_sdk_raises_helpful_error() -> None:
    # No client and no sdk injected, and ib_insync isn't installed in the test env.
    with pytest.raises(RuntimeError, match="ib_insync package"):
        IBKRBroker()


def test_build_broker_selects_backend() -> None:
    from app.api.dependencies import _build_broker
    from app.services.broker import MockBroker

    assert isinstance(_build_broker(Settings(broker_backend="mock")), MockBroker)
    with pytest.raises(RuntimeError, match="ib_insync package"):
        _build_broker(Settings(broker_backend="ibkr"))
    with pytest.raises(NotImplementedError):
        _build_broker(Settings(broker_backend="alpaca"))
