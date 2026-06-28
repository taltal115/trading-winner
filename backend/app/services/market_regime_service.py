"""Market regime service: fetch macro inputs, run the engine, persist snapshot.

Computed once per cycle (market-wide). Orchestration only: it delegates the
deterministic computation to the pure Market Regime Engine and persists a
``market_regime/`` snapshot used downstream as a hard risk constraint.
"""

from __future__ import annotations

from datetime import datetime

from app.engines.market_regime_engine import MarketRegimeInputs, evaluate_regime
from app.models.entities import MarketRegimeSnapshot
from app.repositories.repositories import MarketRegimeRepository
from app.services.log_writer import LogWriter
from app.services.regime_data import MacroDataSource
from app.utils.ids import market_regime_id


class MarketRegimeService:
    def __init__(
        self,
        regime_repo: MarketRegimeRepository,
        source: MacroDataSource,
        log_writer: LogWriter,
    ) -> None:
        self._regimes = regime_repo
        self._source = source
        self._log = log_writer

    def compute_regime(self, when: datetime) -> MarketRegimeSnapshot:
        inputs = self._source.get_market_regime_inputs()
        result = evaluate_regime(inputs)
        snapshot = MarketRegimeSnapshot(
            id=market_regime_id(when),
            date=when.date(),
            timestamp=when,
            regime_state=result.regime_state,
            risk_multiplier=result.risk_multiplier,
            exposure_recommendation=result.exposure_recommendation,
            inputs_summary=self._inputs_summary(inputs),
        )
        self._regimes.save(snapshot)
        self._log.log(
            event="market_regime_computed",
            message=(
                f"regime={result.regime_state.value} "
                f"multiplier={result.risk_multiplier} "
                f"exposure={result.exposure_recommendation.value}"
            ),
            metadata={"market_regime_id": snapshot.id},
        )
        return snapshot

    @staticmethod
    def _inputs_summary(inputs: MarketRegimeInputs) -> dict[str, object]:
        return {
            "spy_trend": inputs.spy_trend,
            "vix": inputs.vix,
            "sector_breadth": inputs.sector_breadth,
            "market_momentum": inputs.market_momentum,
            "cross_stock_correlation": inputs.cross_stock_correlation,
        }
