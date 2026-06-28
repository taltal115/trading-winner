from datetime import UTC, datetime

from app.config.settings import RiskLimits, Settings, SystemPhase
from app.models.entities import (
    AiAnalysis,
    FeatureSnapshot,
    MomentumFeatures,
    RiskDecision,
    ScoreBreakdown,
    Signal,
    Stock,
    TechnicalFeatures,
    VolatilityFeatures,
    VolumeFeatures,
)
from app.models.enums import (
    CatalystDirection,
    CatalystType,
    Sentiment,
    SignalDecision,
    TradeSide,
)
from app.repositories.base import InMemoryDocumentStore
from app.repositories.repositories import (
    AiAnalysisRepository,
    FeatureRepository,
    LogRepository,
    PortfolioRepository,
    PositionRepository,
    SignalRepository,
    StockRepository,
    TradeRepository,
)
from app.services.broker import MockBroker
from app.services.execution_service import ExecutionService
from app.services.integrity_service import IntegrityService
from app.services.log_writer import LogWriter
from app.services.portfolio_service import PortfolioService

TICKER = "NVDA"
TS = datetime(2026, 7, 28, 10, 5, 0, tzinfo=UTC)
FEATURE_ID = "feature_NVDA_2026-07-28"
SIGNAL_ID = "signal_NVDA_2026-07-28"
AI_ID = "ai_NVDA_2026-07-28"


def _features() -> FeatureSnapshot:
    return FeatureSnapshot(
        id=FEATURE_ID,
        ticker=TICKER,
        timestamp=TS,
        technical=TechnicalFeatures(rsi=60, macd=1.0, atr=4.0, sma_20=10, sma_50=9, sma_200=8),
        volume=VolumeFeatures(relative_volume=2.0, avg_volume=1_000_000),
        momentum=MomentumFeatures(daily_return=0.01, weekly_return=0.05, monthly_return=0.1),
        volatility=VolatilityFeatures(std_dev=0.02, bollinger_width=0.08),
    )


def _signal(ai: bool) -> Signal:
    return Signal(
        id=SIGNAL_ID,
        ticker=TICKER,
        timestamp=TS,
        score=72,
        score_breakdown=ScoreBreakdown(
            momentum_score=80,
            volume_score=70,
            catalyst_score=0,
            sector_strength=50,
            volatility_breakout=50,
            macro_alignment=50,
        ),
        expected_return=0.05,
        risk_score=0.2,
        feature_snapshot_id=FEATURE_ID,
        ai_analysis_id=AI_ID if ai else None,
        decision=SignalDecision.BUY,
    )


def _ai() -> AiAnalysis:
    return AiAnalysis(
        id=AI_ID,
        related_id=SIGNAL_ID,
        ticker=TICKER,
        summary="bullish",
        catalyst_type=CatalystType.NEWS,
        catalyst_direction=CatalystDirection.BULLISH,
        ai_bias=0.3,
        sentiment=Sentiment.POSITIVE,
        confidence=0.7,
        confidence_adjustment=0.06,
        reasoning_version="mock-v1",
    )


def _decision(approved: bool, quantity: float = 100.0) -> RiskDecision:
    return RiskDecision(
        id="risk_NVDA_2026-07-28_100500",
        ticker=TICKER,
        timestamp=TS,
        side=TradeSide.LONG,
        approved=approved,
        rejection_reasons=[] if approved else ["blocked"],
        signal_id=SIGNAL_ID,
        feature_snapshot_id=FEATURE_ID,
        ai_analysis_id=AI_ID,
        account_equity=100_000.0,
        risk_per_trade=0.01,
        confidence_multiplier=1.2,
        stop_distance=4.0,
        stop_price=96.0,
        quantity=quantity,
        notional=quantity * 100.0,
    )


def _build(with_ai: bool) -> tuple[ExecutionService, TradeRepository, PositionRepository, Signal]:
    store = InMemoryDocumentStore()
    feature_repo = FeatureRepository(store)
    signal_repo = SignalRepository(store)
    trade_repo = TradeRepository(store)
    ai_repo = AiAnalysisRepository(store)
    stock_repo = StockRepository(store)
    position_repo = PositionRepository(store)
    portfolio_repo = PortfolioRepository(store)
    log = LogRepository(store)

    feature_repo.save(_features())
    signal = _signal(with_ai)
    signal_repo.save(signal)
    if with_ai:
        ai_repo.save(_ai())
    stock_repo.save(
        Stock(
            id="stock_NVDA_2026-07-28",
            ticker=TICKER,
            name="NVIDIA",
            sector="Technology",
            industry="Semis",
            market_cap=2e12,
            exchange="NASDAQ",
            last_updated=TS,
        )
    )

    integrity = IntegrityService(feature_repo, signal_repo, trade_repo, ai_repo)
    portfolio = PortfolioService(portfolio_repo, position_repo, LogWriter("portfolio", log))
    service = ExecutionService(
        trade_repo,
        stock_repo,
        MockBroker(),
        integrity,
        portfolio,
        LogWriter("execution", log),
        Settings(phase=SystemPhase.RISK_EXECUTION, risk=RiskLimits()),
    )
    return service, trade_repo, position_repo, signal


def test_execution_blocked_when_risk_not_approved() -> None:
    service, trade_repo, position_repo, signal = _build(with_ai=True)
    result = service.execute(signal, _features(), _decision(approved=False), 100.0)
    assert result is None
    assert trade_repo.list() == []
    assert position_repo.list() == []


def test_execution_blocked_by_gate_without_ai_in_phase4() -> None:
    service, trade_repo, position_repo, signal = _build(with_ai=False)
    result = service.execute(signal, _features(), _decision(approved=True), 100.0)
    assert result is None  # gate requires ai_analysis_id in phase 4
    assert trade_repo.list() == []


def test_execution_creates_trade_and_position() -> None:
    service, trade_repo, position_repo, signal = _build(with_ai=True)
    trade = service.execute(signal, _features(), _decision(approved=True), 100.0)
    assert trade is not None
    assert trade.risk_decision_id == "risk_NVDA_2026-07-28_100500"
    assert trade.ai_analysis_id == AI_ID
    assert trade.quantity == 100.0
    assert len(trade_repo.list()) == 1
    assert len(position_repo.get_open()) == 1


def test_execution_is_idempotent() -> None:
    service, trade_repo, position_repo, signal = _build(with_ai=True)
    first = service.execute(signal, _features(), _decision(approved=True), 100.0)
    second = service.execute(signal, _features(), _decision(approved=True), 100.0)
    assert first is not None and second is not None
    assert first.id == second.id
    assert len(trade_repo.list()) == 1
    assert len(position_repo.get_open()) == 1
