"""Outcome service: materialize learning-loop records when trades close.

When the learning loop is enabled (Phase 6+), every closed trade produces an
append-only ``outcomes/`` document that captures the full traceability chain
and deterministic attribution metrics. The service is idempotent: re-processing
the same trade never creates a duplicate outcome.

This layer never influences trading decisions — it only records what happened
so the system can improve over time (PROJECT.md section 10).
"""

from __future__ import annotations

from app.engines.outcome_engine import OutcomeInputs, compute_outcome_metrics
from app.models.entities import AiAnalysis, Signal, Trade, TradeOutcome
from app.models.enums import LogLevel, TradeStatus
from app.repositories.repositories import (
    AiAnalysisRepository,
    OutcomeRepository,
    SignalRepository,
    TradeRepository,
)
from app.services.log_writer import LogWriter
from app.utils.ids import outcome_id


class OutcomeService:
    def __init__(
        self,
        outcome_repo: OutcomeRepository,
        trade_repo: TradeRepository,
        signal_repo: SignalRepository,
        ai_repo: AiAnalysisRepository,
        log_writer: LogWriter,
    ) -> None:
        self._outcomes = outcome_repo
        self._trades = trade_repo
        self._signals = signal_repo
        self._ai = ai_repo
        self._log = log_writer

    def record_from_close(self, trade: Trade, exit_reason: str) -> TradeOutcome | None:
        """Persist a learning outcome for a freshly closed trade (idempotent)."""
        if trade.status != TradeStatus.CLOSED:
            return None
        if trade.exit_time is None or trade.exit_price is None or trade.pnl is None:
            self._log.log(
                event="outcome_skipped_incomplete_trade",
                message=f"{trade.id}: missing exit fields",
                level=LogLevel.WARNING,
                metadata={"trade_id": trade.id},
            )
            return None

        existing = self._outcomes.get_for_trade(trade.id)
        if existing is not None:
            return existing

        signal = self._signals.get(trade.signal_id)
        if signal is None:
            self._log.log(
                event="outcome_skipped_missing_signal",
                message=f"{trade.id}: signal {trade.signal_id} not found",
                level=LogLevel.ERROR,
                metadata={"trade_id": trade.id},
            )
            return None

        analysis = self._load_analysis(trade.ai_analysis_id)
        metrics = compute_outcome_metrics(
            entry_price=trade.entry_price,
            exit_price=trade.exit_price,
            entry_time=trade.entry_time,
            exit_time=trade.exit_time,
            realized_pnl=trade.pnl,
        )
        outcome = TradeOutcome(
            id=outcome_id(trade.ticker, trade.exit_time),
            trade_id=trade.id,
            ticker=trade.ticker,
            signal_id=trade.signal_id,
            feature_snapshot_id=trade.feature_snapshot_id,
            ai_analysis_id=trade.ai_analysis_id,
            risk_decision_id=trade.risk_decision_id,
            fundamental_id=signal.fundamental_id,
            market_regime_id=signal.market_regime_id,
            entry_time=trade.entry_time,
            exit_time=trade.exit_time,
            entry_price=trade.entry_price,
            exit_price=trade.exit_price,
            quantity=trade.quantity,
            realized_pnl=trade.pnl,
            return_pct=metrics.return_pct,
            hold_days=metrics.hold_days,
            is_winner=metrics.is_winner,
            exit_reason=exit_reason,
            entry_score=signal.score,
            ai_bias=analysis.ai_bias if analysis else None,
            ai_confidence_adjustment=analysis.confidence_adjustment if analysis else None,
        )
        self._outcomes.save(outcome)
        self._log.log(
            event="outcome_recorded",
            message=(
                f"{trade.ticker}: pnl={trade.pnl:.2f} return={metrics.return_pct:.2%} "
                f"reason={exit_reason}"
            ),
            metadata={"outcome_id": outcome.id, "trade_id": trade.id},
        )
        return outcome

    def process_pending(self) -> list[TradeOutcome]:
        """Backfill outcomes for any closed trades that lack a record yet."""
        recorded: list[TradeOutcome] = []
        for trade in self._trades.get_closed():
            if self._outcomes.get_for_trade(trade.id) is not None:
                continue
            outcome = self.record_from_close(trade, exit_reason="backfill")
            if outcome is not None:
                recorded.append(outcome)
        return recorded

    def list_outcomes(self) -> list[TradeOutcome]:
        return sorted(self._outcomes.list(), key=lambda o: o.exit_time, reverse=True)

    def get_outcome(self, outcome_id_value: str) -> TradeOutcome | None:
        return self._outcomes.get(outcome_id_value)

    def _load_analysis(self, analysis_id: str | None) -> AiAnalysis | None:
        if not analysis_id:
            return None
        return self._ai.get(analysis_id)

    @staticmethod
    def build_inputs(
        trade: Trade,
        signal: Signal,
        exit_reason: str,
        analysis: AiAnalysis | None,
    ) -> OutcomeInputs:
        """Expose input assembly for tests without persisting."""
        return OutcomeInputs(
            trade_id=trade.id,
            ticker=trade.ticker,
            signal_id=trade.signal_id,
            feature_snapshot_id=trade.feature_snapshot_id,
            ai_analysis_id=trade.ai_analysis_id,
            risk_decision_id=trade.risk_decision_id,
            fundamental_id=signal.fundamental_id,
            market_regime_id=signal.market_regime_id,
            entry_time=trade.entry_time,
            exit_time=trade.exit_time or trade.entry_time,
            entry_price=trade.entry_price,
            exit_price=trade.exit_price or trade.entry_price,
            quantity=trade.quantity,
            realized_pnl=trade.pnl or 0.0,
            fees=trade.fees,
            exit_reason=exit_reason,
            entry_score=signal.score,
            ai_bias=analysis.ai_bias if analysis else None,
            ai_confidence_adjustment=analysis.confidence_adjustment if analysis else None,
        )
