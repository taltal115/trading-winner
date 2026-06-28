from datetime import UTC, datetime, timedelta

from app.api.dependencies import AppContainer
from app.config.settings import ExitLimits, Settings, SystemPhase
from app.models.entities import PriceBar
from app.models.enums import TradeStatus
from app.services.log_writer import LogWriter
from app.services.market_data import MockMarketDataSource
from app.services.position_monitor_service import PositionMonitorService
from app.workers.learning_job import run_learning_job


class _CrashSource(MockMarketDataSource):
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


def _phase6() -> AppContainer:
    return AppContainer(Settings(phase=SystemPhase.PRODUCTION))


def _phase5() -> AppContainer:
    return AppContainer(Settings(phase=SystemPhase.STAGING))


def test_phase6_monitor_records_outcome_on_close() -> None:
    container = _phase6()
    container.pipeline_service.run_daily()

    closed = container.position_monitor_service.monitor_positions()
    # Uptrend feed -> no exit yet; force close with crash source + outcome hook.
    assert closed == []

    monitor = PositionMonitorService(
        container.position_repo,
        container.trade_repo,
        container.portfolio_service,
        container.broker,
        _CrashSource(),
        LogWriter("position_monitor", container.log_repo),
        ExitLimits(),
        outcome_service=container.outcome_service,
    )
    closed = monitor.monitor_positions()
    assert len(closed) == 1
    trade = closed[0]
    assert trade.status == TradeStatus.CLOSED

    outcomes = container.outcome_service.list_outcomes()
    assert len(outcomes) == 1
    outcome = outcomes[0]
    assert outcome.trade_id == trade.id
    assert outcome.signal_id == trade.signal_id
    assert outcome.ai_analysis_id == trade.ai_analysis_id
    assert outcome.risk_decision_id == trade.risk_decision_id
    assert outcome.exit_reason == "STOP_LOSS"
    assert outcome.is_winner is False
    assert container.integrity_service.find_orphans() == []


def test_phase5_monitor_does_not_record_outcomes() -> None:
    container = _phase5()
    container.pipeline_service.run_daily()

    monitor = PositionMonitorService(
        container.position_repo,
        container.trade_repo,
        container.portfolio_service,
        container.broker,
        _CrashSource(),
        LogWriter("position_monitor", container.log_repo),
        ExitLimits(),
    )
    monitor.monitor_positions()
    assert container.outcome_service.list_outcomes() == []


def test_learning_job_backfills_closed_trades() -> None:
    container = _phase6()
    container.pipeline_service.run_daily()

    # Close without the outcome hook (simulates a trade closed before Phase 6).
    PositionMonitorService(
        container.position_repo,
        container.trade_repo,
        container.portfolio_service,
        container.broker,
        _CrashSource(),
        LogWriter("position_monitor", container.log_repo),
        ExitLimits(),
    ).monitor_positions()
    assert container.outcome_service.list_outcomes() == []

    recorded = run_learning_job(container)
    assert recorded is not None
    assert len(recorded) == 1
    outcome = container.outcome_service.list_outcomes()[0]
    assert outcome.trade_id == container.trade_repo.get_closed()[0].id
    jobs = container.store.list("jobs")
    assert any(j["job_type"] == "learning_job" and j["status"] == "SUCCEEDED" for j in jobs)


def test_learning_job_disabled_below_phase6() -> None:
    container = _phase5()
    assert run_learning_job(container) is None


def test_outcome_idempotent_on_re_record() -> None:
    container = _phase6()
    container.pipeline_service.run_daily()
    PositionMonitorService(
        container.position_repo,
        container.trade_repo,
        container.portfolio_service,
        container.broker,
        _CrashSource(),
        LogWriter("position_monitor", container.log_repo),
        ExitLimits(),
        outcome_service=container.outcome_service,
    ).monitor_positions()

    trade = container.trade_repo.get_closed()[0]
    first = container.outcome_service.record_from_close(trade, "STOP_LOSS")
    second = container.outcome_service.record_from_close(trade, "STOP_LOSS")
    assert first is not None and second is not None
    assert first.id == second.id
    assert len(container.outcome_service.list_outcomes()) == 1
