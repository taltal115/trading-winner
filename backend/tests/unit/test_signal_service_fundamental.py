from datetime import datetime

from app.engines.fundamental_engine import BANKRUPTCY_RISK
from app.models.entities import (
    FeatureSnapshot,
    FundamentalSnapshot,
    MomentumFeatures,
    QualitySubscores,
    TechnicalFeatures,
    VolatilityFeatures,
    VolumeFeatures,
)
from app.repositories.base import InMemoryDocumentStore
from app.repositories.repositories import LogRepository, SignalRepository
from app.services.log_writer import LogWriter
from app.services.signal_service import SignalService

TS = datetime(2026, 7, 28, 16, 0, 0)


def _feature() -> FeatureSnapshot:
    return FeatureSnapshot(
        id="feature_NVDA_2026-07-28",
        ticker="NVDA",
        timestamp=TS,
        technical=TechnicalFeatures(rsi=60, macd=1.0, atr=4.0, sma_20=10, sma_50=9, sma_200=8),
        volume=VolumeFeatures(relative_volume=2.0, avg_volume=1_000_000),
        momentum=MomentumFeatures(daily_return=0.01, weekly_return=0.05, monthly_return=0.1),
        volatility=VolatilityFeatures(std_dev=0.02, bollinger_width=0.08),
    )


def _fundamental(score: float, flags: list[str] | None = None) -> FundamentalSnapshot:
    return FundamentalSnapshot(
        id="fundamental_NVDA_2026-07-28",
        ticker="NVDA",
        date=TS.date(),
        timestamp=TS,
        fundamental_score=score,
        quality_subscores=QualitySubscores(
            profitability_score=score,
            growth_score=score,
            leverage_score=score,
            cashflow_score=score,
        ),
        risk_flags=flags or [],
    )


def _service() -> SignalService:
    store = InMemoryDocumentStore()
    return SignalService(SignalRepository(store), LogWriter("signal_engine", LogRepository(store)))


def test_no_fundamental_is_unchanged_baseline() -> None:
    signal = _service().generate_signal(_feature())
    assert signal is not None
    assert signal.fundamental_id is None
    assert signal.market_regime_id is None


def test_high_quality_bias_boosts_score() -> None:
    baseline = _service().generate_signal(_feature())
    biased = _service().generate_signal(_feature(), fundamental=_fundamental(90.0))
    assert baseline is not None and biased is not None
    assert biased.score > baseline.score
    assert biased.fundamental_id == "fundamental_NVDA_2026-07-28"


def test_market_regime_id_is_recorded() -> None:
    signal = _service().generate_signal(_feature(), market_regime_id="regime_2026-07-28")
    assert signal is not None
    assert signal.market_regime_id == "regime_2026-07-28"


def test_bankruptcy_flag_forces_ignore() -> None:
    signal = _service().generate_signal(
        _feature(), fundamental=_fundamental(85.0, [BANKRUPTCY_RISK])
    )
    assert signal is None  # hard veto -> IGNORE, not stored


def test_low_score_forces_ignore() -> None:
    signal = _service().generate_signal(_feature(), fundamental=_fundamental(10.0))
    assert signal is None  # below the veto threshold -> IGNORE
