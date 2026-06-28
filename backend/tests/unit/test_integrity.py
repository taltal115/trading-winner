from datetime import datetime

import pytest

from app.config.settings import RiskLimits, Settings, SystemPhase
from app.models.entities import (
    FeatureSnapshot,
    MomentumFeatures,
    ScoreBreakdown,
    Signal,
    TechnicalFeatures,
    Trade,
    VolatilityFeatures,
    VolumeFeatures,
)
from app.models.enums import SignalDecision, TradeSide
from app.repositories.base import InMemoryDocumentStore
from app.repositories.repositories import (
    AiAnalysisRepository,
    FeatureRepository,
    SignalRepository,
    TradeRepository,
)
from app.services.integrity_service import IntegrityError, IntegrityService

TICKER = "NVDA"
FEATURE_ID = f"feature_{TICKER}_2026-07-28"
SIGNAL_ID = f"signal_{TICKER}_2026-07-28"


def _settings(phase: SystemPhase) -> Settings:
    return Settings(phase=phase, risk=RiskLimits())


def _build() -> tuple[IntegrityService, FeatureRepository, SignalRepository, TradeRepository]:
    store = InMemoryDocumentStore()
    features = FeatureRepository(store)
    signals = SignalRepository(store)
    trades = TradeRepository(store)
    ai = AiAnalysisRepository(store)
    service = IntegrityService(features, signals, trades, ai)
    return service, features, signals, trades


def _feature() -> FeatureSnapshot:
    return FeatureSnapshot(
        id=FEATURE_ID,
        ticker=TICKER,
        timestamp=datetime(2026, 7, 28, 10, 0, 0),
        technical=TechnicalFeatures(rsi=60, macd=1.0, atr=4.0, sma_20=10, sma_50=9, sma_200=8),
        volume=VolumeFeatures(relative_volume=2.0, avg_volume=1_000_000),
        momentum=MomentumFeatures(daily_return=0.01, weekly_return=0.05, monthly_return=0.1),
        volatility=VolatilityFeatures(std_dev=0.02, bollinger_width=0.08),
    )


def _signal() -> Signal:
    return Signal(
        id=SIGNAL_ID,
        ticker=TICKER,
        timestamp=datetime(2026, 7, 28, 10, 5, 0),
        score=87,
        score_breakdown=ScoreBreakdown(
            momentum_score=80,
            volume_score=70,
            catalyst_score=0,
            sector_strength=50,
            volatility_breakout=50,
            macro_alignment=50,
        ),
        expected_return=0.04,
        risk_score=0.2,
        feature_snapshot_id=FEATURE_ID,
        decision=SignalDecision.STRONG_BUY,
    )


def _trade(**overrides: object) -> Trade:
    base: dict[str, object] = dict(
        id="trade_NVDA_2026-07-28_093015",
        ticker=TICKER,
        side=TradeSide.LONG,
        entry_time=datetime(2026, 7, 28, 9, 30, 15),
        entry_price=892.5,
        quantity=10,
        signal_id=SIGNAL_ID,
        feature_snapshot_id=FEATURE_ID,
    )
    base.update(overrides)
    return Trade(**base)  # type: ignore[arg-type]


def test_orphan_signal_detected_when_feature_missing() -> None:
    service, _, signals, _ = _build()
    signals.save(_signal())
    violations = service.find_orphans()
    assert any("missing feature" in v for v in violations)


def test_no_orphans_when_references_present() -> None:
    service, features, signals, _ = _build()
    features.save(_feature())
    signals.save(_signal())
    assert service.find_orphans() == []


def test_phase1_trade_executable_without_ai() -> None:
    service, features, signals, _ = _build()
    features.save(_feature())
    signals.save(_signal())
    service.assert_trade_executable(_trade(), _settings(SystemPhase.MVP_READ_ONLY))


def test_phase3_trade_requires_ai() -> None:
    service, features, signals, _ = _build()
    features.save(_feature())
    signals.save(_signal())
    with pytest.raises(IntegrityError) as exc:
        service.assert_trade_executable(_trade(), _settings(SystemPhase.AI_INTEGRATION))
    assert "ai_analysis_id" in str(exc.value)


def test_phase4_trade_requires_risk_decision() -> None:
    service, features, signals, _ = _build()
    features.save(_feature())
    signals.save(_signal())
    trade = _trade(ai_analysis_id=None)
    with pytest.raises(IntegrityError) as exc:
        service.assert_trade_executable(trade, _settings(SystemPhase.RISK_EXECUTION))
    msg = str(exc.value)
    assert "ai_analysis_id" in msg and "risk_decision_id" in msg
