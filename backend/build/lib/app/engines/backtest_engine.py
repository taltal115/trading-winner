"""Backtest engine: deterministic walk-forward replay.

Critical guarantee (CODING_STANDARDS.md 10, .cursor/rules.md 9/14): the backtest
reuses the SAME ``compute_features`` and ``score_features`` used live. There is
no parallel scoring path, so a strategy that backtests is the strategy that
trades. Exit logic follows TRADING_ENGINE.md section 8.

Modeling choices (documented, deterministic):
- One position per ticker at a time (no pyramiding).
- Entry and all exits transact at the bar close, so a trade's return equals the
  product of the daily mark-to-market returns over its holding period.
- Stop distance = min(atr_multiple * ATR, max_stop_pct * entry) -> the tighter
  (smaller-loss) stop, per "−2 ATR or −5% (whichever smaller)".
"""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, ConfigDict, Field

from app.engines.exit_engine import compute_stop_distance, evaluate_exit
from app.engines.feature_engine import MIN_BARS, compute_features
from app.engines.scoring_engine import score_features
from app.models.entities import PriceBar
from app.models.enums import ExitReason, SignalDecision


class BacktestParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    max_hold_days: int = 10
    profit_target: float = 0.12
    atr_stop_multiple: float = 2.0
    max_stop_pct: float = 0.05
    # Entry gate matches Phase 1's actionable/stored signal set (non-IGNORE).
    # Without catalyst inputs the quant-only FinalScore rarely reaches BUY (>=70),
    # so WATCH+ is the consistent live/backtest entry set. As catalyst scoring
    # comes online in Phase 3, this can tighten to BUY/STRONG_BUY.
    entry_decisions: tuple[SignalDecision, ...] = (
        SignalDecision.WATCH,
        SignalDecision.BUY,
        SignalDecision.STRONG_BUY,
    )


class SimulatedTrade(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ticker: str
    entry_date: date
    exit_date: date
    entry_price: float
    exit_price: float
    return_pct: float
    holding_days: int
    entry_score: float
    exit_reason: ExitReason


class DailyReturn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    day: date
    ret: float


class TickerBacktest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ticker: str
    trades: list[SimulatedTrade] = Field(default_factory=list)
    daily_returns: list[DailyReturn] = Field(default_factory=list)


class _OpenPosition(BaseModel):
    model_config = ConfigDict(extra="forbid")
    entry_index: int
    entry_price: float
    entry_date: date
    entry_score: float
    stop_price: float
    target_price: float


def _exit_reason(
    position: _OpenPosition,
    bar: PriceBar,
    sma_20: float,
    sma_50: float,
    holding_days: int,
    params: BacktestParams,
) -> ExitReason | None:
    return evaluate_exit(
        current_close=bar.close,
        stop_price=position.stop_price,
        target_price=position.target_price,
        sma_20=sma_20,
        sma_50=sma_50,
        holding_days=holding_days,
        max_hold_days=params.max_hold_days,
    )


def run_backtest(
    ticker: str,
    bars: list[PriceBar],
    params: BacktestParams | None = None,
) -> TickerBacktest:
    """Replay ``bars`` chronologically and return trades + daily returns."""
    active_params = params or BacktestParams()
    ordered = sorted(bars, key=lambda b: b.timestamp)

    result = TickerBacktest(ticker=ticker)
    position: _OpenPosition | None = None
    prev_close: float | None = None

    for i, bar in enumerate(ordered):
        day_ret = bar.close / prev_close - 1.0 if (position and prev_close) else 0.0
        result.daily_returns.append(DailyReturn(day=bar.timestamp.date(), ret=day_ret))
        prev_close = bar.close

        if i + 1 < MIN_BARS:
            continue

        features = compute_features(ticker, ordered[: i + 1])

        if position is not None:
            holding_days = i - position.entry_index
            reason = _exit_reason(
                position,
                bar,
                features.technical.sma_20,
                features.technical.sma_50,
                holding_days,
                active_params,
            )
            if reason is not None:
                result.trades.append(
                    SimulatedTrade(
                        ticker=ticker,
                        entry_date=position.entry_date,
                        exit_date=bar.timestamp.date(),
                        entry_price=position.entry_price,
                        exit_price=bar.close,
                        return_pct=bar.close / position.entry_price - 1.0,
                        holding_days=holding_days,
                        entry_score=position.entry_score,
                        exit_reason=reason,
                    )
                )
                position = None
        else:
            score = score_features(features)
            if score.decision in active_params.entry_decisions:
                stop_distance = compute_stop_distance(
                    bar.close,
                    features.technical.atr,
                    active_params.atr_stop_multiple,
                    active_params.max_stop_pct,
                )
                position = _OpenPosition(
                    entry_index=i,
                    entry_price=bar.close,
                    entry_date=bar.timestamp.date(),
                    entry_score=score.adjusted_score,
                    stop_price=bar.close - stop_distance,
                    target_price=bar.close * (1.0 + active_params.profit_target),
                )

    return result
