from app.config.settings import SafetyLimits
from app.engines.safety_engine import SafetyInputs, evaluate_safety

LIMITS = SafetyLimits(max_daily_loss=0.06, max_consecutive_losses=4)


def _inputs(
    kill: bool = False,
    equity: float = 100_000.0,
    pnl_today: float = 0.0,
    losses: int = 0,
) -> SafetyInputs:
    return SafetyInputs(
        kill_switch_enabled=kill,
        account_equity=equity,
        realized_pnl_today=pnl_today,
        consecutive_losses=losses,
    )


def test_allows_trading_when_within_limits() -> None:
    result = evaluate_safety(_inputs(pnl_today=-1000.0, losses=2), LIMITS)
    assert result.halted is False
    assert result.reasons == []


def test_kill_switch_halts() -> None:
    result = evaluate_safety(_inputs(kill=True), LIMITS)
    assert result.halted is True
    assert any("kill switch" in r for r in result.reasons)


def test_daily_loss_limit_halts_at_threshold() -> None:
    # -6% of 100k = -6000 -> exactly at the limit halts.
    result = evaluate_safety(_inputs(pnl_today=-6000.0), LIMITS)
    assert result.halted is True
    assert any("daily loss" in r for r in result.reasons)


def test_daily_loss_within_limit_allows() -> None:
    result = evaluate_safety(_inputs(pnl_today=-5999.99), LIMITS)
    assert result.halted is False


def test_loss_streak_halts() -> None:
    result = evaluate_safety(_inputs(losses=4), LIMITS)
    assert result.halted is True
    assert any("loss-streak" in r for r in result.reasons)


def test_profit_today_never_halts_on_loss_rules() -> None:
    result = evaluate_safety(_inputs(pnl_today=5000.0, losses=1), LIMITS)
    assert result.halted is False


def test_zero_equity_does_not_trigger_daily_loss() -> None:
    # Guard against div-by-relative comparison when equity is unset.
    result = evaluate_safety(_inputs(equity=0.0, pnl_today=-10.0), LIMITS)
    assert all("daily loss" not in r for r in result.reasons)
