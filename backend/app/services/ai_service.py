"""AI reasoning service (enrichment only).

Responsibilities:
- Gate AI calls: only when the quant score clears the threshold AND a catalyst
  is present (cost control, AI_PIPELINE.md 2.2 / 10).
- Build structured prompt context, call the provider, validate the response
  against ``AIReasoningOutput`` (no free-text into production logic).
- Clamp ``confidence_adjustment`` to the configured maximum.
- Persist ``ai_analysis/`` with reasoning/prompt/embedding versions.
- On any failure, log and return ``None`` -> the system falls back to the
  quant-only signal. AI NEVER decides a trade.
"""

from __future__ import annotations

from pydantic import ValidationError

from app.config.settings import Settings
from app.engines.catalyst_engine import detect_catalyst
from app.models.ai import AIPromptContext, AIReasoningOutput, NewsContext
from app.models.entities import AiAnalysis, FeatureSnapshot, NewsItem, Signal
from app.models.enums import LogLevel
from app.repositories.repositories import AiAnalysisRepository
from app.services.ai_provider import AIProvider
from app.services.log_writer import LogWriter
from app.services.retrieval_service import RetrievalService
from app.utils.ids import ai_analysis_id


class AIService:
    def __init__(
        self,
        ai_repo: AiAnalysisRepository,
        log_writer: LogWriter,
        provider: AIProvider,
        settings: Settings,
        retrieval_service: RetrievalService | None = None,
    ) -> None:
        self._ai = ai_repo
        self._log = log_writer
        self._provider = provider
        self._settings = settings
        self._retrieval = retrieval_service

    def analyze_signal(
        self,
        signal: Signal,
        features: FeatureSnapshot,
        news: list[NewsItem],
    ) -> AiAnalysis | None:
        if signal.score < self._settings.ai_score_threshold:
            return None

        catalyst = detect_catalyst(news)
        if not catalyst.detected:
            self._log.log(
                event="ai_skipped_no_catalyst",
                message=f"{signal.ticker}: no catalyst, AI not called",
                metadata={"ticker": signal.ticker},
            )
            return None

        context = AIPromptContext(
            ticker=signal.ticker,
            news=[
                NewsContext(headline=n.headline, source=n.source, sentiment=n.sentiment)
                for n in news
            ],
            price_change=features.momentum.daily_return,
            volume_spike=features.volume.relative_volume,
            sector_trend="unknown",
            feature_summary={
                "rsi": features.technical.rsi,
                "macd": features.technical.macd,
                "relative_volume": features.volume.relative_volume,
            },
            catalyst_type=catalyst.catalyst_type,
            retrieved_context=self._retrieve_context(signal.ticker, news),
        )

        try:
            raw = self._provider.analyze(context)
            output = AIReasoningOutput.model_validate(raw)
        except (ValidationError, ValueError, KeyError, RuntimeError) as exc:
            self._log.log(
                event="ai_failed",
                message=f"{signal.ticker}: AI failed, falling back to quant-only: {exc}",
                level=LogLevel.ERROR,
                metadata={"ticker": signal.ticker},
            )
            return None

        analysis = self._build_analysis(signal, output)
        self._ai.save(analysis)
        self._log.log(
            event="ai_analysis_created",
            message=f"{signal.ticker}: {output.catalyst_direction} (bias {output.ai_bias})",
            metadata={"ai_analysis_id": analysis.id, "signal_id": signal.id},
        )
        return analysis

    def _retrieve_context(self, ticker: str, news: list[NewsItem]) -> list[str]:
        if self._retrieval is None:
            return []
        return self._retrieval.retrieve(ticker, [item.headline for item in news])

    def _build_analysis(self, signal: Signal, output: AIReasoningOutput) -> AiAnalysis:
        cap = self._settings.ai_max_confidence_adjustment
        clamped = max(-cap, min(cap, output.confidence_adjustment))
        embedding_version = (
            self._retrieval.embedding_version if self._retrieval is not None else "v1"
        )
        return AiAnalysis(
            id=ai_analysis_id(signal.ticker, signal.timestamp),
            related_id=signal.id,
            ticker=signal.ticker,
            summary=output.summary,
            catalyst_type=output.catalyst_type,
            catalyst_direction=output.catalyst_direction,
            ai_bias=output.ai_bias,
            sentiment=output.sentiment,
            key_insights=output.key_insights,
            risk_factors=output.risk_factors,
            confidence=output.confidence,
            confidence_adjustment=clamped,
            reasoning_version=self._provider.reasoning_version,
            prompt_version=self._provider.prompt_version,
            embedding_version=embedding_version,
        )

    def list_analyses(self) -> list[AiAnalysis]:
        return self._ai.list()

    def get_analysis(self, analysis_id: str) -> AiAnalysis | None:
        return self._ai.get(analysis_id)
