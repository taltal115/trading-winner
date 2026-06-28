from datetime import UTC, datetime

import pytest

from app.engines.outcome_engine import compute_outcome_metrics


def test_positive_return_is_winner() -> None:
    entry = datetime(2026, 7, 28, 9, 30, tzinfo=UTC)
    exit_ = datetime(2026, 7, 30, 15, 0, tzinfo=UTC)
    metrics = compute_outcome_metrics(
        entry_price=100.0,
        exit_price=112.0,
        entry_time=entry,
        exit_time=exit_,
        realized_pnl=120.0,
    )
    assert metrics.return_pct == pytest.approx(0.12)
    assert metrics.hold_days == 2
    assert metrics.is_winner is True


def test_negative_return_is_loser() -> None:
    entry = datetime(2026, 7, 28, 9, 30, tzinfo=UTC)
    exit_ = datetime(2026, 7, 29, 10, 0, tzinfo=UTC)
    metrics = compute_outcome_metrics(
        entry_price=100.0,
        exit_price=95.0,
        entry_time=entry,
        exit_time=exit_,
        realized_pnl=-50.0,
    )
    assert metrics.return_pct == pytest.approx(-0.05)
    assert metrics.is_winner is False


def test_zero_pnl_is_not_a_winner() -> None:
    entry = datetime(2026, 7, 28, tzinfo=UTC)
    exit_ = datetime(2026, 7, 29, tzinfo=UTC)
    metrics = compute_outcome_metrics(
        entry_price=50.0,
        exit_price=50.0,
        entry_time=entry,
        exit_time=exit_,
        realized_pnl=0.0,
    )
    assert metrics.is_winner is False


def test_rejects_non_positive_entry_price() -> None:
    now = datetime(2026, 7, 28, tzinfo=UTC)
    with pytest.raises(ValueError, match="entry_price"):
        compute_outcome_metrics(
            entry_price=0.0,
            exit_price=10.0,
            entry_time=now,
            exit_time=now,
            realized_pnl=0.0,
        )
