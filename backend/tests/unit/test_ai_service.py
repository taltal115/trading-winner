from datetime import datetime

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
from app.repositories.repositories import AiAnalysisRepository, LogRepository
from app.services.ai_provider import MockAIProvider
from app.services.ai_service import AIService
from app.services.log_writer import LogWriter

TICKER = "NVDA"
TS = datetime(2026, 7, 28, 10, 5, 0)


def _features() -> FeatureSnapshot:
    return FeatureSnapshot(
        id="feature_NVDA_2026-07-28",
        ticker=TICKER,
        timestamp=TS,
        technical=TechnicalFeatures(rsi=60, macd=1.0, atr=4.0, sma_20=10, sma_50=9, sma_200=8),
        volume=VolumeFeatures(relative_volume=2.0, avg_volume=1_000_000),
        momentum=MomentumFeatures(daily_return=0.01, weekly_return=0.05, monthly_return=0.1),
        volatility=VolatilityFeatures(std_dev=0.02, bollinger_width=0.08),
    )


def _signal(score: float) -> Signal:
    return Signal(
        id="signal_NVDA_2026-07-28",
        ticker=TICKER,
        timestamp=TS,
        score=score,
        score_breakdown=ScoreBreakdown(
            momentum_score=score,
            volume_score=score,
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


def _news(headline: str, sentiment: Sentiment = Sentiment.POSITIVE) -> NewsItem:
    return NewsItem(
        id="news_NVDA_2026-07-28_1",
        ticker=TICKER,
        timestamp=TS,
        headline=headline,
        source="Reuters",
        sentiment=sentiment,
        relevance_score=0.9,
    )


def _service(provider: object | None = None) -> tuple[AIService, AiAnalysisRepository]:
    store = InMemoryDocumentStore()
    ai_repo = AiAnalysisRepository(store)
    log = LogWriter("ai_pipeline", LogRepository(store))
    settings = Settings(phase=SystemPhase.AI_INTEGRATION)
    service = AIService(ai_repo, log, provider or MockAIProvider(), settings)  # type: ignore[arg-type]
    return service, ai_repo


def test_skips_when_below_score_threshold() -> None:
    service, ai_repo = _service()
    result = service.analyze_signal(_signal(40), _features(), [_news("announces partnership")])
    assert result is None
    assert ai_repo.list() == []


def test_skips_when_no_catalyst() -> None:
    service, ai_repo = _service()
    result = service.analyze_signal(_signal(60), _features(), [_news("trades sideways")])
    assert result is None
    assert ai_repo.list() == []


def test_creates_analysis_when_gated_in() -> None:
    service, ai_repo = _service()
    analysis = service.analyze_signal(
        _signal(60), _features(), [_news("NVIDIA announces partnership")]
    )
    assert analysis is not None
    assert analysis.related_id == "signal_NVDA_2026-07-28"
    assert analysis.catalyst_direction.value == "bullish"
    assert len(ai_repo.list()) == 1


def test_confidence_adjustment_is_clamped() -> None:
    class _BigAdjustmentProvider:
        reasoning_version = "test-v1"
        prompt_version = "1.0"

        def analyze(self, context: AIPromptContext) -> dict[str, object]:
            return {
                "ticker": context.ticker,
                "catalyst_type": context.catalyst_type.value,
                "catalyst_direction": "bullish",
                "ai_bias": 0.9,
                "sentiment": "positive",
                "summary": "x",
                "key_insights": [],
                "risk_factors": [],
                "confidence": 0.9,
                "confidence_adjustment": 0.9,
            }

    service, _ = _service(_BigAdjustmentProvider())
    analysis = service.analyze_signal(_signal(60), _features(), [_news("announces partnership")])
    assert analysis is not None
    assert analysis.confidence_adjustment == 0.2  # clamped to ai_max_confidence_adjustment


def test_provider_failure_falls_back_to_quant_only() -> None:
    class _FailingProvider:
        reasoning_version = "test-v1"
        prompt_version = "1.0"

        def analyze(self, context: AIPromptContext) -> dict[str, object]:
            raise RuntimeError("model timeout")

    service, ai_repo = _service(_FailingProvider())
    result = service.analyze_signal(_signal(60), _features(), [_news("announces partnership")])
    assert result is None
    assert ai_repo.list() == []


def test_malformed_provider_output_is_rejected() -> None:
    class _BadProvider:
        reasoning_version = "test-v1"
        prompt_version = "1.0"

        def analyze(self, context: AIPromptContext) -> dict[str, object]:
            return {"ticker": context.ticker, "garbage": True}

    service, ai_repo = _service(_BadProvider())
    result = service.analyze_signal(_signal(60), _features(), [_news("announces partnership")])
    assert result is None
    assert ai_repo.list() == []
