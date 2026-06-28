from datetime import datetime, timedelta

import pytest

from app.engines import scoring_engine
from app.engines.feature_engine import MIN_BARS, compute_features
from app.engines.universe_filter_engine import (
    UniverseCandidate,
    UniverseThresholds,
    filter_universe,
)
from app.models.entities import PriceBar
from app.models.enums import SignalDecision


def _bars(ticker: str, n: int, start: float, step: float) -> list[PriceBar]:
    base = datetime(2026, 1, 1, 16, 0, 0)
    bars: list[PriceBar] = []
    for i in range(n):
        close = start + step * i
        bars.append(
            PriceBar(
                ticker=ticker,
                timestamp=base + timedelta(days=i),
                open=close - 0.5,
                high=close + 1.0,
                low=close - 1.0,
                close=close,
                volume=1_000_000 + (50_000 if i == n - 1 else 0),
            )
        )
    return bars


def test_universe_filter_thresholds() -> None:
    candidates = [
        UniverseCandidate(ticker="AAA", market_cap=2e9, avg_volume=2e6, price=50, active=True),
        UniverseCandidate(ticker="BBB", market_cap=5e8, avg_volume=2e6, price=50, active=True),
        UniverseCandidate(ticker="CCC", market_cap=2e9, avg_volume=2e6, price=3, active=True),
        UniverseCandidate(ticker="DDD", market_cap=2e9, avg_volume=2e6, price=50, active=False),
    ]
    passed = filter_universe(candidates, UniverseThresholds())
    assert [c.ticker for c in passed] == ["AAA"]


def test_feature_engine_requires_min_bars() -> None:
    with pytest.raises(ValueError):
        compute_features("NVDA", _bars("NVDA", MIN_BARS - 1, 100, 0.1))


def test_feature_engine_uptrend_produces_aligned_smas() -> None:
    features = compute_features("NVDA", _bars("NVDA", 260, 100, 0.5))
    assert features.id == "feature_NVDA_2026-09-17"
    assert features.technical.sma_20 > features.technical.sma_50 > features.technical.sma_200
    assert features.momentum.weekly_return > 0
    assert features.volume.relative_volume > 1.0


def test_scoring_uptrend_scores_higher_than_downtrend() -> None:
    up = compute_features("UP", _bars("UP", 260, 100, 0.5))
    down = compute_features("DN", _bars("DN", 260, 230, -0.5))
    up_score = scoring_engine.score_features(up)
    down_score = scoring_engine.score_features(down)
    assert up_score.final_score > down_score.final_score
    assert up_score.breakdown.momentum_score > down_score.breakdown.momentum_score


@pytest.mark.parametrize(
    "score,expected",
    [
        (90, SignalDecision.STRONG_BUY),
        (75, SignalDecision.BUY),
        (55, SignalDecision.WATCH),
        (40, SignalDecision.IGNORE),
    ],
)
def test_decision_thresholds(score: float, expected: SignalDecision) -> None:
    assert scoring_engine.decide(score) == expected


def test_ai_adjustment_cannot_break_determinism() -> None:
    features = compute_features("NVDA", _bars("NVDA", 260, 100, 0.5))
    base = scoring_engine.score_features(features)
    boosted = scoring_engine.score_features(features, ai_confidence_adjustment=0.1)
    assert boosted.adjusted_score >= base.adjusted_score
    assert base.final_score == boosted.final_score  # AI never changes FinalScore
