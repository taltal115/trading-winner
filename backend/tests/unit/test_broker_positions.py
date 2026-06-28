from app.models.enums import OrderAction, TradeSide
from app.services.broker import MockBroker, Order


def _order(action: OrderAction, oid: str, qty: float, price: float) -> Order:
    return Order(
        client_order_id=oid,
        ticker="NVDA",
        side=TradeSide.LONG,
        action=action,
        quantity=qty,
        order_type="MARKET",
        reference_price=price,
    )


def test_buy_creates_position() -> None:
    broker = MockBroker()
    broker.submit_order(_order(OrderAction.BUY, "order_NVDA_2026-07-28_100000", 10, 100.0))
    positions = broker.get_positions()
    assert len(positions) == 1
    assert positions[0].ticker == "NVDA"
    assert positions[0].quantity == 10.0
    assert positions[0].avg_price == 100.0


def test_buys_weight_average_price() -> None:
    broker = MockBroker()
    broker.submit_order(_order(OrderAction.BUY, "order_NVDA_2026-07-28_100000", 10, 100.0))
    broker.submit_order(_order(OrderAction.BUY, "order_NVDA_2026-07-28_100100", 10, 110.0))
    pos = broker.get_positions()[0]
    assert pos.quantity == 20.0
    assert pos.avg_price == 105.0


def test_sell_reduces_and_flat_is_dropped() -> None:
    broker = MockBroker()
    broker.submit_order(_order(OrderAction.BUY, "order_NVDA_2026-07-28_100000", 10, 100.0))
    broker.submit_order(_order(OrderAction.SELL, "order_NVDA_2026-07-28_100000_exit", 10, 120.0))
    assert broker.get_positions() == []


def test_submit_is_idempotent_for_positions() -> None:
    broker = MockBroker()
    order = _order(OrderAction.BUY, "order_NVDA_2026-07-28_100000", 10, 100.0)
    broker.submit_order(order)
    broker.submit_order(order)  # same client_order_id -> not re-applied
    assert broker.get_positions()[0].quantity == 10.0
