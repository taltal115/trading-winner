"""Daily pipeline orchestration.

Flow: ingest universe -> features -> (Stage 4.5) Fundamental Engine ->
(Stage 4.6) Market Regime Engine -> quant signals (quality-biased) ->
(Phase 3+) AI enrichment -> (Phase 4+) risk evaluation + paper execution. Each
later stage is wired in only when the container decides the phase/flags warrant
it, so the same orchestrator serves every phase without branching on globals.

The Fundamental and Market Regime stages are additive and gated by settings
flags that default OFF; when disabled the orchestrator behaves byte-for-byte as
before (no fundamentals computed, regime multiplier effectively 1.0).
"""

from __future__ import annotations

from datetime import UTC, datetime

from app.engines.fundamental_engine import FUNDAMENTAL_VETO_SCORE
from app.models.entities import FeatureSnapshot, FundamentalSnapshot, MarketRegimeSnapshot, Signal
from app.services.ai_service import AIService
from app.services.execution_service import ExecutionService
from app.services.feature_service import FeatureService
from app.services.fundamental_service import FundamentalService
from app.services.ingestion_service import IngestionService
from app.services.log_writer import LogWriter
from app.services.market_data import MarketDataSource
from app.services.market_regime_service import MarketRegimeService
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
        fundamental_service: FundamentalService | None = None,
        market_regime_service: MarketRegimeService | None = None,
        fundamental_min_score: float = FUNDAMENTAL_VETO_SCORE,
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
        self._fundamentals = fundamental_service
        self._regime = market_regime_service
        self._fundamental_min_score = fundamental_min_score

    def run_daily(self) -> list[Signal]:
        survivors = self._ingestion.ingest_universe()
        tickers = [c.ticker for c in survivors]
        features = self._features.build_for_tickers(tickers)
        features_by_ticker = {f.ticker: f for f in features}
        as_of = features[0].timestamp if features else datetime.now(UTC)

        # Stage 4.5 (gated): fundamentals per surviving ticker.
        fundamentals: dict[str, FundamentalSnapshot] = {}
        if self._fundamentals is not None and features:
            fundamentals = self._fundamentals.compute_for_tickers(
                [f.ticker for f in features], as_of
            )

        # Stage 4.6 (gated): market regime, once per run.
        regime: MarketRegimeSnapshot | None = None
        if self._regime is not None:
            regime = self._regime.compute_regime(as_of)

        signals = self._signals.generate_for_features(
            features,
            fundamentals=fundamentals or None,
            market_regime_id=regime.id if regime is not None else None,
            min_score=self._fundamental_min_score,
        )

        enriched = 0
        if self._ai is not None and self._news is not None:
            signals = [
                self._maybe_enrich(
                    signal,
                    features_by_ticker[signal.ticker],
                    fundamentals.get(signal.ticker),
                    regime,
                )
                for signal in signals
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
                executed = self._run_execution(signals, features_by_ticker, regime)

        self._log.log(
            event="pipeline_completed",
            message=(
                f"universe={len(survivors)} features={len(features)} "
                f"signals={len(signals)} ai_enriched={enriched} executed={executed}"
            ),
            metadata={"signal_ids": [s.id for s in signals]},
        )
        return signals

    def _maybe_enrich(
        self,
        signal: Signal,
        features: FeatureSnapshot,
        fundamental: FundamentalSnapshot | None,
        regime: MarketRegimeSnapshot | None,
    ) -> Signal:
        assert self._ai is not None and self._news is not None
        news = self._news.ingest_for_ticker(signal.ticker)
        analysis = self._ai.analyze_signal(
            signal,
            features,
            news,
            fundamental_score=fundamental.fundamental_score if fundamental is not None else None,
            regime_state=regime.regime_state.value if regime is not None else None,
        )
        if analysis is None:
            return signal
        return self._signals.apply_ai_analysis(
            features,
            signal,
            analysis,
            fundamental=fundamental,
            min_score=self._fundamental_min_score,
        )

    def _run_execution(
        self,
        signals: list[Signal],
        features_by_ticker: dict[str, FeatureSnapshot],
        regime: MarketRegimeSnapshot | None,
    ) -> int:
        assert self._risk is not None and self._execution is not None and self._source is not None
        executed = 0
        for signal in signals:
            features = features_by_ticker[signal.ticker]
            reference_price = self._source.get_price_history(signal.ticker)[-1].close
            decision = self._risk.evaluate(signal, features, reference_price, regime)
            if not decision.approved:
                continue
            trade = self._execution.execute(signal, features, decision, reference_price)
            if trade is not None:
                executed += 1
        return executed
