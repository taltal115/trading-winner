from datetime import datetime

from app.models.entities import (
    FeatureSnapshot,
    MomentumFeatures,
    ScoreBreakdown,
    Signal,
    TechnicalFeatures,
    VolatilityFeatures,
    VolumeFeatures,
)
from app.models.enums import SignalDecision, SignalStatus
from app.repositories.base import InMemoryDocumentStore
from app.repositories.repositories import FeatureRepository, SignalRepository


def _feature(ticker: str) -> FeatureSnapshot:
    return FeatureSnapshot(
        id=f"feature_{ticker}_2026-07-28",
        ticker=ticker,
        timestamp=datetime(2026, 7, 28, 10, 0, 0),
        technical=TechnicalFeatures(rsi=60, macd=1.0, atr=4.0, sma_20=10, sma_50=9, sma_200=8),
        volume=VolumeFeatures(relative_volume=2.0, avg_volume=1_000_000),
        momentum=MomentumFeatures(daily_return=0.01, weekly_return=0.05, monthly_return=0.1),
        volatility=VolatilityFeatures(std_dev=0.02, bollinger_width=0.08),
    )


def _signal(ticker: str, score: float) -> Signal:
    return Signal(
        id=f"signal_{ticker}_2026-07-28",
        ticker=ticker,
        timestamp=datetime(2026, 7, 28, 10, 5, 0),
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
        feature_snapshot_id=f"feature_{ticker}_2026-07-28",
        decision=SignalDecision.BUY,
        status=SignalStatus.OPEN,
    )


def test_save_and_get_roundtrip() -> None:
    store = InMemoryDocumentStore()
    repo = FeatureRepository(store)
    feature = _feature("NVDA")
    repo.save(feature)
    fetched = repo.get(feature.id)
    assert fetched is not None
    assert fetched.ticker == "NVDA"


def test_top_signals_sorted_and_limited() -> None:
    store = InMemoryDocumentStore()
    repo = SignalRepository(store)
    repo.save(_signal("AAA", 70))
    repo.save(_signal("BBB", 90))
    repo.save(_signal("CCC", 80))
    top = repo.get_top_signals(limit=2)
    assert [s.score for s in top] == [90, 80]
