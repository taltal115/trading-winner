from datetime import UTC, datetime, timedelta

from app.api.dependencies import AppContainer
from app.config.settings import ExitLimits, Settings, SystemPhase
from app.models.entities import PriceBar
from app.models.enums import JobStatus, TradeStatus
from app.services.log_writer import LogWriter
from app.services.market_data import MockMarketDataSource
from app.services.position_monitor_service import PositionMonitorService
from app.workers.position_monitor import run_position_monitor


class _CrashSource(MockMarketDataSource):
    """Serves a deep, flat decline for any ticker to force stop-loss exits."""

    def get_price_history(self, ticker: str) -> list[PriceBar]:
        first_day = datetime(2026, 1, 1, tzinfo=UTC)
        return [
            PriceBar(
                ticker=ticker,
                timestamp=first_day + timedelta(days=i),
                open=1.0,
                high=1.0,
                low=1.0,
                close=1.0,
                volume=1_000_000.0,
            )
            for i in range(260)
        ]


def _phase5() -> AppContainer:
    return AppContainer(Settings(phase=SystemPhase.STAGING))


def test_monitor_closes_open_position_end_to_end() -> None:
    container = _phase5()
    container.pipeline_service.run_daily()  # opens NVDA with full traceability
    assert len(container.portfolio_service.open_positions()) == 1

    portfolio_before = container.portfolio_service.get_or_create_portfolio()
    cash_before = portfolio_before.cash

    # Monitor over the SAME repos/portfolio/broker but with a crashed price feed.
    monitor = PositionMonitorService(
        container.position_repo,
        container.trade_repo,
        container.portfolio_service,
        container.broker,
        _CrashSource(),
        LogWriter("position_monitor", container.log_repo),
        ExitLimits(),
    )
    closed = monitor.monitor_positions()

    assert len(closed) == 1
    trade = closed[0]
    assert trade.ticker == "NVDA"
    assert trade.status == TradeStatus.CLOSED
    assert trade.exit_price == 1.0
    assert trade.pnl is not None and trade.pnl < 0  # forced stop-loss
    assert container.portfolio_service.open_positions() == []
    # Proceeds returned to cash; traceability chain intact.
    assert container.portfolio_service.get_or_create_portfolio().cash > cash_before
    assert container.integrity_service.find_orphans() == []


def test_monitor_holds_when_no_exit_triggers() -> None:
    container = _phase5()
    container.pipeline_service.run_daily()
    # Default (uptrend) feed, freshly opened -> nothing should exit yet.
    closed = container.position_monitor_service.monitor_positions()
    assert closed == []
    assert len(container.portfolio_service.open_positions()) == 1


def test_worker_records_succeeded_job() -> None:
    container = _phase5()
    container.pipeline_service.run_daily()
    run_position_monitor(container)
    jobs = [j for j in container.store.list("jobs")]
    assert len(jobs) == 1
    assert jobs[0]["status"] == JobStatus.SUCCEEDED
    assert jobs[0]["job_type"] == "position_monitor"


def test_worker_is_disabled_below_phase5() -> None:
    container = AppContainer(Settings(phase=SystemPhase.RISK_EXECUTION))
    container.pipeline_service.run_daily()
    closed = run_position_monitor(container)
    assert closed == []
    # No job is created when monitoring is gated off.
    assert container.store.list("jobs") == []
    # The position opened by Phase 4 execution remains untouched.
    assert len(container.portfolio_service.open_positions()) == 1
