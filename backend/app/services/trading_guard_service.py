"""Trading guard service: account-level safety gate for new entries.

Gathers the live account state (kill switch, today's realized PnL, loss streak),
runs the pure ``safety_engine``, and exposes a single ``assess`` verdict plus
operator controls for the manual kill switch. This is the orchestration layer
for the safety governor; all halting decisions stay in the pure engine.
"""

from __future__ import annotations

from datetime import UTC, datetime

from app.config.settings import SafetyLimits
from app.engines.safety_engine import SafetyAssessment, SafetyInputs, evaluate_safety
from app.models.entities import SystemState
from app.models.enums import LogLevel
from app.repositories.repositories import SystemStateRepository, TradeRepository
from app.services.log_writer import LogWriter
from app.services.portfolio_service import PortfolioService
from app.utils.ids import system_state_id


class TradingGuardService:
    def __init__(
        self,
        system_state_repo: SystemStateRepository,
        trade_repo: TradeRepository,
        portfolio_service: PortfolioService,
        log_writer: LogWriter,
        limits: SafetyLimits,
    ) -> None:
        self._state = system_state_repo
        self._trades = trade_repo
        self._portfolio = portfolio_service
        self._log = log_writer
        self._limits = limits

    def get_state(self) -> SystemState:
        existing = self._state.get(system_state_id())
        if existing is not None:
            return existing
        state = SystemState(id=system_state_id(), updated_at=datetime.now(UTC))
        return self._state.save(state)

    def assess(self) -> SafetyAssessment:
        """Run the safety governor against the current account state."""
        state = self.get_state()
        portfolio = self._portfolio.get_or_create_portfolio()
        inputs = SafetyInputs(
            kill_switch_enabled=state.kill_switch_enabled,
            account_equity=portfolio.equity,
            realized_pnl_today=self._realized_pnl_today(),
            consecutive_losses=self._consecutive_losses(),
        )
        assessment = evaluate_safety(inputs, self._limits)
        if assessment.halted:
            self._log.log(
                event="trading_halted",
                message=f"new entries halted: {assessment.reasons}",
                level=LogLevel.WARNING,
                metadata={"reasons": assessment.reasons},
            )
        return assessment

    def engage_kill_switch(self, reason: str) -> SystemState:
        state = self.get_state()
        updated = state.model_copy(
            update={
                "kill_switch_enabled": True,
                "halt_reason": reason,
                "updated_at": datetime.now(UTC),
            }
        )
        self._state.save(updated)
        self._log.log(
            event="kill_switch_engaged",
            message=f"kill switch engaged: {reason}",
            level=LogLevel.WARNING,
        )
        return updated

    def release_kill_switch(self) -> SystemState:
        state = self.get_state()
        updated = state.model_copy(
            update={
                "kill_switch_enabled": False,
                "halt_reason": None,
                "updated_at": datetime.now(UTC),
            }
        )
        self._state.save(updated)
        self._log.log(
            event="kill_switch_released",
            message="kill switch released; entries re-enabled subject to other limits",
        )
        return updated

    def _realized_pnl_today(self) -> float:
        today = datetime.now(UTC).date()
        total = 0.0
        for trade in self._trades.get_closed():
            if trade.exit_time is not None and trade.exit_time.date() == today:
                total += trade.pnl or 0.0
        return round(total, 2)

    def _consecutive_losses(self) -> int:
        streak = 0
        for trade in self._trades.get_closed():  # most-recent first
            if trade.pnl is not None and trade.pnl < 0:
                streak += 1
            else:
                break
        return streak
