"""RAG retrieval ranking engine (AI_PIPELINE.md section 5).

Pure: no I/O, no side effects. Given a query embedding and a corpus of embedded
documents, ranks them by cosine similarity and returns the top matches. The
embedding provider (external boundary) and the corpus source (repositories) live
in the service layer; this engine only does deterministic math so retrieval is
reproducible and unit-testable offline.
"""

from __future__ import annotations

import math

from pydantic import BaseModel, ConfigDict


class RetrievalDocument(BaseModel):
    """A candidate document paired with its precomputed embedding."""

    model_config = ConfigDict(extra="forbid")

    text: str
    embedding: list[float]


class ScoredDocument(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str
    score: float


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Cosine similarity in [-1, 1]; 0.0 when either vector is degenerate."""
    if len(a) != len(b):
        raise ValueError(f"embedding dimension mismatch: {len(a)} != {len(b)}")
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


def rank_by_similarity(
    query: list[float],
    documents: list[RetrievalDocument],
    top_k: int,
    min_score: float = 0.0,
) -> list[ScoredDocument]:
    """Return the ``top_k`` documents most similar to ``query``.

    Documents scoring below ``min_score`` are dropped so only positively
    relevant context is injected into the prompt (noise control). Ties preserve
    corpus order for determinism (Python's stable sort).
    """
    scored = [
        ScoredDocument(text=doc.text, score=cosine_similarity(query, doc.embedding))
        for doc in documents
    ]
    relevant = [s for s in scored if s.score >= min_score]
    relevant.sort(key=lambda s: s.score, reverse=True)
    return relevant[:top_k]
