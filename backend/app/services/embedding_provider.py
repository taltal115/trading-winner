"""Embedding provider abstraction (external embedding-model boundary).

This is the seam where the real OpenAI embedding model plugs in (AI_PIPELINE.md
section 8). Providers turn text into dense vectors; the RAG retrieval engine
ranks by cosine similarity. The default ``MockEmbeddingProvider`` is fully
deterministic so similarity search runs offline without API cost.
"""

from __future__ import annotations

import hashlib
import math
from typing import Protocol

_DEFAULT_DIM = 64


class EmbeddingProvider(Protocol):
    embedding_version: str

    def embed(self, texts: list[str]) -> list[list[float]]: ...


class MockEmbeddingProvider:
    """Deterministic hashing embedding for dev/tests.

    Each token is hashed into a fixed-dimension bag-of-words vector (with a
    sign bit), then L2-normalized. Texts that share tokens land near each other
    under cosine similarity, so the full RAG path is exercised reproducibly
    without a network call.
    """

    embedding_version = "mock-embed-v1"

    def __init__(self, dim: int = _DEFAULT_DIM) -> None:
        self._dim = dim

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [self._embed_one(text) for text in texts]

    def _embed_one(self, text: str) -> list[float]:
        vector = [0.0] * self._dim
        for token in text.lower().split():
            digest = int(hashlib.sha256(token.encode("utf-8")).hexdigest(), 16)
            index = digest % self._dim
            sign = 1.0 if (digest >> 8) % 2 == 0 else -1.0
            vector[index] += sign
        norm = math.sqrt(sum(value * value for value in vector))
        if norm == 0.0:
            return vector
        return [value / norm for value in vector]
