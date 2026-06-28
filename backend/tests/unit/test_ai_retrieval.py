"""Tests that the AIService injects RAG context and records the embedding version.

Verifies the wiring is enrichment-only: retrieved context reaches the prompt the
provider sees, the embedding version is persisted for reproducibility, and a
``None`` retrieval service leaves the legacy (empty-context) behavior intact.
"""

from __future__ import annotations

from datetime import UTC, datetime

from app.config.settings import Settings, SystemPhase
from app.models.ai import AIPromptContext
from app.models.entities import (
    FeatureSnapshot,
    MomentumFeatures,
    NewsItem,
    ScoreBreakdown,
    Signal,
    TechnicalFeatures,
    VolatilityFeatures,
    VolumeFeatures,
)
from app.models.enums import Sentiment, SignalDecision, SignalStatus
from app.repositories.base import InMemoryDocumentStore
from app.repositories.repositories import (
    AiAnalysisRepository,
    EmbeddingRepository,
    LogRepository,
    NewsRepository,
)
from app.services.ai_service import AIService
from app.services.embedding_provider import MockEmbeddingProvider
from app.services.log_writer import LogWriter
from app.services.retrieval_service import RetrievalService

TS = datetime(2026, 7, 28, 10, 5, 0, tzinfo=UTC)


class _CapturingProvider:
    reasoning_version = "test-v1"
    prompt_version = "1.0"

    def __init__(self) -> None:
        self.seen_context: list[str] = []

    def analyze(self, context: AIPromptContext) -> dict[str, object]:
        self.seen_context = context.retrieved_context
        return {
            "ticker": context.ticker,
            "catalyst_type": context.catalyst_type.value,
            "catalyst_direction": "bullish",
            "ai_bias": 0.2,
            "sentiment": "positive",
            "summary": "ok",
            "key_insights": [],
            "risk_factors": [],
            "confidence": 0.7,
            "confidence_adjustment": 0.05,
        }


def _features() -> FeatureSnapshot:
    return FeatureSnapshot(
        id="feature_NVDA_2026-07-28",
        ticker="NVDA",
        timestamp=TS,
        technical=TechnicalFeatures(rsi=60, macd=1.0, atr=4.0, sma_20=10, sma_50=9, sma_200=8),
        volume=VolumeFeatures(relative_volume=2.0, avg_volume=1_000_000),
        momentum=MomentumFeatures(daily_return=0.01, weekly_return=0.05, monthly_return=0.1),
        volatility=VolatilityFeatures(std_dev=0.02, bollinger_width=0.08),
    )


def _signal() -> Signal:
    return Signal(
        id="signal_NVDA_2026-07-28",
        ticker="NVDA",
        timestamp=TS,
        score=60,
        score_breakdown=ScoreBreakdown(
            momentum_score=60,
            volume_score=60,
            catalyst_score=0,
            sector_strength=50,
            volatility_breakout=50,
            macro_alignment=50,
        ),
        expected_return=0.04,
        risk_score=0.2,
        feature_snapshot_id="feature_NVDA_2026-07-28",
        decision=SignalDecision.WATCH,
        status=SignalStatus.OPEN,
    )


def _news(seq: int, headline: str) -> NewsItem:
    return NewsItem(
        id=f"news_NVDA_2026-07-28_{seq}",
        ticker="NVDA",
        timestamp=TS,
        headline=headline,
        source="Reuters",
        sentiment=Sentiment.POSITIVE,
        relevance_score=0.9,
    )


def _build(provider: _CapturingProvider, with_retrieval: bool) -> tuple[AIService, NewsRepository]:
    store = InMemoryDocumentStore()
    news_repo = NewsRepository(store)
    ai_repo = AiAnalysisRepository(store)
    log = LogWriter("ai_pipeline", LogRepository(store))
    settings = Settings(phase=SystemPhase.AI_INTEGRATION)
    retrieval = (
        RetrievalService(
            news_repo,
            ai_repo,
            EmbeddingRepository(store),
            MockEmbeddingProvider(),
            LogWriter("retrieval_service", LogRepository(store)),
        )
        if with_retrieval
        else None
    )
    service = AIService(ai_repo, log, provider, settings, retrieval_service=retrieval)  # type: ignore[arg-type]
    return service, news_repo


def test_retrieved_context_reaches_provider_and_sets_embedding_version() -> None:
    provider = _CapturingProvider()
    service, news_repo = _build(provider, with_retrieval=True)
    # Historical precedent in the corpus that the current event should retrieve.
    news_repo.save(_news(1, "nvidia ai chip demand surges on cloud capex"))

    analysis = service.analyze_signal(
        _signal(), _features(), [_news(2, "NVIDIA announces new ai chip partnership")]
    )
    assert analysis is not None
    assert provider.seen_context == ["nvidia ai chip demand surges on cloud capex"]
    assert analysis.embedding_version == "mock-embed-v1"


def test_without_retrieval_context_is_empty_and_version_default() -> None:
    provider = _CapturingProvider()
    service, _ = _build(provider, with_retrieval=False)
    analysis = service.analyze_signal(
        _signal(), _features(), [_news(2, "NVIDIA announces new ai chip partnership")]
    )
    assert analysis is not None
    assert provider.seen_context == []
    assert analysis.embedding_version == "v1"
