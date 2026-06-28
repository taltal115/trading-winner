"""Portfolio service: account equity/cash and live position state.

Owns the read model the risk engine needs (open-position count, sector
exposure, cash, duplicate check) and applies fills to positions/cash. This is
the only place that mutates portfolio state.
"""

from __future__ import annotations

from datetime import UTC, datetime

from app.models.entities import Portfolio, Position, Trade
from app.repositories.repositories import PortfolioRepository, PositionRepository
from app.services.log_writer import LogWriter
from app.utils.ids import portfolio_id, position_id

_DEFAULT_NAME = "main"
_DEFAULT_EQUITY = 100_000.0


class PortfolioService:
    def __init__(
        self,
        portfolio_repo: PortfolioRepository,
        position_repo: PositionRepository,
        log_writer: LogWriter,
        starting_equity: float = _DEFAULT_EQUITY,
    ) -> None:
        self._portfolios = portfolio_repo
        self._positions = position_repo
        self._log = log_writer
        self._starting_equity = starting_equity

    def get_or_create_portfolio(self) -> Portfolio:
        existing = self._portfolios.get(portfolio_id(_DEFAULT_NAME))
        if existing is not None:
            return existing
        portfolio = Portfolio(
            id=portfolio_id(_DEFAULT_NAME),
            name=_DEFAULT_NAME,
            equity=self._starting_equity,
            cash=self._starting_equity,
            updated_at=datetime.now(UTC),
        )
        return self._portfolios.save(portfolio)

    def open_positions(self) -> list[Position]:
        return self._positions.get_open()

    def open_position_count(self) -> int:
        return len(self._positions.get_open())

    def holding(self, ticker: str) -> bool:
        return self._positions.get_for_ticker(ticker) is not None

    def sector_exposure(self, sector: str) -> float:
        return sum(p.market_value for p in self._positions.get_open() if p.sector == sector)

    def apply_fill(
        self,
        trade: Trade,
        sector: str,
        fill_price: float,
        quantity: float,
        stop_price: float,
        target_price: float,
    ) -> Position:
        """Record a new position and debit cash. Assumes a fresh long entry."""
        notional = fill_price * quantity
        portfolio = self.get_or_create_portfolio()
        position = Position(
            id=position_id(trade.ticker, trade.entry_time),
            ticker=trade.ticker,
            sector=sector,
            quantity=quantity,
            avg_entry_price=fill_price,
            market_value=notional,
            unrealized_pnl=0.0,
            risk_exposure=round(notional / portfolio.equity, 4) if portfolio.equity else 0.0,
            stop_price=stop_price,
            target_price=target_price,
            opened_at=trade.entry_time,
            trade_id=trade.id,
        )
        self._positions.save(position)

        updated = portfolio.model_copy(
            update={"cash": portfolio.cash - notional, "updated_at": datetime.now(UTC)}
        )
        self._portfolios.save(updated)
        self._log.log(
            event="position_opened",
            message=f"{trade.ticker}: {quantity} @ {fill_price} (notional {notional:.2f})",
            metadata={"position_id": position.id, "trade_id": trade.id},
        )
        return position

    def apply_exit(
        self,
        position: Position,
        exit_price: float,
        quantity: float,
        realized_pnl: float,
    ) -> Position:
        """Close a position: credit proceeds to cash and realize PnL into equity.

        The position record is retained (quantity zeroed) for traceability rather
        than deleted, so the trade remains reconstructable end-to-end.
        """
        proceeds = exit_price * quantity
        portfolio = self.get_or_create_portfolio()
        closed = position.model_copy(
            update={"quantity": 0.0, "market_value": 0.0, "unrealized_pnl": 0.0}
        )
        self._positions.save(closed)

        updated = portfolio.model_copy(
            update={
                "cash": portfolio.cash + proceeds,
                "equity": portfolio.equity + realized_pnl,
                "updated_at": datetime.now(UTC),
            }
        )
        self._portfolios.save(updated)
        self._log.log(
            event="position_closed",
            message=(
                f"{position.ticker}: {quantity} @ {exit_price} "
                f"(proceeds {proceeds:.2f}, pnl {realized_pnl:.2f})"
            ),
            metadata={"position_id": position.id, "trade_id": position.trade_id},
        )
        return closed
