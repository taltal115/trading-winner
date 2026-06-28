"""Pure technical-indicator math.

No I/O, no side effects, deterministic. These functions are the shared
primitives used by the feature engine and (later) the backtest engine so live
and historical computations stay identical.
"""

from __future__ import annotations

from statistics import fmean, pstdev


def sma(values: list[float], period: int) -> float:
    """Simple moving average of the most recent ``period`` values."""
    if len(values) < period:
        raise ValueError(f"need {period} values for SMA, got {len(values)}")
    return fmean(values[-period:])


def ema(values: list[float], period: int) -> float:
    """Exponential moving average (seeded with the leading SMA)."""
    if len(values) < period:
        raise ValueError(f"need {period} values for EMA, got {len(values)}")
    multiplier = 2.0 / (period + 1)
    result = fmean(values[:period])
    for value in values[period:]:
        result = (value - result) * multiplier + result
    return result


def rsi(closes: list[float], period: int = 14) -> float:
    """Wilder's RSI over ``period`` closes. Returns 0-100."""
    if len(closes) < period + 1:
        raise ValueError(f"need {period + 1} closes for RSI, got {len(closes)}")
    gains: list[float] = []
    losses: list[float] = []
    for prev, curr in zip(closes[-period - 1 :], closes[-period:], strict=False):
        change = curr - prev
        gains.append(max(change, 0.0))
        losses.append(max(-change, 0.0))
    avg_gain = fmean(gains)
    avg_loss = fmean(losses)
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100.0 - (100.0 / (1.0 + rs))


def macd_line(closes: list[float], fast: int = 12, slow: int = 26) -> float:
    """MACD line = EMA(fast) - EMA(slow)."""
    return ema(closes, fast) - ema(closes, slow)


def atr(highs: list[float], lows: list[float], closes: list[float], period: int = 14) -> float:
    """Average True Range (simple mean of true ranges over ``period``)."""
    if not (len(highs) == len(lows) == len(closes)):
        raise ValueError("highs, lows, closes must be equal length")
    if len(closes) < period + 1:
        raise ValueError(f"need {period + 1} bars for ATR, got {len(closes)}")
    true_ranges: list[float] = []
    for i in range(1, len(closes)):
        high_low = highs[i] - lows[i]
        high_close = abs(highs[i] - closes[i - 1])
        low_close = abs(lows[i] - closes[i - 1])
        true_ranges.append(max(high_low, high_close, low_close))
    return fmean(true_ranges[-period:])


def stddev(values: list[float]) -> float:
    """Population standard deviation."""
    if len(values) < 2:
        raise ValueError("need at least 2 values for stddev")
    return pstdev(values)


def bollinger_width(closes: list[float], period: int = 20, num_std: float = 2.0) -> float:
    """(upper - lower) / middle band width, a unitless volatility measure."""
    middle = sma(closes, period)
    if middle == 0:
        return 0.0
    deviation = stddev(closes[-period:])
    return (2 * num_std * deviation) / middle


def pct_return(values: list[float], lookback: int) -> float:
    """Percentage return over ``lookback`` periods."""
    if len(values) <= lookback:
        raise ValueError(f"need {lookback + 1} values, got {len(values)}")
    past = values[-lookback - 1]
    if past == 0:
        return 0.0
    return values[-1] / past - 1.0
