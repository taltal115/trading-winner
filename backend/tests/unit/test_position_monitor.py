from datetime import UTC, datetime, timedelta

from app.config.settings import ExitLimits
from app.engines.feature_engine import MIN_BARS
from app.models.entities import PriceBar, Trade
from app.models.enums import TradeSide, TradeStatus
from app.repositories.base import InMemoryDocumentStore
from app.repositories.repositories import (
    LogRepository,
    PortfolioRepository,
    PositionRepository,
    TradeRepository,
)
from app.services.broker import MockBroker
from app.services.log_writer import LogWriter
from app.services.market_data import MockMarketDataSource
from app.services.portfolio_service import PortfolioService
from app.services.position_monitor_service import PositionMonitorService

TICKER = "NVDA"
ENTRY_TS = datetime(2026, 7, 28, 16, 0, 0, tzinfo=UTC)


class _StubSource(MockMarketDataSource):
    """MockMarketDataSource that serves a controlled close series for one ticker."""

    def __init__(self, closes: list[float]) -> None:
        super().__init__()
        self._closes = closes

    def get_price_history(self, ticker: str) -> list[PriceBar]:
        first_day = datetime(2026, 1, 1, tzinfo=UTC)
        bars: list[PriceBar] = []
        for i, close in enumerate(self._closes):
            bars.append(
                PriceBar(
                    ticker=ticker,
                    timestamp=first_day + timedelta(days=i),
                    open=close,
                    high=close,
                    low=close,
                    close=close,
                    volume=1_000_000.0,
                )
            )
        return bars


def _flat(close: float, count: int = MIN_BARS) -> list[float]:
    return [close] * count


def _declining(start: float, count: int = MIN_BARS) -> list[float]:
    return [start - i * 0.1 for i in range(count)]


def _trade(quantity: float = 100.0) -> Trade:
    return Trade(
        id=f"trade_{TICKER}_2026-07-28_160000",
        ticker=TICKER,
        side=TradeSide.LONG,
        entry_time=ENTRY_TS,
        entry_price=100.0,
        quantity=quantity,
        status=TradeStatus.OPEN,
        signal_id=f"signal_{TICKER}_2026-07-28",
        feature_snapshot_id=f"feature_{TICKER}_2026-07-28",
        ai_analysis_id=f"ai_{TICKER}_2026-07-28",
        risk_decision_id=f"risk_{TICKER}_2026-07-28_160000",
    )


def _build(
    closes: list[float],
    stop_price: float,
    target_price: float,
    opened_at: datetime = ENTRY_TS,
) -> tuple[PositionMonitorService, TradeRepository, PositionRepository, PortfolioService]:
    store = InMemoryDocumentStore()
    trade_repo = TradeRepository(store)
    position_repo = PositionRepository(store)
    portfolio_repo = PortfolioRepository(store)
    log_repo = LogRepository(store)

    portfolio = PortfolioService(portfolio_repo, position_repo, LogWriter("portfolio", log_repo))
    trade = _trade()
    trade = trade.model_copy(update={"entry_time": opened_at})
    trade_repo.save(trade)
    portfolio.apply_fill(
        trade,
        sector="Technology",
        fill_price=trade.entry_price,
        quantity=trade.quantity,
        stop_price=stop_price,
        target_price=target_price,
    )

    monitor = PositionMonitorService(
        position_repo,
        trade_repo,
        portfolio,
        MockBroker(),
        _StubSource(closes),
        LogWriter("position_monitor", log_repo),
        ExitLimits(),
    )
    return monitor, trade_repo, position_repo, portfolio


def test_stop_loss_closes_position() -> None:
    monitor, trade_repo, position_repo, portfolio = _build(
        _flat(90.0), stop_price=95.0, target_price=130.0
    )
    cash_before = portfolio.get_or_create_portfolio().cash

    closed = monitor.monitor_positions()

    assert len(closed) == 1
    trade = closed[0]
    assert trade.status == TradeStatus.CLOSED
    assert trade.exit_price == 90.0
    assert trade.pnl == (90.0 - 100.0) * 100.0  # realized loss
    assert position_repo.get_open() == []
    # Proceeds credited back to cash; equity reflects the realized loss.
    assert portfolio.get_or_create_portfolio().cash == cash_before + 90.0 * 100.0


def test_profit_target_closes_position() -> None:
    monitor, _, position_repo, _ = _build(_flat(120.0), stop_price=80.0, target_price=112.0)
    closed = monitor.monitor_positions()
    assert len(closed) == 1
    assert closed[0].pnl == (120.0 - 100.0) * 100.0
    assert position_repo.get_open() == []


def test_momentum_failure_closes_position() -> None:
    # Declining series -> sma_20 < sma_50; stop/target are out of the way.
    monitor, _, position_repo, _ = _build(_declining(120.0), stop_price=0.01, target_price=1e9)
    closed = monitor.monitor_positions()
    assert len(closed) == 1
    assert position_repo.get_open() == []


def test_time_exit_closes_position() -> None:
    old_entry = datetime.now(UTC) - timedelta(days=15)
    monitor, _, position_repo, _ = _build(
        _flat(100.0), stop_price=80.0, target_price=130.0, opened_at=old_entry
    )
    closed = monitor.monitor_positions()
    assert len(closed) == 1
    assert position_repo.get_open() == []


def test_no_exit_keeps_position_open() -> None:
    monitor, trade_repo, position_repo, _ = _build(
        _flat(100.0), stop_price=80.0, target_price=130.0
    )
    closed = monitor.monitor_positions()
    assert closed == []
    assert len(position_repo.get_open()) == 1
    assert trade_repo.list()[0].status == TradeStatus.OPEN


def test_monitor_is_idempotent() -> None:
    monitor, trade_repo, position_repo, _ = _build(_flat(90.0), stop_price=95.0, target_price=130.0)
    first = monitor.monitor_positions()
    second = monitor.monitor_positions()
    assert len(first) == 1
    assert second == []  # nothing open to close on the second pass
    closed_trades = [t for t in trade_repo.list() if t.status == TradeStatus.CLOSED]
    assert len(closed_trades) == 1
