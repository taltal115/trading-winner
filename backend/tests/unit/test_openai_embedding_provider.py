"""Tests for the OpenAI embedding adapter.

A fake client mimics the ``openai`` embeddings surface
(client.embeddings.create -> .data[i].embedding) so we verify request shape,
vector parsing, empty-input short-circuit, error normalization, the missing-SDK
message and backend selection — without the SDK or any network call.
"""

from __future__ import annotations

from typing import Any

import pytest

from app.config.settings import Settings
from app.services.openai_embedding_provider import OpenAIEmbeddingProvider


class _FakeDatum:
    def __init__(self, embedding: list[float]) -> None:
        self.embedding = embedding


class _FakeResponse:
    def __init__(self, vectors: list[list[float]]) -> None:
        self.data = [_FakeDatum(v) for v in vectors]


class _FakeEmbeddings:
    def __init__(self, vectors: list[list[float]], raise_exc: Exception | None) -> None:
        self._vectors = vectors
        self._raise = raise_exc
        self.last_kwargs: dict[str, Any] = {}

    def create(self, **kwargs: Any) -> _FakeResponse:
        self.last_kwargs = kwargs
        if self._raise is not None:
            raise self._raise
        return _FakeResponse(self._vectors)


class _FakeOpenAI:
    def __init__(
        self,
        vectors: list[list[float]] | None = None,
        raise_exc: Exception | None = None,
    ) -> None:
        self.embeddings = _FakeEmbeddings(vectors or [], raise_exc)


def test_embed_parses_vectors() -> None:
    fake = _FakeOpenAI(vectors=[[0.1, 0.2], [0.3, 0.4]])
    provider = OpenAIEmbeddingProvider(model="text-embedding-3-large", client=fake)
    result = provider.embed(["a", "b"])
    assert result == [[0.1, 0.2], [0.3, 0.4]]
    assert fake.embeddings.last_kwargs["model"] == "text-embedding-3-large"
    assert fake.embeddings.last_kwargs["input"] == ["a", "b"]


def test_embedding_version_tracks_model() -> None:
    provider = OpenAIEmbeddingProvider(model="text-embedding-3-small", client=_FakeOpenAI())
    assert provider.embedding_version == "text-embedding-3-small-v1"


def test_empty_input_short_circuits_without_api_call() -> None:
    fake = _FakeOpenAI(raise_exc=AssertionError("should not be called"))
    assert OpenAIEmbeddingProvider(client=fake).embed([]) == []


def test_sdk_error_is_normalized_to_runtime_error() -> None:
    provider = OpenAIEmbeddingProvider(client=_FakeOpenAI(raise_exc=ValueError("boom")))
    with pytest.raises(RuntimeError, match="OpenAI embedding request failed"):
        provider.embed(["a"])


def test_missing_sdk_raises_helpful_error() -> None:
    with pytest.raises(RuntimeError, match="openai package"):
        OpenAIEmbeddingProvider()


def test_build_embedding_provider_selects_backend() -> None:
    from app.api.dependencies import _build_embedding_provider
    from app.services.embedding_provider import MockEmbeddingProvider

    assert isinstance(
        _build_embedding_provider(Settings(embedding_backend="mock")), MockEmbeddingProvider
    )
    with pytest.raises(RuntimeError, match="openai package"):
        _build_embedding_provider(Settings(embedding_backend="openai"))
    with pytest.raises(NotImplementedError):
        _build_embedding_provider(Settings(embedding_backend="cohere"))
