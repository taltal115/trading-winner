from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient

from app.api.dependencies import AppContainer, get_container
from app.config.settings import ExitLimits, Settings, SystemPhase
from app.main import create_app
from app.models.entities import PriceBar
from app.services.log_writer import LogWriter
from app.services.market_data import MockMarketDataSource
from app.services.position_monitor_service import PositionMonitorService
from app.workers.reconciliation import run_reconciliation


class _CrashSource(MockMarketDataSource):
    """Forces a stop-loss exit by serving a deep, flat price for any ticker."""

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


def _client() -> TestClient:
    get_container.cache_clear()
    return TestClient(create_app())


def test_in_sync_after_execution() -> None:
    container = _phase5()
    container.pipeline_service.run_daily()  # buys NVDA via container.broker

    report = container.reconciliation_service.reconcile()
    assert report.in_sync is True
    assert "NVDA" in report.matched


def test_in_sync_after_position_closed() -> None:
    container = _phase5()
    container.pipeline_service.run_daily()

    # Close the open position through the SAME broker via a forced stop-loss exit.
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

    # Both books are now flat -> still in sync.
    report = container.reconciliation_service.reconcile()
    assert report.in_sync is True
    assert container.position_repo.get_open() == []
    assert container.broker.get_positions() == []


def test_drift_detected_when_internal_position_lost() -> None:
    container = _phase5()
    container.pipeline_service.run_daily()
    # Simulate our book losing a position the broker still reports.
    for position in container.position_repo.get_open():
        container.position_repo.delete(position.id)

    report = container.reconciliation_service.reconcile()
    assert report.in_sync is False
    assert any(d.kind == "untracked_internally" for d in report.discrepancies)


def test_drift_detected_when_broker_missing_position() -> None:
    container = _phase5()
    container.pipeline_service.run_daily()
    # Broker reports flat while our book still holds -> phantom position.
    container.broker._positions.clear()  # type: ignore[attr-defined]

    report = container.reconciliation_service.reconcile()
    assert report.in_sync is False
    assert any(d.kind == "missing_at_broker" for d in report.discrepancies)


def test_worker_records_succeeded_job() -> None:
    container = _phase5()
    container.pipeline_service.run_daily()
    report = run_reconciliation(container)
    assert report is not None and report.in_sync is True
    jobs = container.store.list("jobs")
    assert any(j["job_type"] == "reconciliation" and j["status"] == "SUCCEEDED" for j in jobs)


def test_worker_disabled_below_phase5() -> None:
    container = AppContainer(Settings(phase=SystemPhase.RISK_EXECUTION))
    container.pipeline_service.run_daily()
    assert run_reconciliation(container) is None
    assert container.store.list("jobs") == []


def test_reconcile_route_reports_in_sync_when_flat() -> None:
    resp = _client().get("/positions/reconcile")
    assert resp.status_code == 200
    body = resp.json()
    assert body["in_sync"] is True
    assert body["discrepancies"] == []
