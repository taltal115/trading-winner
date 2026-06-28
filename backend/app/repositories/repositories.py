"""Concrete repositories. Query logic lives here, never in services."""

from __future__ import annotations

from app.models.entities import (
    AiAnalysis,
    Backtest,
    EmbeddingRecord,
    FeatureSnapshot,
    JobRecord,
    LogEntry,
    NewsItem,
    Portfolio,
    Position,
    RiskDecision,
    Signal,
    Stock,
    SystemState,
    Trade,
)
from app.models.enums import SignalStatus, TradeStatus
from app.repositories.base import Repository


class StockRepository(Repository[Stock]):
    collection = "stocks"
    model = Stock

    def list_active(self) -> list[Stock]:
        return [s for s in self.list() if s.active]

    def get_by_ticker(self, ticker: str) -> Stock | None:
        matches = [s for s in self.list() if s.ticker == ticker]
        return matches[0] if matches else None


class FeatureRepository(Repository[FeatureSnapshot]):
    collection = "features"
    model = FeatureSnapshot

    def get_for_ticker(self, ticker: str) -> list[FeatureSnapshot]:
        return [f for f in self.list() if f.ticker == ticker]


class SignalRepository(Repository[Signal]):
    collection = "signals"
    model = Signal

    def get_top_signals(self, limit: int = 20) -> list[Signal]:
        open_signals = [s for s in self.list() if s.status == SignalStatus.OPEN]
        return sorted(open_signals, key=lambda s: s.score, reverse=True)[:limit]


class TradeRepository(Repository[Trade]):
    collection = "trades"
    model = Trade

    def get_for_ticker(self, ticker: str) -> list[Trade]:
        return sorted(
            (t for t in self.list() if t.ticker == ticker),
            key=lambda t: t.entry_time,
            reverse=True,
        )

    def get_open(self) -> list[Trade]:
        return [t for t in self.list() if t.status == TradeStatus.OPEN]

    def get_closed(self) -> list[Trade]:
        """Closed trades, most recently exited first (loss-streak/PnL queries)."""
        return sorted(
            (t for t in self.list() if t.status == TradeStatus.CLOSED),
            key=lambda t: t.exit_time or t.entry_time,
            reverse=True,
        )


class RiskDecisionRepository(Repository[RiskDecision]):
    collection = "risk_decisions"
    model = RiskDecision


class PositionRepository(Repository[Position]):
    collection = "positions"
    model = Position

    def get_open(self) -> list[Position]:
        return [p for p in self.list() if p.quantity != 0]

    def get_for_ticker(self, ticker: str) -> Position | None:
        matches = [p for p in self.list() if p.ticker == ticker and p.quantity != 0]
        return matches[0] if matches else None


class PortfolioRepository(Repository[Portfolio]):
    collection = "portfolios"
    model = Portfolio


class NewsRepository(Repository[NewsItem]):
    collection = "news"
    model = NewsItem

    def get_for_ticker(self, ticker: str) -> list[NewsItem]:
        return [n for n in self.list() if n.ticker == ticker]


class AiAnalysisRepository(Repository[AiAnalysis]):
    collection = "ai_analysis"
    model = AiAnalysis


class EmbeddingRepository(Repository[EmbeddingRecord]):
    collection = "ai_embeddings"
    model = EmbeddingRecord


class BacktestRepository(Repository[Backtest]):
    collection = "backtests"
    model = Backtest

    def list_for_strategy(self, strategy: str) -> list[Backtest]:
        return [b for b in self.list() if b.strategy == strategy]


class SystemStateRepository(Repository[SystemState]):
    collection = "system_state"
    model = SystemState


class JobRepository(Repository[JobRecord]):
    collection = "jobs"
    model = JobRecord


class LogRepository(Repository[LogEntry]):
    collection = "logs"
    model = LogEntry
