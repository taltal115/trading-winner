"""Backtest service: orchestrate engine runs, aggregate, persist.

Builds an equal-weight daily-rebalanced portfolio across the requested tickers
(a ticker contributes 0% on days it holds no position), then derives metrics
with the shared pure metric utilities.
"""

from __future__ import annotations

from datetime import UTC, date, datetime

from app.engines.backtest_engine import (
    BacktestParams,
    SimulatedTrade,
    TickerBacktest,
    run_backtest,
)
from app.models.entities import Backtest, BacktestMetrics
from app.models.enums import LogLevel
from app.repositories.repositories import BacktestRepository
from app.services.log_writer import LogWriter
from app.services.market_data import MarketDataSource
from app.utils import metrics
from app.utils.ids import backtest_id


class BacktestService:
    def __init__(
        self,
        backtest_repo: BacktestRepository,
        log_writer: LogWriter,
        source: MarketDataSource,
    ) -> None:
        self._backtests = backtest_repo
        self._log = log_writer
        self._source = source

    def run_backtest(
        self,
        tickers: list[str],
        strategy: str = "momentum_catalyst_v1",
        params: BacktestParams | None = None,
    ) -> Backtest:
        per_ticker: list[TickerBacktest] = []
        for ticker in tickers:
            try:
                bars = self._source.get_price_history(ticker)
                per_ticker.append(run_backtest(ticker, bars, params))
            except (ValueError, KeyError) as exc:
                self._log.log(
                    event="backtest_ticker_skipped",
                    message=f"{ticker} skipped: {exc}",
                    level=LogLevel.WARNING,
                    metadata={"ticker": ticker},
                )

        portfolio_returns, ordered_days = self._equal_weight_returns(per_ticker)
        all_trades = [t for r in per_ticker for t in r.trades]
        result = self._build_result(strategy, tickers, ordered_days, portfolio_returns, all_trades)
        self._backtests.save(result)
        self._log.log(
            event="backtest_completed",
            message=(
                f"{strategy}: trades={result.trade_count} "
                f"sharpe={result.metrics.sharpe:.2f} "
                f"return={result.metrics.total_return:.2%}"
            ),
            metadata={"backtest_id": result.id},
        )
        return result

    def list_backtests(self, strategy: str | None = None) -> list[Backtest]:
        if strategy is not None:
            return self._backtests.list_for_strategy(strategy)
        return self._backtests.list()

    def get_backtest(self, backtest_id_value: str) -> Backtest | None:
        return self._backtests.get(backtest_id_value)

    @staticmethod
    def _equal_weight_returns(
        per_ticker: list[TickerBacktest],
    ) -> tuple[list[float], list[date]]:
        by_day: dict[date, list[float]] = {}
        for ticker_result in per_ticker:
            for entry in ticker_result.daily_returns:
                by_day.setdefault(entry.day, []).append(entry.ret)
        ordered_days = sorted(by_day)
        portfolio_returns = [sum(by_day[d]) / len(by_day[d]) for d in ordered_days]
        return portfolio_returns, ordered_days

    def _build_result(
        self,
        strategy: str,
        tickers: list[str],
        ordered_days: list[date],
        portfolio_returns: list[float],
        all_trades: list[SimulatedTrade],
    ) -> Backtest:
        wins = sum(1 for t in all_trades if t.return_pct > 0)
        trade_count = len(all_trades)
        start_day = ordered_days[0] if ordered_days else date.today()
        end_day = ordered_days[-1] if ordered_days else start_day
        computed = BacktestMetrics(
            sharpe=round(metrics.sharpe_ratio(portfolio_returns), 4),
            win_rate=round(wins / trade_count, 4) if trade_count else 0.0,
            max_drawdown=round(metrics.max_drawdown(portfolio_returns), 4),
            total_return=round(metrics.total_return(portfolio_returns), 4),
        )
        return Backtest(
            id=backtest_id(strategy, start_day),
            strategy=strategy,
            start_date=start_day,
            end_date=end_day,
            tickers=tickers,
            trade_count=trade_count,
            metrics=computed,
            created_at=datetime.now(UTC),
        )
