"""Risk service: gather portfolio state, run the risk engine, persist verdict.

Produces a ``RiskDecision`` for every evaluated signal (approved or not) so the
gate is fully auditable. Long-only swing entries in Phase 4.
"""

from __future__ import annotations

from datetime import UTC, datetime

from app.config.settings import RiskLimits
from app.engines.risk_engine import RiskInputs, assess_risk
from app.models.entities import FeatureSnapshot, MarketRegimeSnapshot, RiskDecision, Signal
from app.models.enums import ExposureRecommendation, LogLevel, TradeSide
from app.repositories.repositories import RiskDecisionRepository, StockRepository
from app.services.log_writer import LogWriter
from app.services.portfolio_service import PortfolioService
from app.utils.ids import risk_decision_id


class RiskService:
    def __init__(
        self,
        risk_repo: RiskDecisionRepository,
        stock_repo: StockRepository,
        portfolio_service: PortfolioService,
        log_writer: LogWriter,
        limits: RiskLimits,
        low_exposure_position_ratio: float = 0.5,
    ) -> None:
        self._risk = risk_repo
        self._stocks = stock_repo
        self._portfolio = portfolio_service
        self._log = log_writer
        self._limits = limits
        self._low_exposure_position_ratio = low_exposure_position_ratio

    def evaluate(
        self,
        signal: Signal,
        features: FeatureSnapshot,
        entry_price: float,
        regime: MarketRegimeSnapshot | None = None,
    ) -> RiskDecision:
        """Run the risk gate for one signal.

        When ``regime`` is supplied (Market Regime Engine enabled) its
        ``risk_multiplier`` scales sizing and a ``low`` ``exposure_recommendation``
        deterministically tightens the open-position cap. With no regime the
        behavior is byte-for-byte unchanged (multiplier 1.0, cap unchanged).
        """
        stock = self._stocks.get_by_ticker(signal.ticker)
        sector = stock.sector if stock is not None else "Unknown"
        portfolio = self._portfolio.get_or_create_portfolio()
        limits = self._effective_limits(regime)

        inputs = RiskInputs(
            ticker=signal.ticker,
            sector=sector,
            side=TradeSide.LONG,
            entry_price=entry_price,
            atr=features.technical.atr,
            score=signal.score,
            account_equity=portfolio.equity,
            cash=portfolio.cash,
            open_positions_count=self._portfolio.open_position_count(),
            sector_exposure=self._portfolio.sector_exposure(sector),
            holding_ticker=self._portfolio.holding(signal.ticker),
            regime_risk_multiplier=regime.risk_multiplier if regime is not None else 1.0,
        )
        assessment = assess_risk(inputs, limits)

        now = datetime.now(UTC)
        decision = RiskDecision(
            id=risk_decision_id(signal.ticker, now),
            ticker=signal.ticker,
            timestamp=now,
            side=TradeSide.LONG,
            approved=assessment.approved,
            rejection_reasons=assessment.rejection_reasons,
            signal_id=signal.id,
            feature_snapshot_id=signal.feature_snapshot_id,
            ai_analysis_id=signal.ai_analysis_id,
            account_equity=portfolio.equity,
            risk_per_trade=self._limits.risk_per_trade,
            confidence_multiplier=assessment.confidence_multiplier,
            stop_distance=assessment.stop_distance,
            stop_price=assessment.stop_price,
            quantity=assessment.quantity,
            notional=assessment.notional,
        )
        self._risk.save(decision)
        self._maybe_log_regime(signal, regime)
        self._log.log(
            event="risk_decision",
            message=(
                f"{signal.ticker}: {'APPROVED' if assessment.approved else 'REJECTED'} "
                f"qty={assessment.quantity} reasons={assessment.rejection_reasons}"
            ),
            level=LogLevel.INFO if assessment.approved else LogLevel.WARNING,
            metadata={"risk_decision_id": decision.id, "signal_id": signal.id},
        )
        return decision

    def _effective_limits(self, regime: MarketRegimeSnapshot | None) -> RiskLimits:
        """Tighten the open-position cap under a low-exposure regime.

        The regime layer can only REDUCE risk within the §11 hard limits; it
        never relaxes a cap. With no regime (or non-low exposure) the configured
        limits are returned unchanged.
        """
        if regime is None or regime.exposure_recommendation is not ExposureRecommendation.LOW:
            return self._limits
        capped = max(1, int(self._limits.max_open_positions * self._low_exposure_position_ratio))
        return self._limits.model_copy(update={"max_open_positions": capped})

    def _maybe_log_regime(self, signal: Signal, regime: MarketRegimeSnapshot | None) -> None:
        if regime is None:
            return
        self._log.log(
            event="regime_applied",
            message=(
                f"{signal.ticker}: regime={regime.regime_state.value} "
                f"multiplier={regime.risk_multiplier} "
                f"exposure={regime.exposure_recommendation.value}"
            ),
            metadata={"signal_id": signal.id, "market_regime_id": regime.id},
        )
