"""Domain enumerations shared across engines, services and repositories."""

from __future__ import annotations

from enum import StrEnum


class TradeSide(StrEnum):
    LONG = "LONG"
    SHORT = "SHORT"


class OrderAction(StrEnum):
    """Broker order action. Entries buy, exits sell (long-only swing system)."""

    BUY = "BUY"
    SELL = "SELL"


class TradeStatus(StrEnum):
    OPEN = "OPEN"
    CLOSED = "CLOSED"
    CANCELLED = "CANCELLED"


class SignalDecision(StrEnum):
    STRONG_BUY = "STRONG_BUY"
    BUY = "BUY"
    WATCH = "WATCH"
    IGNORE = "IGNORE"


class SignalStatus(StrEnum):
    OPEN = "OPEN"
    CLOSED = "CLOSED"


class CatalystDirection(StrEnum):
    """AI catalyst direction. Never an execution authority."""

    BULLISH = "bullish"
    NEUTRAL = "neutral"
    BEARISH = "bearish"


class CatalystType(StrEnum):
    EARNINGS = "earnings"
    NEWS = "news"
    MACRO = "macro"
    INSIDER = "insider"
    UNKNOWN = "unknown"


class Sentiment(StrEnum):
    POSITIVE = "positive"
    NEUTRAL = "neutral"
    NEGATIVE = "negative"


class RegimeState(StrEnum):
    """Macro market environment from the Market Regime Engine.

    Deterministic, market-wide. AI may read it for context but can never
    override it (ARCHITECTURE.md 3.2.2 / TRADING_ENGINE.md 4.6).
    """

    BULLISH = "bullish"
    NEUTRAL = "neutral"
    BEARISH = "bearish"
    HIGH_VOLATILITY = "high_volatility"


class ExposureRecommendation(StrEnum):
    """Deterministic activity cap from the Market Regime Engine."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class ExitReason(StrEnum):
    STOP_LOSS = "STOP_LOSS"
    PROFIT_TARGET = "PROFIT_TARGET"
    TIME = "TIME"
    MOMENTUM_FAILURE = "MOMENTUM_FAILURE"


class JobStatus(StrEnum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"


class LogLevel(StrEnum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
