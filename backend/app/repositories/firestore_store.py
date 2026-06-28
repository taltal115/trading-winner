"""Firestore-backed ``DocumentStore`` (the production storage adapter).

This is the concrete implementation of the storage seam defined in
``repositories/base.py``. Repositories, services and engines are unchanged: they
depend only on the ``DocumentStore`` protocol, so swapping the in-memory store
for Firestore is a wiring decision (``repository_backend = "firestore"``).

Design:
- The ``google-cloud-firestore`` SDK is imported lazily so the package is only
  required when this backend is actually selected (dev/tests use memory).
- Documents are stored under flat, human-readable ids exactly as produced by the
  repositories (``collection/doc_id``), matching DATABASE.md (no nested paths,
  no hash ids). Repositories serialize with ``model_dump(mode="json")``, so
  Firestore receives JSON-safe dicts that round-trip cleanly via
  ``model_validate`` on read.
- A client may be injected for testing; production constructs a real client.
"""

from __future__ import annotations

from typing import Any, cast


class FirestoreDocumentStore:
    """Adapts Google Cloud Firestore to the ``DocumentStore`` protocol."""

    def __init__(self, project: str | None = None, client: Any = None) -> None:
        if client is not None:
            self._client = client
            return
        try:
            from google.cloud import firestore
        except ImportError as exc:  # pragma: no cover - exercised only without the SDK
            raise RuntimeError(
                "repository_backend='firestore' requires the google-cloud-firestore "
                "package. Install it with: pip install '.[firestore]'"
            ) from exc
        self._client = firestore.Client(project=project) if project else firestore.Client()

    def set(self, collection: str, doc_id: str, data: dict[str, object]) -> None:
        self._client.collection(collection).document(doc_id).set(data)

    def get(self, collection: str, doc_id: str) -> dict[str, object] | None:
        snapshot = self._client.collection(collection).document(doc_id).get()
        if not snapshot.exists:
            return None
        return cast("dict[str, object]", snapshot.to_dict())

    def list(self, collection: str) -> list[dict[str, object]]:
        documents = self._client.collection(collection).stream()
        return [cast("dict[str, object]", doc.to_dict()) for doc in documents]

    def delete(self, collection: str, doc_id: str) -> None:
        self._client.collection(collection).document(doc_id).delete()
