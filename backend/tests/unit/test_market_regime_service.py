from datetime import datetime

from app.models.enums import ExposureRecommendation, RegimeState
from app.repositories.base import InMemoryDocumentStore
from app.repositories.repositories import LogRepository, MarketRegimeRepository
from app.services.log_writer import LogWriter
from app.services.market_regime_service import MarketRegimeService
from app.services.regime_data import MockMacroDataSource

WHEN = datetime(2026, 7, 28, 16, 0, 0)


def _service() -> tuple[MarketRegimeService, MarketRegimeRepository]:
    store = InMemoryDocumentStore()
    repo = MarketRegimeRepository(store)
    service = MarketRegimeService(
        repo, MockMacroDataSource(), LogWriter("market_regime_engine", LogRepository(store))
    )
    return service, repo


def test_compute_persists_snapshot_with_readable_id() -> None:
    service, repo = _service()
    snapshot = service.compute_regime(WHEN)
    assert snapshot.id == "regime_2026-07-28"
    assert repo.get(snapshot.id) is not None
    assert snapshot.regime_state is RegimeState.NEUTRAL
    assert snapshot.risk_multiplier == 1.0
    assert snapshot.exposure_recommendation is ExposureRecommendation.MEDIUM
    assert snapshot.engine_version == "market-regime-v1"


def test_inputs_summary_is_populated() -> None:
    service, _ = _service()
    snapshot = service.compute_regime(WHEN)
    assert set(snapshot.inputs_summary) == {
        "spy_trend",
        "vix",
        "sector_breadth",
        "market_momentum",
        "cross_stock_correlation",
    }


def test_get_latest_returns_most_recent() -> None:
    service, repo = _service()
    service.compute_regime(datetime(2026, 7, 27, 16, 0, 0))
    latest = service.compute_regime(WHEN)
    assert repo.get_latest() is not None
    assert repo.get_latest().id == latest.id
