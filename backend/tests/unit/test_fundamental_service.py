from datetime import datetime

from app.engines.fundamental_engine import BANKRUPTCY_RISK
from app.repositories.base import InMemoryDocumentStore
from app.repositories.repositories import FundamentalRepository, LogRepository
from app.services.fundamental_data import MockFundamentalDataSource
from app.services.fundamental_service import FundamentalService
from app.services.log_writer import LogWriter

WHEN = datetime(2026, 7, 28, 16, 0, 0)


def _service() -> tuple[FundamentalService, FundamentalRepository]:
    store = InMemoryDocumentStore()
    repo = FundamentalRepository(store)
    service = FundamentalService(
        repo, MockFundamentalDataSource(), LogWriter("fundamental_engine", LogRepository(store))
    )
    return service, repo


def test_compute_persists_snapshot_with_readable_id() -> None:
    service, repo = _service()
    snapshot = service.compute_for_ticker("NVDA", WHEN)
    assert snapshot.id == "fundamental_NVDA_2026-07-28"
    assert repo.get(snapshot.id) is not None
    assert snapshot.date.isoformat() == "2026-07-28"
    assert snapshot.fundamental_score > 80.0
    assert snapshot.risk_flags == []
    assert snapshot.engine_version == "fundamental-v1"


def test_distressed_ticker_flags_bankruptcy() -> None:
    service, _ = _service()
    snapshot = service.compute_for_ticker("XYZ", WHEN)
    assert BANKRUPTCY_RISK in snapshot.risk_flags
    assert snapshot.fundamental_score < 20.0


def test_inputs_summary_is_populated() -> None:
    service, _ = _service()
    snapshot = service.compute_for_ticker("NVDA", WHEN)
    assert set(snapshot.inputs_summary) >= {
        "revenue_ttm",
        "earnings_ttm",
        "operating_cashflow_ttm",
        "total_debt",
        "debt_to_equity",
        "shares_outstanding_trend",
    }


def test_compute_for_tickers_returns_map() -> None:
    service, repo = _service()
    snapshots = service.compute_for_tickers(["NVDA", "AAPL"], WHEN)
    assert set(snapshots) == {"NVDA", "AAPL"}
    assert len(repo.list()) == 2
