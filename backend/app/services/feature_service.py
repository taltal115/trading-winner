"""Feature service: orchestrate feature computation and persistence."""

from __future__ import annotations

from app.engines.feature_engine import compute_features
from app.models.entities import FeatureSnapshot
from app.models.enums import LogLevel
from app.repositories.repositories import FeatureRepository
from app.services.log_writer import LogWriter
from app.services.market_data import MarketDataSource


class FeatureService:
    def __init__(
        self,
        feature_repo: FeatureRepository,
        log_writer: LogWriter,
        source: MarketDataSource,
    ) -> None:
        self._features = feature_repo
        self._log = log_writer
        self._source = source

    def build_features(self, ticker: str) -> FeatureSnapshot:
        bars = self._source.get_price_history(ticker)
        snapshot = compute_features(ticker, bars)
        self._features.save(snapshot)
        self._log.log(
            event="features_computed",
            message=f"features computed for {ticker}",
            metadata={"feature_id": snapshot.id},
        )
        return snapshot

    def build_for_tickers(self, tickers: list[str]) -> list[FeatureSnapshot]:
        snapshots: list[FeatureSnapshot] = []
        for ticker in tickers:
            try:
                snapshots.append(self.build_features(ticker))
            except ValueError as exc:
                self._log.log(
                    event="features_skipped",
                    message=f"insufficient data for {ticker}: {exc}",
                    level=LogLevel.WARNING,
                    metadata={"ticker": ticker},
                )
        return snapshots
