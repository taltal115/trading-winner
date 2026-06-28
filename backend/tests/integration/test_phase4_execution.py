from app.api.dependencies import AppContainer
from app.config.settings import Settings, SystemPhase


def _phase4() -> AppContainer:
    return AppContainer(Settings(phase=SystemPhase.RISK_EXECUTION))


def test_phase4_executes_only_fully_traceable_signal() -> None:
    container = _phase4()
    container.pipeline_service.run_daily()

    trades = container.trade_repo.list()
    # Only NVDA is fully traceable (has AI analysis) and risk-approved.
    assert len(trades) == 1
    trade = trades[0]
    assert trade.ticker == "NVDA"
    assert trade.signal_id and trade.feature_snapshot_id
    assert trade.ai_analysis_id is not None
    assert trade.risk_decision_id is not None

    # AAPL has no catalyst -> no AI -> blocked by the execution gate.
    assert all(t.ticker != "AAPL" for t in trades)


def test_phase4_opens_position_and_debits_cash() -> None:
    container = _phase4()
    container.pipeline_service.run_daily()
    positions = container.portfolio_service.open_positions()
    portfolio = container.portfolio_service.get_or_create_portfolio()
    assert len(positions) == 1
    assert portfolio.cash < portfolio.equity  # cash was debited by the fill


def test_phase4_integrity_holds() -> None:
    container = _phase4()
    container.pipeline_service.run_daily()
    assert container.integrity_service.find_orphans() == []


def test_phase4_rerun_is_idempotent() -> None:
    container = _phase4()
    container.pipeline_service.run_daily()
    container.pipeline_service.run_daily()
    # Re-running does not double-execute (duplicate-position rejection + idempotent id).
    assert len(container.trade_repo.list()) == 1
    assert len(container.portfolio_service.open_positions()) == 1


def test_risk_decisions_are_persisted_for_audit() -> None:
    container = _phase4()
    container.pipeline_service.run_daily()
    assert len(container.risk_repo.list()) >= 1
