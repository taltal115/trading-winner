"""Tests for the pure RAG retrieval engine (cosine similarity + ranking)."""

from __future__ import annotations

import math

import pytest

from app.engines.retrieval_engine import (
    RetrievalDocument,
    cosine_similarity,
    rank_by_similarity,
)


def test_cosine_similarity_identical_vectors_is_one() -> None:
    assert cosine_similarity([1.0, 2.0, 3.0], [1.0, 2.0, 3.0]) == pytest.approx(1.0)


def test_cosine_similarity_orthogonal_is_zero() -> None:
    assert cosine_similarity([1.0, 0.0], [0.0, 1.0]) == pytest.approx(0.0)


def test_cosine_similarity_opposite_is_negative_one() -> None:
    assert cosine_similarity([1.0, 0.0], [-1.0, 0.0]) == pytest.approx(-1.0)


def test_cosine_similarity_zero_vector_is_zero() -> None:
    assert cosine_similarity([0.0, 0.0], [1.0, 1.0]) == 0.0


def test_cosine_similarity_dimension_mismatch_raises() -> None:
    with pytest.raises(ValueError, match="dimension mismatch"):
        cosine_similarity([1.0], [1.0, 2.0])


def _doc(text: str, embedding: list[float]) -> RetrievalDocument:
    return RetrievalDocument(text=text, embedding=embedding)


def test_rank_orders_by_similarity_and_limits_top_k() -> None:
    query = [1.0, 0.0]
    docs = [
        _doc("aligned", [1.0, 0.0]),
        _doc("partial", [1.0, 1.0]),
        _doc("orthogonal", [0.0, 1.0]),
    ]
    ranked = rank_by_similarity(query, docs, top_k=2)
    assert [r.text for r in ranked] == ["aligned", "partial"]
    assert ranked[0].score == pytest.approx(1.0)
    assert ranked[1].score == pytest.approx(math.sqrt(0.5))


def test_rank_drops_documents_below_min_score() -> None:
    query = [1.0, 0.0]
    docs = [_doc("aligned", [1.0, 0.0]), _doc("opposite", [-1.0, 0.0])]
    ranked = rank_by_similarity(query, docs, top_k=5, min_score=0.0)
    assert [r.text for r in ranked] == ["aligned"]


def test_rank_empty_corpus_returns_empty() -> None:
    assert rank_by_similarity([1.0, 0.0], [], top_k=5) == []
