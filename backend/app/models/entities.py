"""Firestore document models.

Field naming is snake_case across Python and Firestore to match the explicit
traceability fields mandated by .cursor/rules.md (``signal_id``,
``feature_snapshot_id``, ``ai_analysis_id``). Every entity carries a
human-readable ``id``.
"""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.enums import (
    CatalystDirection,
    CatalystType,
    JobStatus,
    LogLevel,
    Sentiment,
    SignalDecision,
    SignalStatus,
    TradeSide,
    TradeStatus,
)
from app.utils.ids import is_valid_id, validate_ticker


class Entity(BaseModel):
    """Base for all stored documents."""

    model_config = ConfigDict(extra="forbid")

    id: str

    @field_validator("id")
    @classmethod
    def _check_id(cls, value: str) -> str:
        if not is_valid_id(value):
            raise ValueError(f"Non human-readable id: {value!r}")
        return value


class Stock(Entity):
    ticker: str
    name: str
    sector: str
    industry: str
    market_cap: float
    exchange: str
    currency: str = "USD"
    active: bool = True
    last_updated: datetime

    @field_validator("ticker")
    @classmethod
    def _check_ticker(cls, value: str) -> str:
        return validate_ticker(value)


class PriceBar(BaseModel):
    """A single OHLCV bar used as raw input to the feature engine."""

    model_config = ConfigDict(extra="forbid")

    ticker: str
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float


class TechnicalFeatures(BaseModel):
    model_config = ConfigDict(extra="forbid")
    rsi: float
    macd: float
    atr: float
    sma_20: float
    sma_50: float
    sma_200: float


class VolumeFeatures(BaseModel):
    model_config = ConfigDict(extra="forbid")
    relative_volume: float
    avg_volume: float


class MomentumFeatures(BaseModel):
    model_config = ConfigDict(extra="forbid")
    daily_return: float
    weekly_return: float
    monthly_return: float


class VolatilityFeatures(BaseModel):
    model_config = ConfigDict(extra="forbid")
    std_dev: float
    bollinger_width: float


class FeatureSnapshot(Entity):
    """Top-level document: features/feature_{ticker}_{date}."""

    ticker: str
    timestamp: datetime
    technical: TechnicalFeatures
    volume: VolumeFeatures
    momentum: MomentumFeatures
    volatility: VolatilityFeatures


class ScoreBreakdown(BaseModel):
    """Component scores (0-100) for full traceability of FinalScore."""

    model_config = ConfigDict(extra="forbid")
    momentum_score: float
    volume_score: float
    catalyst_score: float
    sector_strength: float
    volatility_breakout: float
    macro_alignment: float


class Signal(Entity):
    ticker: str
    timestamp: datetime
    score: float
    score_breakdown: ScoreBreakdown
    expected_return: float
    risk_score: float
    strategy: str = "momentum_catalyst"
    feature_snapshot_id: str
    ai_analysis_id: str | None = None
    decision: SignalDecision
    status: SignalStatus = SignalStatus.OPEN


class NewsItem(Entity):
    ticker: str
    timestamp: datetime
    headline: str
    source: str
    sentiment: Sentiment
    relevance_score: float
    raw_text: str = ""


class AiAnalysis(Entity):
    """LLM enrichment. Never an execution authority."""

    related_id: str
    ticker: str
    summary: str
    catalyst_type: CatalystType
    catalyst_direction: CatalystDirection
    ai_bias: float = Field(ge=-1.0, le=1.0)
    sentiment: Sentiment
    key_insights: list[str] = Field(default_factory=list)
    risk_factors: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)
    confidence_adjustment: float
    reasoning_version: str
    prompt_version: str = "1.0"
    embedding_version: str = "v1"


class EmbeddingRecord(Entity):
    """Persisted embedding for a corpus document (``ai_embeddings/``).

    Caches the vector for a source document (a news headline or a prior AI
    reasoning summary) so RAG retrieval embeds only the query at request time
    instead of re-embedding the whole corpus. Re-embedded when
    ``embedding_version`` changes (AI_PIPELINE.md sections 8 / 13).
    """

    source_id: str
    source_type: str  # "news" | "insight"
    ticker: str | None = None
    text: str
    vector: list[float]
    embedding_version: str
    created_at: datetime


class Trade(Entity):
    ticker: str
    side: TradeSide
    entry_time: datetime
    exit_time: datetime | None = None
    entry_price: float
    exit_price: float | None = None
    quantity: float
    status: TradeStatus = TradeStatus.OPEN
    signal_id: str
    feature_snapshot_id: str
    ai_analysis_id: str | None = None
    risk_decision_id: str | None = None
    pnl: float | None = None
    fees: float = 0.0


class RiskDecision(Entity):
    """Deterministic risk-engine verdict. The hard gate before execution.

    AI cannot override this layer (.cursor/rules.md 3.3 / 6).
    """

    ticker: str
    timestamp: datetime
    side: TradeSide
    approved: bool
    rejection_reasons: list[str] = Field(default_factory=list)
    signal_id: str
    feature_snapshot_id: str
    ai_analysis_id: str | None = None
    account_equity: float
    risk_per_trade: float
    confidence_multiplier: float
    stop_distance: float
    stop_price: float
    quantity: float
    notional: float


class Position(Entity):
    """Real-time portfolio state for one ticker.

    ``stop_price`` and ``target_price`` are the exit levels committed at entry so
    the live position monitor honors the exact contract the trade was opened
    under (deterministic, reproducible exits via the shared exit engine).
    """

    ticker: str
    sector: str
    quantity: float
    avg_entry_price: float
    market_value: float
    unrealized_pnl: float
    risk_exposure: float
    stop_price: float
    target_price: float
    opened_at: datetime
    trade_id: str


class Portfolio(Entity):
    """Account-level state for the paper/live trading account."""

    name: str
    equity: float
    cash: float
    updated_at: datetime


class BacktestMetrics(BaseModel):
    model_config = ConfigDict(extra="forbid")
    sharpe: float
    win_rate: float
    max_drawdown: float
    total_return: float


class Backtest(Entity):
    strategy: str
    start_date: date
    end_date: date
    tickers: list[str]
    trade_count: int
    metrics: BacktestMetrics
    created_at: datetime


class SystemState(Entity):
    """Singleton operational state for the trading system.

    Persists the manual kill switch so an operator-engaged halt survives process
    restarts. Data-derived circuit breakers (daily loss, loss streak) are
    recomputed each run and are not stored here.
    """

    kill_switch_enabled: bool = False
    halt_reason: str | None = None
    updated_at: datetime


class JobRecord(Entity):
    job_type: str
    status: JobStatus = JobStatus.PENDING
    created_at: datetime
    updated_at: datetime
    error: str | None = None


class LogEntry(Entity):
    service: str
    level: LogLevel
    event: str
    message: str
    timestamp: datetime
    metadata: dict[str, object] = Field(default_factory=dict)
