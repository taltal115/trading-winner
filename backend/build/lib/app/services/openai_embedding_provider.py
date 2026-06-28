"""OpenAI embedding provider — the production ``EmbeddingProvider`` adapter.

Concrete implementation of the embedding seam in ``embedding_provider.py``
(AI_PIPELINE.md section 8: ``text-embedding-3-large`` or equivalent). Mirrors the
OpenAI reasoning adapter: the ``openai`` SDK is imported lazily (reuses the
``[openai]`` extra), a client may be injected for testing, and any SDK error is
normalized to ``RuntimeError`` so the retrieval service degrades gracefully to
"no retrieved context" rather than breaking the (enrichment-only) AI path.
"""

from __future__ import annotations

from typing import Any


class OpenAIEmbeddingProvider:
    """Adapts the OpenAI Embeddings API to the ``EmbeddingProvider`` protocol."""

    def __init__(
        self,
        model: str = "text-embedding-3-large",
        api_key: str | None = None,
        client: Any = None,
    ) -> None:
        self._model = model
        self.embedding_version = f"{model}-v1"
        if client is not None:
            self._client = client
            return
        try:
            from openai import OpenAI
        except ImportError as exc:  # pragma: no cover - exercised only without the SDK
            raise RuntimeError(
                "embedding_backend='openai' requires the openai package. "
                "Install it with: pip install '.[openai]'"
            ) from exc
        self._client = OpenAI(api_key=api_key) if api_key else OpenAI()

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        try:
            response = self._client.embeddings.create(model=self._model, input=texts)
            return [list(item.embedding) for item in response.data]
        except Exception as exc:  # normalize SDK errors -> retrieval degrades gracefully
            raise RuntimeError(f"OpenAI embedding request failed: {exc}") from exc
