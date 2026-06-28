"""Feature engine: raw price bars -> engineered FeatureSnapshot.

Pure and deterministic (CODING_STANDARDS.md 7): no API calls, no DB access, no
side effects. Services are responsible for loading bars and persisting output.
"""

from __future__ import annotations

from app.models.entities import (
    FeatureSnapshot,
    MomentumFeatures,
    PriceBar,
    TechnicalFeatures,
    VolatilityFeatures,
    VolumeFeatures,
)
from app.utils import indicators
from app.utils.ids import feature_id

# 200 SMA + one prior bar for change-based indicators.
MIN_BARS = 201
_WEEK = 5
_MONTH = 21
_AVG_VOLUME_WINDOW = 20


def compute_features(ticker: str, bars: list[PriceBar]) -> FeatureSnapshot:
    """Compute a feature snapshot from chronologically ordered bars."""
    if len(bars) < MIN_BARS:
        raise ValueError(f"need >= {MIN_BARS} bars for {ticker}, got {len(bars)}")

    ordered = sorted(bars, key=lambda b: b.timestamp)
    closes = [b.close for b in ordered]
    highs = [b.high for b in ordered]
    lows = [b.low for b in ordered]
    volumes = [b.volume for b in ordered]
    latest = ordered[-1]

    avg_volume = indicators.sma(volumes, _AVG_VOLUME_WINDOW)
    relative_volume = volumes[-1] / avg_volume if avg_volume else 0.0

    technical = TechnicalFeatures(
        rsi=indicators.rsi(closes),
        macd=indicators.macd_line(closes),
        atr=indicators.atr(highs, lows, closes),
        sma_20=indicators.sma(closes, 20),
        sma_50=indicators.sma(closes, 50),
        sma_200=indicators.sma(closes, 200),
    )
    volume = VolumeFeatures(relative_volume=relative_volume, avg_volume=avg_volume)
    momentum = MomentumFeatures(
        daily_return=indicators.pct_return(closes, 1),
        weekly_return=indicators.pct_return(closes, _WEEK),
        monthly_return=indicators.pct_return(closes, _MONTH),
    )
    daily_returns = [closes[i] / closes[i - 1] - 1.0 for i in range(1, len(closes))]
    volatility = VolatilityFeatures(
        std_dev=indicators.stddev(daily_returns[-_MONTH:]),
        bollinger_width=indicators.bollinger_width(closes),
    )

    return FeatureSnapshot(
        id=feature_id(ticker, latest.timestamp),
        ticker=ticker,
        timestamp=latest.timestamp,
        technical=technical,
        volume=volume,
        momentum=momentum,
        volatility=volatility,
    )
