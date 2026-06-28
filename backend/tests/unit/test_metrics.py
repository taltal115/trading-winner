import pytest

from app.utils import metrics


def test_total_return_compounds() -> None:
    assert metrics.total_return([0.1, 0.1]) == pytest.approx(0.21)


def test_total_return_empty_is_zero() -> None:
    assert metrics.total_return([]) == 0.0


def test_equity_curve_values() -> None:
    assert metrics.equity_curve([0.5, -0.5]) == pytest.approx([1.5, 0.75])


def test_max_drawdown_peak_to_trough() -> None:
    assert metrics.max_drawdown([0.5, -0.5]) == pytest.approx(0.5)


def test_max_drawdown_monotonic_up_is_zero() -> None:
    assert metrics.max_drawdown([0.1, 0.1, 0.1]) == pytest.approx(0.0)


def test_sharpe_zero_when_no_variance() -> None:
    assert metrics.sharpe_ratio([0.1, 0.1, 0.1]) == 0.0


def test_sharpe_positive_for_positive_drift() -> None:
    assert metrics.sharpe_ratio([0.01, -0.005, 0.02, 0.0, 0.015]) > 0
