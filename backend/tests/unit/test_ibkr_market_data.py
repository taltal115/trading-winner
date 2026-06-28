"""Tests for the IBKR market-data adapter.

A fake SDK + client mimic the subset of ``ib_insync`` the adapter uses
(``Stock``/``ScannerSubscription`` factories, ``reqHistoricalData``,
``reqContractDetails``, ``reqHistoricalNews``, ``reqScannerData``) so we verify
bar/stock/news mapping, scanner-driven universe enrichment, and the
missing-SDK / backend-selection behavior — all without the SDK or a TWS session.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

import pytest

from app.config.settings import Settings
from app.models.enums import Sentiment
from app.services.ibkr_market_data import IBKRMarketDataSource


class _FakeBar:
    def __init__(self, bar_date: Any, close: float, volume: float) -> None:
        self.date = bar_date
        self.open = close - 1.0
        self.high = close + 1.0
        self.low = close - 2.0
        self.close = close
        self.volume = volume


class _FakeContract:
    def __init__(self, symbol: str) -> None:
        self.symbol = symbol
        self.conId = 12345
        self.primaryExchange = "NASDAQ"
        self.exchange = "SMART"


class _FakeContractDetails:
    def __init__(self, symbol: str) -> None:
        self.contract = _FakeContract(symbol)
        self.longName = "NVIDIA Corporation"
        self.industry = "Technology"
        self.category = "Semiconductors"
        self.marketCap = 2_000_000_000_000.0


class _FakeHeadline:
    def __init__(self, when: Any, headline: str) -> None:
        self.time = when
        self.headline = headline
        self.providerCode = "DJ"
        self.articleId = "a1"


class _FakeScanContract:
    def __init__(self, symbol: str) -> None:
        self.contractDetails = type("_CD", (), {"contract": _FakeContract(symbol)})()


class _FakeScannerSubscription:
    def __init__(self, instrument: str, locationCode: str, scanCode: str) -> None:
        self.instrument = instrument
        self.locationCode = locationCode
        self.scanCode = scanCode


class _FakeSDK:
    @staticmethod
    def Stock(symbol: str, exchange: str, currency: str) -> _FakeContract:
        return _FakeContract(symbol)

    ScannerSubscription = _FakeScannerSubscription


class _FakeIB:
    def __init__(self, scanner_symbols: list[str] | None = None) -> None:
        self._scanner_symbols = scanner_symbols or []

    def reqHistoricalData(self, contract: _FakeContract, **kwargs: Any) -> list[_FakeBar]:
        return [
            _FakeBar(date(2026, 7, 26), 98.0, 1_000_000.0),
            _FakeBar(datetime(2026, 7, 27, 16, 0), 99.0, 2_000_000.0),
            _FakeBar("2026-07-28", 100.0, 3_000_000.0),
        ]

    def reqContractDetails(self, contract: _FakeContract) -> list[_FakeContractDetails]:
        return [_FakeContractDetails(contract.symbol)]

    def reqHistoricalNews(self, *args: Any) -> list[_FakeHeadline]:
        return [
            _FakeHeadline(datetime(2026, 7, 28, 9, 0), "NVDA unveils new chip"),
            _FakeHeadline(date(2026, 7, 28), "Analysts raise targets"),
        ]

    def reqScannerData(self, subscription: _FakeScannerSubscription) -> list[_FakeScanContract]:
        return [_FakeScanContract(symbol) for symbol in self._scanner_symbols]


def _source(client: _FakeIB) -> IBKRMarketDataSource:
    return IBKRMarketDataSource(client=client, sdk=_FakeSDK())


def test_get_price_history_maps_bars_and_coerces_timestamps() -> None:
    bars = _source(_FakeIB()).get_price_history("NVDA")
    assert len(bars) == 3
    assert bars[-1].close == 100.0
    assert bars[-1].volume == 3_000_000.0
    # date, datetime and iso-string timestamps all coerce to aware UTC datetimes.
    assert all(b.timestamp.tzinfo is not None for b in bars)


def test_get_stock_maps_contract_details() -> None:
    stock = _source(_FakeIB()).get_stock("NVDA")
    assert stock.ticker == "NVDA"
    assert stock.name == "NVIDIA Corporation"
    assert stock.sector == "Technology"
    assert stock.market_cap == 2_000_000_000_000.0
    assert stock.exchange == "NASDAQ"
    assert stock.id.startswith("stock_NVDA_")


def test_get_news_maps_headlines_as_neutral() -> None:
    items = _source(_FakeIB()).get_news("NVDA")
    assert len(items) == 2
    assert items[0].headline == "NVDA unveils new chip"
    assert items[0].source == "DJ"
    # IBKR headlines carry no sentiment; classification happens downstream.
    assert all(item.sentiment == Sentiment.NEUTRAL for item in items)
    assert items[0].id != items[1].id  # distinct sequence-based ids


def test_get_universe_enriches_scanner_symbols() -> None:
    candidates = _source(_FakeIB(scanner_symbols=["NVDA", "AAPL"])).get_universe()
    tickers = {c.ticker for c in candidates}
    assert tickers == {"NVDA", "AAPL"}
    nvda = next(c for c in candidates if c.ticker == "NVDA")
    assert nvda.price == 100.0
    assert nvda.avg_volume == 2_000_000.0  # mean of the 3 fake bars
    assert nvda.market_cap == 2_000_000_000_000.0


def test_get_stock_missing_details_raises() -> None:
    class _NoDetailsIB(_FakeIB):
        def reqContractDetails(self, contract: _FakeContract) -> list[_FakeContractDetails]:
            return []

    with pytest.raises(RuntimeError, match="no contract details"):
        _source(_NoDetailsIB()).get_stock("NVDA")


def test_missing_sdk_raises_helpful_error() -> None:
    with pytest.raises(RuntimeError, match="ib_insync package"):
        IBKRMarketDataSource()


def test_build_source_selects_backend() -> None:
    from app.api.dependencies import _build_source
    from app.services.market_data import MockMarketDataSource

    assert isinstance(_build_source(Settings(market_data_backend="mock")), MockMarketDataSource)
    with pytest.raises(RuntimeError, match="ib_insync package"):
        _build_source(Settings(market_data_backend="ibkr"))
    with pytest.raises(NotImplementedError):
        _build_source(Settings(market_data_backend="finnhub"))
