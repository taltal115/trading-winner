"""Tests for the Firestore adapter.

We cannot reach a live Firestore here, so a small in-memory fake that mimics the
``google-cloud-firestore`` client surface (collection -> document -> set/get/
delete and collection.stream) is injected. This verifies the adapter maps the
``DocumentStore`` protocol onto the SDK API correctly and that repositories work
unchanged on top of it.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.config.settings import Settings
from app.models.entities import Stock
from app.repositories.base import DocumentStore
from app.repositories.firestore_store import FirestoreDocumentStore
from app.repositories.repositories import StockRepository


class _FakeSnapshot:
    def __init__(self, data: dict[str, object] | None) -> None:
        self._data = data

    @property
    def exists(self) -> bool:
        return self._data is not None

    def to_dict(self) -> dict[str, object] | None:
        return self._data


class _FakeDocRef:
    def __init__(self, bucket: dict[str, dict[str, object]], doc_id: str) -> None:
        self._bucket = bucket
        self._doc_id = doc_id

    def set(self, data: dict[str, object]) -> None:
        self._bucket[self._doc_id] = dict(data)

    def get(self) -> _FakeSnapshot:
        return _FakeSnapshot(self._bucket.get(self._doc_id))

    def delete(self) -> None:
        self._bucket.pop(self._doc_id, None)


class _FakeCollection:
    def __init__(self, bucket: dict[str, dict[str, object]]) -> None:
        self._bucket = bucket

    def document(self, doc_id: str) -> _FakeDocRef:
        return _FakeDocRef(self._bucket, doc_id)

    def stream(self) -> list[_FakeSnapshot]:
        return [_FakeSnapshot(data) for data in self._bucket.values()]


class _FakeFirestoreClient:
    def __init__(self) -> None:
        self._data: dict[str, dict[str, dict[str, object]]] = {}

    def collection(self, name: str) -> _FakeCollection:
        return _FakeCollection(self._data.setdefault(name, {}))


def _store() -> FirestoreDocumentStore:
    return FirestoreDocumentStore(client=_FakeFirestoreClient())


def test_satisfies_document_store_protocol() -> None:
    assert isinstance(_store(), DocumentStore)


def test_set_get_round_trip() -> None:
    store = _store()
    store.set("stocks", "stock_NVDA_2026-07-28", {"ticker": "NVDA", "active": True})
    assert store.get("stocks", "stock_NVDA_2026-07-28") == {"ticker": "NVDA", "active": True}


def test_get_missing_returns_none() -> None:
    assert _store().get("stocks", "stock_MISSING_2026-07-28") is None


def test_list_returns_all_documents() -> None:
    store = _store()
    store.set("signals", "signal_NVDA_2026-07-28", {"score": 80})
    store.set("signals", "signal_AAPL_2026-07-28", {"score": 60})
    scores = sorted(doc["score"] for doc in store.list("signals"))
    assert scores == [60, 80]


def test_delete_removes_document() -> None:
    store = _store()
    store.set("signals", "signal_NVDA_2026-07-28", {"score": 80})
    store.delete("signals", "signal_NVDA_2026-07-28")
    assert store.get("signals", "signal_NVDA_2026-07-28") is None


def test_repository_persists_through_adapter() -> None:
    repo = StockRepository(_store())
    stock = Stock(
        id="stock_NVDA_2026-07-28",
        ticker="NVDA",
        name="NVIDIA",
        sector="Technology",
        industry="Semis",
        market_cap=2e12,
        exchange="NASDAQ",
        last_updated=datetime(2026, 7, 28, tzinfo=UTC),
    )
    repo.save(stock)

    loaded = repo.get("stock_NVDA_2026-07-28")
    assert loaded is not None
    assert loaded.ticker == "NVDA"
    assert repo.get_by_ticker("NVDA") is not None


def test_missing_sdk_raises_helpful_error() -> None:
    # No client injected and the SDK isn't installed in the test env.
    with pytest.raises(RuntimeError, match="google-cloud-firestore"):
        FirestoreDocumentStore()


def test_build_store_selects_firestore_backend() -> None:
    from app.api.dependencies import _build_store

    settings = Settings(repository_backend="firestore")
    # Construction reaches the Firestore branch; without the SDK it raises.
    with pytest.raises(RuntimeError, match="google-cloud-firestore"):
        _build_store(settings)


def test_build_store_unknown_backend_raises() -> None:
    from app.api.dependencies import _build_store

    with pytest.raises(NotImplementedError):
        _build_store(Settings(repository_backend="postgres"))
