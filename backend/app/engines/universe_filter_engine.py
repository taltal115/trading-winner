"""Stage 1 universe filter (TRADING_ENGINE.md).

Reduces the full equity universe to liquid, tradable candidates using hard
deterministic thresholds. Pure: no I/O, no side effects.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class UniverseCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ticker: str
    market_cap: float
    avg_volume: float
    price: float
    active: bool


class UniverseThresholds(BaseModel):
    model_config = ConfigDict(extra="forbid")

    min_market_cap: float = 1_000_000_000.0
    min_avg_volume: float = 1_000_000.0
    min_price: float = 5.0


def passes_universe_filter(
    candidate: UniverseCandidate,
    thresholds: UniverseThresholds,
) -> bool:
    return (
        candidate.active
        and candidate.market_cap > thresholds.min_market_cap
        and candidate.avg_volume > thresholds.min_avg_volume
        and candidate.price > thresholds.min_price
    )


def filter_universe(
    candidates: list[UniverseCandidate],
    thresholds: UniverseThresholds | None = None,
) -> list[UniverseCandidate]:
    active_thresholds = thresholds or UniverseThresholds()
    return [c for c in candidates if passes_universe_filter(c, active_thresholds)]
