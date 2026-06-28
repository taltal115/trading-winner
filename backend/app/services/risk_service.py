"""Risk service: gather portfolio state, run the risk engine, persist verdict.

Produces a ``RiskDecision`` for every evaluated signal (approved or not) so the
gate is fully auditable. Long-only swing entries in Phase 4.
"""

from __future__ import annotations

from datetime import UTC, datetime

from app.config.settings import RiskLimits
from app.engines.risk_engine import RiskInputs, assess_risk
from app.models.entities import FeatureSnapshot, RiskDecision, Signal
from app.models.enums import LogLevel, TradeSide
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
    ) -> None:
        self._risk = risk_repo
        self._stocks = stock_repo
        self._portfolio = portfolio_service
        self._log = log_writer
        self._limits = limits

    def evaluate(
        self,
        signal: Signal,
        features: FeatureSnapshot,
        entry_price: float,
    ) -> RiskDecision:
        stock = self._stocks.get_by_ticker(signal.ticker)
        sector = stock.sector if stock is not None else "Unknown"
        portfolio = self._portfolio.get_or_create_portfolio()

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
        )
        assessment = assess_risk(inputs, self._limits)

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
