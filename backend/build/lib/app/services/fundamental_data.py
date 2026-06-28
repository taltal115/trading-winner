"""Fundamentals data source abstraction (external API boundary).

This is the seam where a real fundamentals provider (e.g. Finnhub / SEC EDGAR)
plugs in later. Phase 1 ships a deterministic mock so the Fundamental Engine
and the full pipeline can run and be tested offline. Mirrors the
``market_data.py`` Protocol + Mock pattern.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from app.engines.fundamental_engine import FundamentalInputs


@dataclass(frozen=True)
class _FundamentalMeta:
    revenue_ttm: float
    revenue_prior_ttm: float
    earnings_ttm: float
    earnings_prior_ttm: float
    operating_cashflow_ttm: float
    free_cashflow_ttm: float
    total_debt: float
    total_equity: float
    debt_to_equity: float
    current_ratio: float
    net_margin: float
    return_on_equity: float
    shares_outstanding: float
    shares_outstanding_prior: float


# Deterministic fundamentals consistent with the market-data mock universe:
# NVDA is high-quality (boost), XYZ/PENNY are distressed (veto candidates).
_MOCK_FUNDAMENTALS: dict[str, _FundamentalMeta] = {
    "NVDA": _FundamentalMeta(
        revenue_ttm=1.15e11,
        revenue_prior_ttm=9.0e10,
        earnings_ttm=5.6e10,
        earnings_prior_ttm=4.0e10,
        operating_cashflow_ttm=6.4e10,
        free_cashflow_ttm=5.0e10,
        total_debt=1.0e10,
        total_equity=7.0e10,
        debt_to_equity=0.21,
        current_ratio=3.5,
        net_margin=0.48,
        return_on_equity=0.60,
        shares_outstanding=2.46e9,
        shares_outstanding_prior=2.50e9,
    ),
    "AAPL": _FundamentalMeta(
        revenue_ttm=3.90e11,
        revenue_prior_ttm=3.80e11,
        earnings_ttm=1.00e11,
        earnings_prior_ttm=9.90e10,
        operating_cashflow_ttm=1.10e11,
        free_cashflow_ttm=9.00e10,
        total_debt=1.10e11,
        total_equity=6.00e10,
        debt_to_equity=1.80,
        current_ratio=1.05,
        net_margin=0.25,
        return_on_equity=1.20,
        shares_outstanding=1.50e10,
        shares_outstanding_prior=1.55e10,
    ),
    "XYZ": _FundamentalMeta(
        revenue_ttm=8.0e8,
        revenue_prior_ttm=1.0e9,
        earnings_ttm=-1.5e8,
        earnings_prior_ttm=-5.0e7,
        operating_cashflow_ttm=-5.0e7,
        free_cashflow_ttm=-1.0e8,
        total_debt=9.0e8,
        total_equity=1.0e8,
        debt_to_equity=3.0,
        current_ratio=0.8,
        net_margin=-0.19,
        return_on_equity=-1.5,
        shares_outstanding=2.2e8,
        shares_outstanding_prior=2.0e8,
    ),
    "PENNY": _FundamentalMeta(
        revenue_ttm=5.0e7,
        revenue_prior_ttm=6.0e7,
        earnings_ttm=-2.0e7,
        earnings_prior_ttm=-1.0e7,
        operating_cashflow_ttm=-1.0e7,
        free_cashflow_ttm=-1.5e7,
        total_debt=4.0e7,
        total_equity=5.0e6,
        debt_to_equity=8.0,
        current_ratio=0.6,
        net_margin=-0.40,
        return_on_equity=-2.0,
        shares_outstanding=1.5e8,
        shares_outstanding_prior=1.0e8,
    ),
}

# Neutral, healthy-but-unremarkable defaults for tickers without a mock entry.
_DEFAULT_FUNDAMENTAL = _FundamentalMeta(
    revenue_ttm=1.0e10,
    revenue_prior_ttm=9.5e9,
    earnings_ttm=1.0e9,
    earnings_prior_ttm=9.5e8,
    operating_cashflow_ttm=1.2e9,
    free_cashflow_ttm=8.0e8,
    total_debt=4.0e9,
    total_equity=8.0e9,
    debt_to_equity=0.5,
    current_ratio=1.8,
    net_margin=0.10,
    return_on_equity=0.15,
    shares_outstanding=1.0e9,
    shares_outstanding_prior=1.0e9,
)


class FundamentalDataSource(Protocol):
    def get_fundamentals(self, ticker: str) -> FundamentalInputs: ...


class MockFundamentalDataSource:
    """Deterministic synthetic fundamentals for dev and tests."""

    def get_fundamentals(self, ticker: str) -> FundamentalInputs:
        meta = _MOCK_FUNDAMENTALS.get(ticker, _DEFAULT_FUNDAMENTAL)
        return FundamentalInputs(
            ticker=ticker,
            revenue_ttm=meta.revenue_ttm,
            revenue_prior_ttm=meta.revenue_prior_ttm,
            earnings_ttm=meta.earnings_ttm,
            earnings_prior_ttm=meta.earnings_prior_ttm,
            operating_cashflow_ttm=meta.operating_cashflow_ttm,
            free_cashflow_ttm=meta.free_cashflow_ttm,
            total_debt=meta.total_debt,
            total_equity=meta.total_equity,
            debt_to_equity=meta.debt_to_equity,
            current_ratio=meta.current_ratio,
            net_margin=meta.net_margin,
            return_on_equity=meta.return_on_equity,
            shares_outstanding=meta.shares_outstanding,
            shares_outstanding_prior=meta.shares_outstanding_prior,
        )
