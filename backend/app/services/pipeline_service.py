"""Daily pipeline orchestration.

Flow: ingest universe -> features -> quant signals -> (Phase 3+) AI enrichment
-> (Phase 4+) risk evaluation + paper execution. Each later stage is wired in
only when the container decides the phase warrants it, so the same orchestrator
serves every phase without branching on globals.
"""

from __future__ import annotations

from app.models.entities import FeatureSnapshot, Signal
from app.services.ai_service import AIService
from app.services.execution_service import ExecutionService
from app.services.feature_service import FeatureService
from app.services.ingestion_service import IngestionService
from app.services.log_writer import LogWriter
from app.services.market_data import MarketDataSource
from app.services.news_service import NewsService
from app.services.risk_service import RiskService
from app.services.signal_service import SignalService
from app.services.trading_guard_service import TradingGuardService


class PipelineService:
    def __init__(
        self,
        ingestion: IngestionService,
        feature_service: FeatureService,
        signal_service: SignalService,
        log_writer: LogWriter,
        news_service: NewsService | None = None,
        ai_service: AIService | None = None,
        risk_service: RiskService | None = None,
        execution_service: ExecutionService | None = None,
        source: MarketDataSource | None = None,
        trading_guard: TradingGuardService | None = None,
    ) -> None:
        self._ingestion = ingestion
        self._features = feature_service
        self._signals = signal_service
        self._log = log_writer
        self._news = news_service
        self._ai = ai_service
        self._risk = risk_service
        self._execution = execution_service
        self._source = source
        self._guard = trading_guard

    def run_daily(self) -> list[Signal]:
        survivors = self._ingestion.ingest_universe()
        tickers = [c.ticker for c in survivors]
        features = self._features.build_for_tickers(tickers)
        signals = self._signals.generate_for_features(features)
        features_by_ticker = {f.ticker: f for f in features}

        enriched = 0
        if self._ai is not None and self._news is not None:
            signals = [
                self._maybe_enrich(signal, features_by_ticker[signal.ticker]) for signal in signals
            ]
            enriched = sum(1 for s in signals if s.ai_analysis_id is not None)

        executed = 0
        if self._execution is not None and self._risk is not None and self._source is not None:
            if self._guard is not None and self._guard.assess().halted:
                self._log.log(
                    event="execution_stage_halted",
                    message="safety guard halted new entries; skipping execution stage",
                )
            else:
                executed = self._run_execution(signals, features_by_ticker)

        self._log.log(
            event="pipeline_completed",
            message=(
                f"universe={len(survivors)} features={len(features)} "
                f"signals={len(signals)} ai_enriched={enriched} executed={executed}"
            ),
            metadata={"signal_ids": [s.id for s in signals]},
        )
        return signals

    def _maybe_enrich(self, signal: Signal, features: FeatureSnapshot) -> Signal:
        assert self._ai is not None and self._news is not None
        news = self._news.ingest_for_ticker(signal.ticker)
        analysis = self._ai.analyze_signal(signal, features, news)
        if analysis is None:
            return signal
        return self._signals.apply_ai_analysis(features, signal, analysis)

    def _run_execution(
        self,
        signals: list[Signal],
        features_by_ticker: dict[str, FeatureSnapshot],
    ) -> int:
        assert self._risk is not None and self._execution is not None and self._source is not None
        executed = 0
        for signal in signals:
            features = features_by_ticker[signal.ticker]
            reference_price = self._source.get_price_history(signal.ticker)[-1].close
            decision = self._risk.evaluate(signal, features, reference_price)
            if not decision.approved:
                continue
            trade = self._execution.execute(signal, features, decision, reference_price)
            if trade is not None:
                executed += 1
        return executed
