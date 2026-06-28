"""Interactive Brokers (IBKR) market-data adapter — production ``MarketDataSource``.

Concrete implementation of the market-data seam in ``market_data.py`` over the
``ib_insync`` SDK. Services and engines are unchanged: they depend only on the
``MarketDataSource`` protocol, so swapping the synthetic ``MockMarketDataSource``
for IBKR is a wiring decision (``market_data_backend = "ibkr"``).

Design (mirrors the Firestore / OpenAI adapters):
- ``ib_insync`` is imported lazily so the package is only required when this
  backend is selected (dev/tests use the deterministic mock). A helpful
  ``RuntimeError`` is raised if the SDK is missing.
- The SDK factory bundle (``IB``/``Stock``/``ScannerSubscription``) and a
  connected client may both be injected for testing, so the full adapter is
  exercised offline with an in-file fake mimicking the ``ib_insync`` surface.

Mapping notes (IBKR has no single "universe" call):
- ``get_universe`` runs a market scanner, then enriches each symbol via
  ``get_price_history``/``get_stock`` for price, liquidity and market cap so the
  downstream universe filter (TRADING_ENGINE.md) keeps working unchanged.
- IBKR headlines carry no sentiment; ``get_news`` reports ``NEUTRAL`` and leaves
  catalyst/sentiment classification to the AI pipeline.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any

from app.engines.universe_filter_engine import UniverseCandidate
from app.models.entities import NewsItem, PriceBar, Stock
from app.models.enums import Sentiment
from app.utils.ids import news_id, validate_ticker

_HISTORY_DURATION = "1 Y"
_BAR_SIZE = "1 day"
_SCAN_LOCATION = "STK.US.MAJOR"
_SCAN_CODE = "HOT_BY_VOLUME"
_MAX_NEWS = 10


def _import_sdk() -> Any:
    try:
        import ib_insync
    except ImportError as exc:  # pragma: no cover - exercised only without the SDK
        raise RuntimeError(
            "market_data_backend='ibkr' requires the ib_insync package. "
            "Install it with: pip install '.[ibkr]'"
        ) from exc
    return ib_insync


def _as_datetime(value: Any) -> datetime:
    """Coerce an IBKR bar/news timestamp (date | datetime | str) to aware UTC."""
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=UTC)
    if isinstance(value, date):
        return datetime(value.year, value.month, value.day, tzinfo=UTC)
    return datetime.fromisoformat(str(value)).replace(tzinfo=UTC)


class IBKRMarketDataSource:
    """Adapts the IBKR TWS/Gateway API (``ib_insync``) to ``MarketDataSource``."""

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 7497,
        client_id: int = 2,
        client: Any = None,
        sdk: Any = None,
    ) -> None:
        self._sdk = sdk if sdk is not None else _import_sdk()
        if client is not None:
            self._ib = client
            return
        self._ib = self._sdk.IB()
        self._ib.connect(host, port, clientId=client_id)

    def get_universe(self) -> list[UniverseCandidate]:
        subscription = self._sdk.ScannerSubscription(
            instrument="STK",
            locationCode=_SCAN_LOCATION,
            scanCode=_SCAN_CODE,
        )
        candidates: list[UniverseCandidate] = []
        for row in self._ib.reqScannerData(subscription):
            ticker = row.contractDetails.contract.symbol
            bars = self.get_price_history(ticker)
            if not bars:
                continue
            window = bars[-20:]
            avg_volume = sum(b.volume for b in window) / len(window)
            candidates.append(
                UniverseCandidate(
                    ticker=ticker,
                    market_cap=self.get_stock(ticker).market_cap,
                    avg_volume=avg_volume,
                    price=bars[-1].close,
                    active=True,
                )
            )
        return candidates

    def get_stock(self, ticker: str) -> Stock:
        details = self._contract_details(ticker)
        contract = details.contract
        bars = self.get_price_history(ticker)
        last_close = bars[-1].close if bars else 0.0
        market_cap = float(getattr(details, "marketCap", 0.0) or 0.0)
        now = datetime.now(UTC)
        return Stock(
            id=f"stock_{validate_ticker(ticker)}_{now.date().isoformat()}",
            ticker=ticker,
            name=getattr(details, "longName", "") or ticker,
            sector=getattr(details, "industry", "") or "Unknown",
            industry=getattr(details, "category", "") or "Unknown",
            market_cap=market_cap or last_close,
            exchange=getattr(contract, "primaryExchange", "")
            or getattr(contract, "exchange", "")
            or "SMART",
            last_updated=now,
        )

    def get_price_history(self, ticker: str) -> list[PriceBar]:
        contract = self._sdk.Stock(ticker, "SMART", "USD")
        bars = self._ib.reqHistoricalData(
            contract,
            endDateTime="",
            durationStr=_HISTORY_DURATION,
            barSizeSetting=_BAR_SIZE,
            whatToShow="TRADES",
            useRTH=True,
        )
        return [
            PriceBar(
                ticker=ticker,
                timestamp=_as_datetime(bar.date),
                open=float(bar.open),
                high=float(bar.high),
                low=float(bar.low),
                close=float(bar.close),
                volume=float(bar.volume),
            )
            for bar in bars
        ]

    def get_news(self, ticker: str) -> list[NewsItem]:
        details = self._contract_details(ticker)
        con_id = details.contract.conId
        headlines = self._ib.reqHistoricalNews(con_id, "", "", "", _MAX_NEWS)
        items: list[NewsItem] = []
        for sequence, headline in enumerate(headlines, start=1):
            timestamp = _as_datetime(headline.time)
            text = str(headline.headline)
            items.append(
                NewsItem(
                    id=news_id(ticker, timestamp, sequence),
                    ticker=ticker,
                    timestamp=timestamp,
                    headline=text,
                    source=getattr(headline, "providerCode", "") or "IBKR",
                    sentiment=Sentiment.NEUTRAL,  # classified downstream by the AI pipeline
                    relevance_score=0.5,
                    raw_text=text,
                )
            )
        return items

    def _contract_details(self, ticker: str) -> Any:
        contract = self._sdk.Stock(ticker, "SMART", "USD")
        details = self._ib.reqContractDetails(contract)
        if not details:
            raise RuntimeError(f"IBKR returned no contract details for {ticker!r}")
        return details[0]
