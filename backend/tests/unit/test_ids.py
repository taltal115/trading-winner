from datetime import date, datetime

import pytest

from app.utils import ids


def test_feature_and_signal_ids() -> None:
    d = date(2026, 7, 28)
    assert ids.feature_id("NVDA", d) == "feature_NVDA_2026-07-28"
    assert ids.signal_id("NVDA", d) == "signal_NVDA_2026-07-28"


def test_trade_id_includes_time() -> None:
    dt = datetime(2026, 7, 28, 9, 30, 15)
    assert ids.trade_id("NVDA", dt) == "trade_NVDA_2026-07-28_093015"


def test_news_id_sequence() -> None:
    assert ids.news_id("NVDA", date(2026, 7, 28), 1) == "news_NVDA_2026-07-28_1"


def test_invalid_ticker_rejected() -> None:
    with pytest.raises(ValueError):
        ids.feature_id("nvda", date(2026, 7, 28))


@pytest.mark.parametrize(
    "value",
    [
        "signal_NVDA_2026-07-28",
        "trade_NVDA_2026-07-28_093015",
        "news_NVDA_2026-07-28_1",
        "job_market_ingestion_2026-07-28_093000",
        "log_signal_engine_2026-07-28_093000_1",
    ],
)
def test_valid_ids(value: str) -> None:
    assert ids.is_valid_id(value)


@pytest.mark.parametrize(
    "value",
    [
        "a1b2c3d4e5f6a7b8c9d0e1f2",  # hash-like
        "signal_3f9a2b8c1d4e5f6a7b8c9d0e",  # trailing hash
        "noseparator",
    ],
)
def test_invalid_ids(value: str) -> None:
    assert not ids.is_valid_id(value)
