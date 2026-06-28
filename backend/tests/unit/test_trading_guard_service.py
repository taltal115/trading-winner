from datetime import UTC, datetime, timedelta

from app.config.settings import SafetyLimits
from app.models.entities import Trade
from app.models.enums import TradeSide, TradeStatus
from app.repositories.base import InMemoryDocumentStore
from app.repositories.repositories import (
    LogRepository,
    PortfolioRepository,
    PositionRepository,
    SystemStateRepository,
    TradeRepository,
)
from app.services.log_writer import LogWriter
from app.services.portfolio_service import PortfolioService
from app.services.trading_guard_service import TradingGuardService

TICKER = "NVDA"


def _closed_trade(seq: int, pnl: float, exit_time: datetime) -> Trade:
    entry = exit_time - timedelta(days=2)
    return Trade(
        id=f"trade_{TICKER}_2026-07-{seq:02d}_120000",
        ticker=TICKER,
        side=TradeSide.LONG,
        entry_time=entry,
        exit_time=exit_time,
        entry_price=100.0,
        exit_price=100.0 + pnl,
        quantity=1.0,
        status=TradeStatus.CLOSED,
        signal_id=f"signal_{TICKER}_2026-07-{seq:02d}",
        feature_snapshot_id=f"feature_{TICKER}_2026-07-{seq:02d}",
        pnl=pnl,
    )


def _build() -> tuple[TradingGuardService, TradeRepository]:
    store = InMemoryDocumentStore()
    trade_repo = TradeRepository(store)
    state_repo = SystemStateRepository(store)
    portfolio_repo = PortfolioRepository(store)
    position_repo = PositionRepository(store)
    log_repo = LogRepository(store)
    portfolio = PortfolioService(portfolio_repo, position_repo, LogWriter("portfolio", log_repo))
    guard = TradingGuardService(
        state_repo,
        trade_repo,
        portfolio,
        LogWriter("trading_guard", log_repo),
        SafetyLimits(max_daily_loss=0.06, max_consecutive_losses=4),
    )
    return guard, trade_repo


def test_default_state_not_halted() -> None:
    guard, _ = _build()
    assert guard.assess().halted is False
    assert guard.get_state().kill_switch_enabled is False


def test_kill_switch_engage_and_release() -> None:
    guard, _ = _build()
    guard.engage_kill_switch("circuit test")
    state = guard.get_state()
    assert state.kill_switch_enabled is True
    assert state.halt_reason == "circuit test"
    assert guard.assess().halted is True

    guard.release_kill_switch()
    assert guard.get_state().kill_switch_enabled is False
    assert guard.assess().halted is False


def test_consecutive_losses_trip_breaker() -> None:
    guard, trade_repo = _build()
    base = datetime.now(UTC) - timedelta(days=10)
    for i in range(4):
        trade_repo.save(_closed_trade(10 + i, pnl=-50.0, exit_time=base + timedelta(days=i)))
    assert guard.assess().halted is True


def test_recent_win_resets_loss_streak() -> None:
    guard, trade_repo = _build()
    base = datetime.now(UTC) - timedelta(days=10)
    # Three losses, then a win as the most recent -> streak resets to 0.
    trade_repo.save(_closed_trade(10, pnl=-50.0, exit_time=base))
    trade_repo.save(_closed_trade(11, pnl=-50.0, exit_time=base + timedelta(days=1)))
    trade_repo.save(_closed_trade(12, pnl=-50.0, exit_time=base + timedelta(days=2)))
    trade_repo.save(_closed_trade(13, pnl=10.0, exit_time=base + timedelta(days=3)))
    assert guard.assess().halted is False


def test_daily_loss_limit_trips_today_only() -> None:
    guard, trade_repo = _build()
    now = datetime.now(UTC)
    # A big loss yesterday should not count toward today's limit.
    trade_repo.save(_closed_trade(10, pnl=-7000.0, exit_time=now - timedelta(days=1)))
    assert guard.assess().halted is False
    # A loss today beyond 6% of 100k equity trips it.
    trade_repo.save(_closed_trade(11, pnl=-6500.0, exit_time=now))
    assert guard.assess().halted is True
