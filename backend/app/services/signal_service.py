"""Signal service: turn feature snapshots into persisted, scored signals.

Phase 1 is quant-only: no AI is consulted (``ai_analysis_id`` stays ``None``).
IGNORE-grade results are not stored as OPEN signals to keep the signal feed
actionable; they remain reproducible from features + the scoring engine.
"""

from __future__ import annotations

from app.engines.scoring_engine import score_features
from app.models.entities import AiAnalysis, FeatureSnapshot, Signal
from app.models.enums import SignalDecision, SignalStatus
from app.repositories.repositories import SignalRepository
from app.services.log_writer import LogWriter
from app.utils.ids import signal_id


class SignalService:
    def __init__(self, signal_repo: SignalRepository, log_writer: LogWriter) -> None:
        self._signals = signal_repo
        self._log = log_writer

    def generate_signal(self, features: FeatureSnapshot) -> Signal | None:
        result = score_features(features)
        if result.decision == SignalDecision.IGNORE:
            self._log.log(
                event="signal_ignored",
                message=f"{features.ticker} scored {result.adjusted_score} (IGNORE)",
                metadata={"ticker": features.ticker, "score": result.adjusted_score},
            )
            return None

        signal = Signal(
            id=signal_id(features.ticker, features.timestamp),
            ticker=features.ticker,
            timestamp=features.timestamp,
            score=result.adjusted_score,
            score_breakdown=result.breakdown,
            expected_return=result.expected_return,
            risk_score=result.risk_score,
            feature_snapshot_id=features.id,
            ai_analysis_id=None,
            decision=result.decision,
            status=SignalStatus.OPEN,
        )
        self._signals.save(signal)
        self._log.log(
            event="signal_created",
            message=f"{features.ticker} -> {result.decision} ({result.adjusted_score})",
            metadata={"signal_id": signal.id, "decision": result.decision},
        )
        return signal

    def generate_for_features(self, features: list[FeatureSnapshot]) -> list[Signal]:
        signals: list[Signal] = []
        for snapshot in features:
            signal = self.generate_signal(snapshot)
            if signal is not None:
                signals.append(signal)
        return signals

    def apply_ai_analysis(
        self, features: FeatureSnapshot, signal: Signal, analysis: AiAnalysis
    ) -> Signal:
        """Re-score the signal with the AI confidence adjustment and link it.

        The scoring engine still owns the decision: AI only supplies a bounded
        ``confidence_adjustment`` that flows through ``score_features``. The AI's
        ``catalyst_direction`` / ``ai_bias`` never set the decision directly.
        """
        result = score_features(features, ai_confidence_adjustment=analysis.confidence_adjustment)
        updated = signal.model_copy(
            update={
                "score": result.adjusted_score,
                "score_breakdown": result.breakdown,
                "expected_return": result.expected_return,
                "risk_score": result.risk_score,
                "decision": result.decision,
                "ai_analysis_id": analysis.id,
            }
        )
        self._signals.save(updated)
        self._log.log(
            event="signal_enriched",
            message=(
                f"{signal.ticker}: {signal.decision}->{result.decision} "
                f"(adj {analysis.confidence_adjustment:+.3f})"
            ),
            metadata={"signal_id": updated.id, "ai_analysis_id": analysis.id},
        )
        return updated

    def get_top_signals(self, limit: int = 20) -> list[Signal]:
        return self._signals.get_top_signals(limit=limit)

    def get_signal(self, signal_id: str) -> Signal | None:
        return self._signals.get(signal_id)
