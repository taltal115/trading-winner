"""Account-level safety governor (.cursor/rules.md section 6).

Pure, deterministic circuit-breaker logic that decides whether NEW entries are
allowed. This is a hard account-level gate that sits in front of execution; it
is intentionally separate from the per-trade risk engine (no duplicated logic,
.cursor/rules.md 3.2) and can never be overridden by AI.

Three independent triggers halt new entries:
- Manual kill switch (operator-engaged).
- Daily-loss limit: realized loss today >= ``max_daily_loss`` of equity.
- Loss-streak circuit breaker: ``max_consecutive_losses`` losing trades in a row.

Exits are NOT governed here; open positions must still be closeable while halted.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from app.config.settings import SafetyLimits


class SafetyInputs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kill_switch_enabled: bool
    account_equity: float
    realized_pnl_today: float
    consecutive_losses: int


class SafetyAssessment(BaseModel):
    model_config = ConfigDict(extra="forbid")

    halted: bool
    reasons: list[str]


def evaluate_safety(inputs: SafetyInputs, limits: SafetyLimits) -> SafetyAssessment:
    """Return whether new entries are halted and the human-readable reasons."""
    reasons: list[str] = []

    if inputs.kill_switch_enabled:
        reasons.append("kill switch engaged")

    daily_loss_limit = limits.max_daily_loss * inputs.account_equity
    if inputs.account_equity > 0 and inputs.realized_pnl_today <= -daily_loss_limit:
        reasons.append(
            f"daily loss limit breached "
            f"({inputs.realized_pnl_today:.2f} <= -{daily_loss_limit:.2f})"
        )

    if inputs.consecutive_losses >= limits.max_consecutive_losses:
        reasons.append(
            f"loss-streak circuit breaker "
            f"({inputs.consecutive_losses} >= {limits.max_consecutive_losses})"
        )

    return SafetyAssessment(halted=bool(reasons), reasons=reasons)
