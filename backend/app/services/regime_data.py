"""Macro / market-regime data source abstraction (external API boundary).

This is the seam where real macro feeds (SPY trend, VIX, sector breadth) plug
in later. Phase 1 ships a deterministic mock so the Market Regime Engine and
the full pipeline can run and be tested offline. Mirrors the ``market_data.py``
Protocol + Mock pattern.
"""

from __future__ import annotations

from typing import Protocol

from app.engines.market_regime_engine import MarketRegimeInputs


class MacroDataSource(Protocol):
    def get_market_regime_inputs(self) -> MarketRegimeInputs: ...


class MockMacroDataSource:
    """Deterministic synthetic macro inputs.

    Tuned to a calm, neutral baseline (regime=neutral, risk_multiplier=1.0,
    exposure=medium) so the regime layer is a no-op by default until real feeds
    are wired in.
    """

    def get_market_regime_inputs(self) -> MarketRegimeInputs:
        return MarketRegimeInputs(
            spy_trend=0.004,
            vix=15.0,
            sector_breadth=0.50,
            market_momentum=0.0,
            cross_stock_correlation=0.42,
        )
