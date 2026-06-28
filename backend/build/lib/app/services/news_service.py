"""News service: fetch raw news, persist to ``news/``, return for enrichment."""

from __future__ import annotations

from app.models.entities import NewsItem
from app.repositories.repositories import NewsRepository
from app.services.log_writer import LogWriter
from app.services.market_data import MarketDataSource


class NewsService:
    def __init__(
        self,
        news_repo: NewsRepository,
        log_writer: LogWriter,
        source: MarketDataSource,
    ) -> None:
        self._news = news_repo
        self._log = log_writer
        self._source = source

    def ingest_for_ticker(self, ticker: str) -> list[NewsItem]:
        items = self._source.get_news(ticker)
        for item in items:
            self._news.save(item)
        if items:
            self._log.log(
                event="news_ingested",
                message=f"{len(items)} news items for {ticker}",
                metadata={"ticker": ticker, "count": len(items)},
            )
        return items
