"""Fundamental service: fetch raw financials, run the engine, persist snapshot.

Orchestration only (no scoring decisions): it fetches inputs from the data
seam, delegates the deterministic computation to the pure Fundamental Engine,
and persists a ``fundamentals/`` snapshot with full traceability.
"""

from __future__ import annotations

from datetime import datetime

from app.engines.fundamental_engine import (
    FundamentalInputs,
    evaluate_fundamentals,
    shares_outstanding_trend,
)
from app.models.entities import FundamentalSnapshot
from app.models.enums import LogLevel
from app.repositories.repositories import FundamentalRepository
from app.services.fundamental_data import FundamentalDataSource
from app.services.log_writer import LogWriter
from app.utils.ids import fundamental_id


class FundamentalService:
    def __init__(
        self,
        fundamental_repo: FundamentalRepository,
        source: FundamentalDataSource,
        log_writer: LogWriter,
    ) -> None:
        self._fundamentals = fundamental_repo
        self._source = source
        self._log = log_writer

    def compute_for_ticker(self, ticker: str, when: datetime) -> FundamentalSnapshot:
        inputs = self._source.get_fundamentals(ticker)
        result = evaluate_fundamentals(inputs)
        snapshot = FundamentalSnapshot(
            id=fundamental_id(ticker, when),
            ticker=ticker,
            date=when.date(),
            timestamp=when,
            fundamental_score=result.fundamental_score,
            quality_subscores=result.quality_subscores,
            risk_flags=result.risk_flags,
            inputs_summary=self._inputs_summary(inputs),
        )
        self._fundamentals.save(snapshot)
        self._log.log(
            event="fundamentals_computed",
            message=(
                f"{ticker}: fundamental_score={result.fundamental_score} "
                f"flags={result.risk_flags}"
            ),
            metadata={"fundamental_id": snapshot.id, "ticker": ticker},
        )
        return snapshot

    def compute_for_tickers(
        self, tickers: list[str], when: datetime
    ) -> dict[str, FundamentalSnapshot]:
        snapshots: dict[str, FundamentalSnapshot] = {}
        for ticker in tickers:
            try:
                snapshots[ticker] = self.compute_for_ticker(ticker, when)
            except ValueError as exc:
                self._log.log(
                    event="fundamentals_skipped",
                    message=f"insufficient fundamentals for {ticker}: {exc}",
                    level=LogLevel.WARNING,
                    metadata={"ticker": ticker},
                )
        return snapshots

    @staticmethod
    def _inputs_summary(inputs: FundamentalInputs) -> dict[str, object]:
        return {
            "revenue_ttm": inputs.revenue_ttm,
            "earnings_ttm": inputs.earnings_ttm,
            "operating_cashflow_ttm": inputs.operating_cashflow_ttm,
            "total_debt": inputs.total_debt,
            "debt_to_equity": inputs.debt_to_equity,
            "shares_outstanding_trend": shares_outstanding_trend(inputs),
        }
