"""Referential integrity + execution-dependency enforcement.

Encodes the data-integrity rules from DATABASE.md and .cursor/rules.md:

- Every signal must reference an existing feature snapshot.
- Every trade must reference an existing signal and feature snapshot.
- Phase 3+: a trade must reference an existing ai_analysis before execution.
- Phase 4+: a trade must reference a risk_decision before execution.
- Every ai_analysis must reference a signal or trade. No orphans.
"""

from __future__ import annotations

from app.config.settings import Settings
from app.models.entities import Signal, Trade
from app.repositories.repositories import (
    AiAnalysisRepository,
    FeatureRepository,
    SignalRepository,
    TradeRepository,
)


class IntegrityError(Exception):
    """Raised when a record violates referential integrity rules."""


class IntegrityService:
    def __init__(
        self,
        feature_repo: FeatureRepository,
        signal_repo: SignalRepository,
        trade_repo: TradeRepository,
        ai_repo: AiAnalysisRepository,
    ) -> None:
        self._features = feature_repo
        self._signals = signal_repo
        self._trades = trade_repo
        self._ai = ai_repo

    def check_signal(self, signal: Signal) -> list[str]:
        violations: list[str] = []
        if self._features.get(signal.feature_snapshot_id) is None:
            violations.append(
                f"signal {signal.id} references missing feature " f"{signal.feature_snapshot_id}"
            )
        if signal.ai_analysis_id and self._ai.get(signal.ai_analysis_id) is None:
            violations.append(
                f"signal {signal.id} references missing ai_analysis " f"{signal.ai_analysis_id}"
            )
        return violations

    def check_trade(self, trade: Trade) -> list[str]:
        violations: list[str] = []
        if self._signals.get(trade.signal_id) is None:
            violations.append(f"trade {trade.id} references missing signal {trade.signal_id}")
        if self._features.get(trade.feature_snapshot_id) is None:
            violations.append(
                f"trade {trade.id} references missing feature {trade.feature_snapshot_id}"
            )
        if trade.ai_analysis_id and self._ai.get(trade.ai_analysis_id) is None:
            violations.append(
                f"trade {trade.id} references missing ai_analysis {trade.ai_analysis_id}"
            )
        return violations

    def find_orphans(self) -> list[str]:
        violations: list[str] = []
        for signal in self._signals.list():
            violations.extend(self.check_signal(signal))
        for trade in self._trades.list():
            violations.extend(self.check_trade(trade))
        for analysis in self._ai.list():
            related = analysis.related_id
            if self._signals.get(related) is None and self._trades.get(related) is None:
                violations.append(f"ai_analysis {analysis.id} is orphaned (related_id {related})")
        return violations

    def assert_trade_executable(self, trade: Trade, settings: Settings) -> None:
        """Hard gate before any execution. Raises IntegrityError if not allowed."""
        missing: list[str] = []
        if self._signals.get(trade.signal_id) is None:
            missing.append("signal_id")
        if self._features.get(trade.feature_snapshot_id) is None:
            missing.append("feature_snapshot_id")
        if settings.ai_required_for_execution:
            if not trade.ai_analysis_id or self._ai.get(trade.ai_analysis_id) is None:
                missing.append("ai_analysis_id")
        if settings.risk_required_for_execution and not trade.risk_decision_id:
            missing.append("risk_decision_id")
        if missing:
            raise IntegrityError(
                f"trade {trade.id} not executable in phase "
                f"{int(settings.phase)}; missing: {', '.join(missing)}"
            )
