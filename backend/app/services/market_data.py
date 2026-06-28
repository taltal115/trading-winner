"""Market data source abstraction (external API boundary).

This is the seam where IBKR / Finnhub adapters plug in later. Phase 1 ships a
deterministic mock so the full pipeline can run and be tested offline.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Protocol

from app.engines.universe_filter_engine import UniverseCandidate
from app.models.entities import NewsItem, PriceBar, Stock
from app.models.enums import Sentiment
from app.utils.ids import news_id


@dataclass(frozen=True)
class _StockMeta:
    name: str
    sector: str
    growth: float  # per-bar compounding rate
    start: float  # first close
    headline: str  # mock news headline (drives catalyst detection)
    news_sentiment: Sentiment


# Strong momentum names compound, slow names drift, the downtrend decays.
# NVDA carries a catalyst headline; AAPL deliberately has none (gating test).
_MOCK_UNIVERSE: dict[str, _StockMeta] = {
    "NVDA": _StockMeta(
        "NVIDIA Corporation",
        "Technology",
        0.012,
        90.0,
        "NVIDIA announces new AI chip partnership",
        Sentiment.POSITIVE,
    ),
    "AAPL": _StockMeta(
        "Apple Inc.",
        "Technology",
        0.008,
        150.0,
        "Apple stock trades in line with the market",
        Sentiment.NEUTRAL,
    ),
    "XYZ": _StockMeta(
        "Example Downtrend Co",
        "Energy",
        -0.010,
        230.0,
        "Example Downtrend Co guidance cut on weak demand",
        Sentiment.NEGATIVE,
    ),
    "PENNY": _StockMeta(
        "Cheap Stock",
        "Materials",
        0.001,
        3.0,
        "Cheap Stock trading sideways",
        Sentiment.NEUTRAL,
    ),
}
_HISTORY_DAYS = 260


class MarketDataSource(Protocol):
    def get_universe(self) -> list[UniverseCandidate]: ...

    def get_stock(self, ticker: str) -> Stock: ...

    def get_price_history(self, ticker: str) -> list[PriceBar]: ...

    def get_news(self, ticker: str) -> list[NewsItem]: ...


class MockMarketDataSource:
    """Deterministic synthetic market data for dev and tests."""

    def __init__(self, as_of: datetime | None = None) -> None:
        self._as_of = as_of or datetime(2026, 7, 28, 16, 0, 0, tzinfo=UTC)

    def get_universe(self) -> list[UniverseCandidate]:
        candidates: list[UniverseCandidate] = []
        for ticker in _MOCK_UNIVERSE:
            bars = self.get_price_history(ticker)
            price = bars[-1].close
            avg_volume = sum(b.volume for b in bars[-20:]) / 20.0
            market_cap = price * 5_000_000_000 if ticker != "PENNY" else price * 1e7
            candidates.append(
                UniverseCandidate(
                    ticker=ticker,
                    market_cap=market_cap,
                    avg_volume=avg_volume,
                    price=price,
                    active=True,
                )
            )
        return candidates

    def get_stock(self, ticker: str) -> Stock:
        meta = _MOCK_UNIVERSE[ticker]
        bars = self.get_price_history(ticker)
        return Stock(
            id=f"stock_{ticker}_{self._as_of.date().isoformat()}",
            ticker=ticker,
            name=meta.name,
            sector=meta.sector,
            industry=meta.sector,
            market_cap=bars[-1].close * 5_000_000_000,
            exchange="NASDAQ",
            last_updated=self._as_of,
        )

    def get_price_history(self, ticker: str) -> list[PriceBar]:
        meta = _MOCK_UNIVERSE[ticker]
        first_day = self._as_of - timedelta(days=_HISTORY_DAYS - 1)
        bars: list[PriceBar] = []
        for i in range(_HISTORY_DAYS):
            close = max(1.0, meta.start * (1.0 + meta.growth) ** i)
            band = close * 0.01
            # Recent relative-volume expansion on the final bar.
            volume = 5_000_000.0 if i == _HISTORY_DAYS - 1 else 1_500_000.0
            bars.append(
                PriceBar(
                    ticker=ticker,
                    timestamp=first_day + timedelta(days=i),
                    open=close - band,
                    high=close + band,
                    low=close - band,
                    close=close,
                    volume=volume,
                )
            )
        return bars

    def get_news(self, ticker: str) -> list[NewsItem]:
        meta = _MOCK_UNIVERSE[ticker]
        return [
            NewsItem(
                id=news_id(ticker, self._as_of, 1),
                ticker=ticker,
                timestamp=self._as_of,
                headline=meta.headline,
                source="MockWire",
                sentiment=meta.news_sentiment,
                relevance_score=0.9,
                raw_text=meta.headline,
            )
        ]
