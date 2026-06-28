"""Tests for the deterministic mock embedding provider."""

from __future__ import annotations

import pytest

from app.engines.retrieval_engine import cosine_similarity
from app.services.embedding_provider import MockEmbeddingProvider


def test_embed_is_deterministic() -> None:
    provider = MockEmbeddingProvider()
    first = provider.embed(["NVIDIA announces new AI chip"])
    second = provider.embed(["NVIDIA announces new AI chip"])
    assert first == second


def test_embed_returns_one_vector_per_text() -> None:
    vectors = MockEmbeddingProvider(dim=32).embed(["a", "b", "c"])
    assert len(vectors) == 3
    assert all(len(v) == 32 for v in vectors)


def test_embeddings_are_unit_normalized() -> None:
    [vector] = MockEmbeddingProvider().embed(["chip demand accelerating"])
    norm = sum(value * value for value in vector) ** 0.5
    assert norm == pytest.approx(1.0)


def test_shared_tokens_are_more_similar_than_unrelated_text() -> None:
    provider = MockEmbeddingProvider()
    query, related, unrelated = provider.embed(
        [
            "nvidia ai chip partnership",
            "nvidia announces another ai chip",
            "oil prices fall on weak demand",
        ]
    )
    assert cosine_similarity(query, related) > cosine_similarity(query, unrelated)


def test_empty_text_yields_zero_vector() -> None:
    [vector] = MockEmbeddingProvider(dim=8).embed([""])
    assert vector == [0.0] * 8
