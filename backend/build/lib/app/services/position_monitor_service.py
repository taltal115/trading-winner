"""Position monitor: the live exit side of the trading loop (Phase 5).

Entries are produced by the execution service; this service is what closes them.
For every open position it pulls the latest price, recomputes features through the
SAME feature engine used at entry/backtest, and asks the SHARED exit engine
(``evaluate_exit``) whether the position should close. There is no parallel exit
path, so live exits behave exactly like backtested exits (.cursor/rules.md 3.2).

Safety / determinism:
- The monitor never opens positions and never touches the risk gate.
- Exit levels (stop/target) are read off the position as committed at entry.
- It only acts on OPEN positions and uses a deterministic, idempotent exit order
  id, so re-running (or a retried job) never double-closes or double-sells.
"""

from __future__ import annotations

from datetime import UTC, datetime

from app.config.settings import ExitLimits
from app.engines.execution_engine import build_exit_order
from app.engines.exit_engine import evaluate_exit
from app.engines.feature_engine import MIN_BARS, compute_features
from app.models.entities import Position, Trade
from app.models.enums import LogLevel, TradeStatus
from app.repositories.repositories import PositionRepository, TradeRepository
from app.services.broker import BrokerClient
from app.services.log_writer import LogWriter
from app.services.market_data import MarketDataSource
from app.services.outcome_service import OutcomeService
from app.services.portfolio_service import PortfolioService


class PositionMonitorService:
    def __init__(
        self,
        position_repo: PositionRepository,
        trade_repo: TradeRepository,
        portfolio_service: PortfolioService,
        broker: BrokerClient,
        source: MarketDataSource,
        log_writer: LogWriter,
        limits: ExitLimits,
        outcome_service: OutcomeService | None = None,
    ) -> None:
        self._positions = position_repo
        self._trades = trade_repo
        self._portfolio = portfolio_service
        self._broker = broker
        self._source = source
        self._log = log_writer
        self._limits = limits
        self._outcomes = outcome_service

    def monitor_positions(self) -> list[Trade]:
        """Evaluate every open position and close those that hit an exit rule."""
        closed: list[Trade] = []
        open_positions = self._positions.get_open()
        for position in open_positions:
            trade = self._evaluate(position)
            if trade is not None:
                closed.append(trade)
        self._log.log(
            event="position_monitor_completed",
            message=f"checked={len(open_positions)} closed={len(closed)}",
            metadata={"closed_trade_ids": [t.id for t in closed]},
        )
        return closed

    def _evaluate(self, position: Position) -> Trade | None:
        bars = self._source.get_price_history(position.ticker)
        if len(bars) < MIN_BARS:
            self._log.log(
                event="position_monitor_skipped",
                message=f"{position.ticker}: insufficient bars ({len(bars)})",
                level=LogLevel.WARNING,
                metadata={"position_id": position.id},
            )
            return None

        features = compute_features(position.ticker, bars)
        current_close = bars[-1].close
        holding_days = (datetime.now(UTC) - position.opened_at).days

        reason = evaluate_exit(
            current_close=current_close,
            stop_price=position.stop_price,
            target_price=position.target_price,
            sma_20=features.technical.sma_20,
            sma_50=features.technical.sma_50,
            holding_days=holding_days,
            max_hold_days=self._limits.max_hold_days,
        )
        if reason is None:
            return None
        return self._close(position, current_close, reason.value)

    def _close(self, position: Position, exit_price: float, reason: str) -> Trade | None:
        trade = self._trades.get(position.trade_id)
        if trade is None or trade.status != TradeStatus.OPEN:
            self._log.log(
                event="position_close_skipped",
                message=f"{position.ticker}: trade {position.trade_id} not open",
                level=LogLevel.WARNING,
                metadata={"position_id": position.id},
            )
            return None

        order = build_exit_order(position, exit_price)
        fill = self._broker.submit_order(order)

        realized_pnl = round((fill.fill_price - trade.entry_price) * trade.quantity - trade.fees, 2)
        closed_trade = trade.model_copy(
            update={
                "exit_time": fill.filled_at,
                "exit_price": fill.fill_price,
                "status": TradeStatus.CLOSED,
                "pnl": realized_pnl,
            }
        )
        self._trades.save(closed_trade)
        self._portfolio.apply_exit(position, fill.fill_price, trade.quantity, realized_pnl)

        self._log.log(
            event="position_closed",
            message=(
                f"{position.ticker}: {reason} @ {fill.fill_price} " f"(pnl {realized_pnl:.2f})"
            ),
            metadata={
                "position_id": position.id,
                "trade_id": closed_trade.id,
                "exit_reason": reason,
            },
        )
        if self._outcomes is not None:
            self._outcomes.record_from_close(closed_trade, reason)
        return closed_trade
