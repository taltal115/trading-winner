"""Ingestion service: pull raw data, store metadata, apply Stage 1 filter.

API -> Service -> (Engine) -> Repository -> Firestore. The service owns
orchestration and persistence; the universe filtering decision is delegated to
the engine.
"""

from __future__ import annotations

from app.engines.universe_filter_engine import (
    UniverseCandidate,
    UniverseThresholds,
    filter_universe,
)
from app.repositories.repositories import StockRepository
from app.services.log_writer import LogWriter
from app.services.market_data import MarketDataSource


class IngestionService:
    def __init__(
        self,
        stock_repo: StockRepository,
        log_writer: LogWriter,
        source: MarketDataSource,
        thresholds: UniverseThresholds | None = None,
    ) -> None:
        self._stocks = stock_repo
        self._log = log_writer
        self._source = source
        self._thresholds = thresholds or UniverseThresholds()

    def ingest_universe(self) -> list[UniverseCandidate]:
        """Persist stock metadata and return Stage-1 surviving candidates."""
        candidates = self._source.get_universe()
        survivors = filter_universe(candidates, self._thresholds)
        for candidate in survivors:
            self._stocks.save(self._source.get_stock(candidate.ticker))
        self._log.log(
            event="universe_ingested",
            message=f"{len(survivors)}/{len(candidates)} stocks passed universe filter",
            metadata={"survivors": [c.ticker for c in survivors]},
        )
        return survivors
