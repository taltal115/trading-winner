from fastapi.testclient import TestClient

from app.api.dependencies import AppContainer, get_container
from app.config.settings import Settings, SystemPhase
from app.main import create_app


def _phase4() -> AppContainer:
    return AppContainer(Settings(phase=SystemPhase.RISK_EXECUTION))


def _client() -> TestClient:
    get_container.cache_clear()
    return TestClient(create_app())


def test_kill_switch_blocks_execution_stage() -> None:
    container = _phase4()
    container.trading_guard_service.engage_kill_switch("ops halt")

    container.pipeline_service.run_daily()

    # Entries are halted: no trades, no positions, but signals still generate.
    assert container.trade_repo.list() == []
    assert container.portfolio_service.open_positions() == []


def test_resume_re_enables_execution() -> None:
    container = _phase4()
    container.trading_guard_service.engage_kill_switch("ops halt")
    container.pipeline_service.run_daily()
    assert container.trade_repo.list() == []

    container.trading_guard_service.release_kill_switch()
    container.pipeline_service.run_daily()
    assert len(container.trade_repo.list()) == 1  # NVDA executes once resumed


def test_signals_still_produced_while_halted() -> None:
    container = _phase4()
    container.trading_guard_service.engage_kill_switch("ops halt")
    signals = container.pipeline_service.run_daily()
    assert len(signals) >= 1  # the read-only pipeline is unaffected by the guard


def test_guard_does_not_block_below_execution_phase() -> None:
    # Phase 1 has no execution stage, so the guard is simply not wired in.
    container = AppContainer(Settings(phase=SystemPhase.MVP_READ_ONLY))
    signals = container.pipeline_service.run_daily()
    assert len(signals) >= 1
    assert container.trade_repo.list() == []


def test_trading_routes_halt_resume_cycle() -> None:
    client = _client()

    assert client.get("/trading/status").json()["halted"] is False

    halted = client.post("/trading/halt", params={"reason": "manual"})
    assert halted.status_code == 200
    assert halted.json()["kill_switch_enabled"] is True

    status = client.get("/trading/status").json()
    assert status["halted"] is True
    assert status["halt_reason"] == "manual"

    resumed = client.post("/trading/resume")
    assert resumed.status_code == 200
    assert resumed.json()["kill_switch_enabled"] is False
    assert client.get("/trading/status").json()["halted"] is False
