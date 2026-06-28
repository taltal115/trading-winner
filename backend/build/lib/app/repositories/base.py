"""Repository layer foundations.

Architecture rule (CODING_STANDARDS.md 5.1): business logic must never touch
the database directly. All persistence flows through repositories, which sit on
top of a ``DocumentStore`` abstraction. The in-memory store is used for dev and
tests; a Firestore-backed store can implement the same protocol later without
changing services or engines.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from app.models.entities import Entity


@runtime_checkable
class DocumentStore(Protocol):
    """Minimal document database surface (Firestore-compatible)."""

    def set(self, collection: str, doc_id: str, data: dict[str, object]) -> None: ...

    def get(self, collection: str, doc_id: str) -> dict[str, object] | None: ...

    def list(self, collection: str) -> list[dict[str, object]]: ...

    def delete(self, collection: str, doc_id: str) -> None: ...


class InMemoryDocumentStore:
    """Dict-backed store. Append/overwrite by id; no hidden state."""

    def __init__(self) -> None:
        self._data: dict[str, dict[str, dict[str, object]]] = {}

    def set(self, collection: str, doc_id: str, data: dict[str, object]) -> None:
        self._data.setdefault(collection, {})[doc_id] = data

    def get(self, collection: str, doc_id: str) -> dict[str, object] | None:
        return self._data.get(collection, {}).get(doc_id)

    def list(self, collection: str) -> list[dict[str, object]]:
        return list(self._data.get(collection, {}).values())

    def delete(self, collection: str, doc_id: str) -> None:
        self._data.get(collection, {}).pop(doc_id, None)


class Repository[ModelT: Entity]:
    """Typed CRUD wrapper around a ``DocumentStore`` collection."""

    collection: str
    model: type[ModelT]

    def __init__(self, store: DocumentStore) -> None:
        self._store = store

    def save(self, entity: ModelT) -> ModelT:
        self._store.set(self.collection, entity.id, entity.model_dump(mode="json"))
        return entity

    def get(self, doc_id: str) -> ModelT | None:
        raw = self._store.get(self.collection, doc_id)
        return self.model.model_validate(raw) if raw is not None else None

    def list(self) -> list[ModelT]:
        return [self.model.model_validate(raw) for raw in self._store.list(self.collection)]

    def delete(self, doc_id: str) -> None:
        self._store.delete(self.collection, doc_id)
