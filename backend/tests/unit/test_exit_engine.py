import pytest

from app.engines.exit_engine import compute_stop_distance, evaluate_exit
from app.models.enums import ExitReason


def test_stop_distance_picks_tighter() -> None:
    # 2*ATR = 4 vs 5% of 100 = 5 -> tighter is 4.
    assert compute_stop_distance(100.0, 2.0) == pytest.approx(4.0)
    # 2*ATR = 20 vs 5% of 100 = 5 -> tighter is 5.
    assert compute_stop_distance(100.0, 10.0) == pytest.approx(5.0)


def _eval(close: float, sma_20: float = 10.0, sma_50: float = 9.0, days: int = 1) -> object:
    return evaluate_exit(
        current_close=close,
        stop_price=90.0,
        target_price=112.0,
        sma_20=sma_20,
        sma_50=sma_50,
        holding_days=days,
        max_hold_days=10,
    )


def test_stop_loss_triggers() -> None:
    assert _eval(89.0) == ExitReason.STOP_LOSS


def test_profit_target_triggers() -> None:
    assert _eval(112.0) == ExitReason.PROFIT_TARGET


def test_time_exit_triggers() -> None:
    assert _eval(100.0, days=10) == ExitReason.TIME


def test_momentum_failure_triggers() -> None:
    assert _eval(100.0, sma_20=8.0, sma_50=9.0) == ExitReason.MOMENTUM_FAILURE


def test_hold_when_no_condition_met() -> None:
    assert _eval(100.0) is None
