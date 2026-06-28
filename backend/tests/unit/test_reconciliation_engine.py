from app.engines.reconciliation_engine import reconcile


def test_in_sync_when_quantities_match() -> None:
    report = reconcile({"NVDA": 10.0, "AAPL": 5.0}, {"NVDA": 10.0, "AAPL": 5.0})
    assert report.in_sync is True
    assert report.matched == ["AAPL", "NVDA"]
    assert report.discrepancies == []


def test_empty_books_are_in_sync() -> None:
    report = reconcile({}, {})
    assert report.in_sync is True
    assert report.discrepancies == []


def test_quantity_mismatch_detected() -> None:
    report = reconcile({"NVDA": 10.0}, {"NVDA": 8.0})
    assert report.in_sync is False
    assert len(report.discrepancies) == 1
    drift = report.discrepancies[0]
    assert drift.kind == "quantity_mismatch"
    assert drift.internal_quantity == 10.0
    assert drift.broker_quantity == 8.0


def test_missing_at_broker_detected() -> None:
    report = reconcile({"NVDA": 10.0}, {})
    assert report.in_sync is False
    assert report.discrepancies[0].kind == "missing_at_broker"


def test_untracked_internally_detected() -> None:
    report = reconcile({}, {"TSLA": 3.0})
    assert report.in_sync is False
    assert report.discrepancies[0].kind == "untracked_internally"


def test_mixed_drift_is_classified_per_ticker() -> None:
    report = reconcile(
        {"NVDA": 10.0, "AAPL": 5.0, "MSFT": 2.0},
        {"NVDA": 10.0, "AAPL": 4.0, "TSLA": 3.0},
    )
    assert report.matched == ["NVDA"]
    kinds = {d.ticker: d.kind for d in report.discrepancies}
    assert kinds == {
        "AAPL": "quantity_mismatch",
        "MSFT": "missing_at_broker",
        "TSLA": "untracked_internally",
    }
