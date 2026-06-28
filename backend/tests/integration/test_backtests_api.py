from fastapi.testclient import TestClient

from app.api.dependencies import get_container
from app.main import create_app


def _client() -> TestClient:
    get_container.cache_clear()
    return TestClient(create_app())


def test_run_backtest_then_list_and_get() -> None:
    client = _client()
    run = client.post(
        "/backtests/run",
        json={"tickers": ["NVDA", "AAPL", "XYZ"], "strategy": "momentum_catalyst_v1"},
    )
    assert run.status_code == 200
    body = run.json()
    assert body["trade_count"] >= 1
    assert set(body["metrics"]) == {"sharpe", "win_rate", "max_drawdown", "total_return"}
    assert body["id"].startswith("backtest_momentum_catalyst_v1_")

    listed = client.get("/backtests")
    assert listed.status_code == 200
    assert any(b["id"] == body["id"] for b in listed.json())

    fetched = client.get(f"/backtests/{body['id']}")
    assert fetched.status_code == 200
    assert fetched.json()["strategy"] == "momentum_catalyst_v1"


def test_get_missing_backtest_404() -> None:
    client = _client()
    resp = client.get("/backtests/backtest_missing_2024-01-01")
    assert resp.status_code == 404


def test_run_backtest_requires_tickers() -> None:
    client = _client()
    resp = client.post("/backtests/run", json={"tickers": []})
    assert resp.status_code == 422
