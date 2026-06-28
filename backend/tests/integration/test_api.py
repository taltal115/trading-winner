from fastapi.testclient import TestClient

from app.api.dependencies import get_container
from app.main import create_app


def _client() -> TestClient:
    get_container.cache_clear()
    return TestClient(create_app())


def test_health() -> None:
    resp = _client().get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["phase"] == 1


def test_pipeline_run_then_list_signals() -> None:
    client = _client()
    run = client.post("/pipeline/run")
    assert run.status_code == 200
    signals = run.json()
    assert len(signals) >= 1

    # Every signal must trace back to a feature snapshot and carry no AI in Phase 1.
    for signal in signals:
        assert signal["feature_snapshot_id"].startswith("feature_")
        assert signal["ai_analysis_id"] is None
        assert signal["decision"] != "IGNORE"

    listed = client.get("/signals", params={"limit": 10})
    assert listed.status_code == 200
    scores = [s["score"] for s in listed.json()]
    assert scores == sorted(scores, reverse=True)


def test_get_single_signal_and_404() -> None:
    client = _client()
    created = client.post("/pipeline/run").json()
    signal_id = created[0]["id"]
    assert client.get(f"/signals/{signal_id}").status_code == 200
    assert client.get("/signals/signal_MISSING_2026-07-28").status_code == 404


def test_integrity_clean_after_pipeline() -> None:
    client = _client()
    client.post("/pipeline/run")
    resp = client.get("/system/integrity")
    assert resp.status_code == 200
    assert resp.json() == {"ok": True, "violations": []}
