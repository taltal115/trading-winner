"""Execution service: the final, gated, idempotent step before a position.

Order of operations (ARCHITECTURE.md 3.6, .cursor/rules.md 6):
1. Refuse if the risk decision is not approved.
2. Build the trade and enforce the execution-dependency gate
   (signal_id + feature_snapshot_id always; ai_analysis_id in Phase 3+;
   risk_decision_id in Phase 4+). AI alone can never reach this point.
3. Idempotency: one trade per signal. Re-running returns the existing trade and
   never re-submits to the broker or re-opens a position.
4. Submit to the broker, persist the trade, apply the fill to the portfolio.
"""

from __future__ import annotations

from datetime import UTC, datetime

from app.config.settings import Settings
from app.engines.execution_engine import build_order
from app.models.entities import FeatureSnapshot, RiskDecision, Signal, Trade
from app.models.enums import LogLevel, TradeSide, TradeStatus
from app.repositories.repositories import StockRepository, TradeRepository
from app.services.broker import BrokerClient
from app.services.integrity_service import IntegrityError, IntegrityService
from app.services.log_writer import LogWriter
from app.services.portfolio_service import PortfolioService
from app.utils.ids import trade_id


class ExecutionService:
    def __init__(
        self,
        trade_repo: TradeRepository,
        stock_repo: StockRepository,
        broker: BrokerClient,
        integrity_service: IntegrityService,
        portfolio_service: PortfolioService,
        log_writer: LogWriter,
        settings: Settings,
    ) -> None:
        self._trades = trade_repo
        self._stocks = stock_repo
        self._broker = broker
        self._integrity = integrity_service
        self._portfolio = portfolio_service
        self._log = log_writer
        self._settings = settings

    def execute(
        self,
        signal: Signal,
        features: FeatureSnapshot,
        decision: RiskDecision,
        reference_price: float,
    ) -> Trade | None:
        if not decision.approved:
            self._log.log(
                event="execution_blocked_risk",
                message=f"{signal.ticker}: risk not approved, no order",
                level=LogLevel.WARNING,
                metadata={"signal_id": signal.id, "risk_decision_id": decision.id},
            )
            return None

        deterministic_id = trade_id(signal.ticker, signal.timestamp)
        existing = self._trades.get(deterministic_id)
        if existing is not None:
            return existing  # idempotent: signal already executed

        trade = Trade(
            id=deterministic_id,
            ticker=signal.ticker,
            side=TradeSide.LONG,
            entry_time=datetime.now(UTC),
            entry_price=reference_price,
            quantity=decision.quantity,
            status=TradeStatus.OPEN,
            signal_id=signal.id,
            feature_snapshot_id=signal.feature_snapshot_id,
            ai_analysis_id=signal.ai_analysis_id,
            risk_decision_id=decision.id,
        )

        try:
            self._integrity.assert_trade_executable(trade, self._settings)
        except IntegrityError as exc:
            self._log.log(
                event="execution_blocked_gate",
                message=f"{signal.ticker}: execution gate failed: {exc}",
                level=LogLevel.ERROR,
                metadata={"signal_id": signal.id},
            )
            return None

        order = build_order(decision, reference_price, features.volume.relative_volume)
        fill = self._broker.submit_order(order)

        filled_trade = trade.model_copy(update={"entry_price": fill.fill_price})
        self._trades.save(filled_trade)

        stock = self._stocks.get_by_ticker(signal.ticker)
        sector = stock.sector if stock is not None else "Unknown"
        target_price = fill.fill_price * (1.0 + self._settings.exit.profit_target)
        self._portfolio.apply_fill(
            filled_trade,
            sector,
            fill.fill_price,
            fill.quantity,
            stop_price=decision.stop_price,
            target_price=round(target_price, 4),
        )

        self._log.log(
            event="trade_executed",
            message=f"{signal.ticker}: filled {fill.quantity} @ {fill.fill_price}",
            metadata={
                "trade_id": filled_trade.id,
                "signal_id": signal.id,
                "risk_decision_id": decision.id,
            },
        )
        return filled_trade
