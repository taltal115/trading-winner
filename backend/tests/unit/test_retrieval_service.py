"""Tests for the RAG retrieval service over the news/analysis corpus."""

from __future__ import annotations

from datetime import UTC, datetime

from app.models.entities import AiAnalysis, NewsItem
from app.models.enums import CatalystDirection, CatalystType, Sentiment
from app.repositories.base import InMemoryDocumentStore
from app.repositories.repositories import (
    AiAnalysisRepository,
    EmbeddingRepository,
    LogRepository,
    NewsRepository,
)
from app.services.embedding_provider import MockEmbeddingProvider
from app.services.log_writer import LogWriter
from app.services.retrieval_service import RetrievalService

TS = datetime(2026, 7, 28, 10, 0, 0, tzinfo=UTC)


def _news(seq: int, headline: str) -> NewsItem:
    return NewsItem(
        id=f"news_NVDA_2026-07-28_{seq}",
        ticker="NVDA",
        timestamp=TS,
        headline=headline,
        source="Reuters",
        sentiment=Sentiment.NEUTRAL,
        relevance_score=0.8,
    )


def _analysis(summary: str) -> AiAnalysis:
    return AiAnalysis(
        id="ai_NVDA_2026-07-28",
        related_id="signal_NVDA_2026-07-28",
        ticker="NVDA",
        summary=summary,
        catalyst_type=CatalystType.NEWS,
        catalyst_direction=CatalystDirection.BULLISH,
        ai_bias=0.2,
        sentiment=Sentiment.POSITIVE,
        confidence=0.7,
        confidence_adjustment=0.05,
        reasoning_version="mock-v1",
    )


def _service(
    news: list[NewsItem],
    analyses: list[AiAnalysis],
    embeddings: object | None = None,
    top_k: int = 5,
    embedding_repo: EmbeddingRepository | None = None,
) -> RetrievalService:
    store = InMemoryDocumentStore()
    news_repo = NewsRepository(store)
    ai_repo = AiAnalysisRepository(store)
    for item in news:
        news_repo.save(item)
    for analysis in analyses:
        ai_repo.save(analysis)
    log = LogWriter("retrieval_service", LogRepository(store))
    provider = embeddings or MockEmbeddingProvider()
    repo = embedding_repo or EmbeddingRepository(store)
    return RetrievalService(news_repo, ai_repo, repo, provider, log, top_k)  # type: ignore[arg-type]


def test_retrieves_semantically_similar_documents_first() -> None:
    service = _service(
        news=[
            _news(1, "nvidia announces new ai chip partnership"),
            _news(2, "oil prices fall on weak global demand"),
        ],
        analyses=[],
    )
    context = service.retrieve("NVDA", ["nvidia ai chip deal expands"])
    assert context[0] == "nvidia announces new ai chip partnership"


def test_excludes_the_current_events_own_text() -> None:
    query = "nvidia announces new ai chip partnership"
    service = _service(news=[_news(1, query)], analyses=[])
    assert service.retrieve("NVDA", [query]) == []


def test_top_k_limits_results() -> None:
    service = _service(
        news=[_news(i, f"ai chip story number {i}") for i in range(1, 6)],
        analyses=[],
        top_k=2,
    )
    assert len(service.retrieve("NVDA", ["ai chip"])) == 2


def test_empty_corpus_returns_empty() -> None:
    assert _service(news=[], analyses=[]).retrieve("NVDA", ["ai chip"]) == []


def test_blank_query_returns_empty() -> None:
    service = _service(news=[_news(1, "ai chip news")], analyses=[])
    assert service.retrieve("NVDA", ["", "  "]) == []


def test_past_analysis_summaries_are_part_of_corpus() -> None:
    service = _service(
        news=[],
        analyses=[_analysis("prior ai chip catalyst played out bullishly")],
    )
    context = service.retrieve("NVDA", ["new ai chip catalyst"])
    assert context == ["prior ai chip catalyst played out bullishly"]


def test_embedding_failure_degrades_to_empty_context() -> None:
    class _FailingEmbeddings:
        embedding_version = "failing-v1"

        def embed(self, texts: list[str]) -> list[list[float]]:
            raise RuntimeError("embedding API down")

    service = _service(
        news=[_news(1, "ai chip news")],
        analyses=[],
        embeddings=_FailingEmbeddings(),
    )
    assert service.retrieve("NVDA", ["ai chip"]) == []


def test_embedding_version_is_exposed() -> None:
    assert _service(news=[], analyses=[]).embedding_version == "mock-embed-v1"


class _CountingEmbeddings:
    """Wraps the mock provider, counting how many times embed() is called."""

    def __init__(self, version: str = "count-v1") -> None:
        self.embedding_version = version
        self.calls = 0
        self._mock = MockEmbeddingProvider()

    def embed(self, texts: list[str]) -> list[list[float]]:
        self.calls += 1
        return self._mock.embed(texts)


def test_corpus_embeddings_are_persisted_and_reused() -> None:
    store = InMemoryDocumentStore()
    embedding_repo = EmbeddingRepository(store)
    emb = _CountingEmbeddings()
    service = _service(
        news=[_news(1, "ai chip story one"), _news(2, "oil prices slide")],
        analyses=[],
        embeddings=emb,
        embedding_repo=embedding_repo,
    )

    assert service.retrieve("NVDA", ["ai chip"]) == ["ai chip story one"]
    # First call: one batch embed for the 2 corpus docs + one embed for the query.
    assert emb.calls == 2
    assert len(embedding_repo.list()) == 2

    service.retrieve("NVDA", ["ai chip"])
    # Second call reuses the cached vectors: only the query is embedded.
    assert emb.calls == 3
    assert len(embedding_repo.list()) == 2  # no new records persisted


def test_reembeds_when_embedding_version_changes() -> None:
    store = InMemoryDocumentStore()
    embedding_repo = EmbeddingRepository(store)
    news = [_news(1, "ai chip story one")]

    v1 = _CountingEmbeddings(version="v1")
    _service(news=news, analyses=[], embeddings=v1, embedding_repo=embedding_repo).retrieve(
        "NVDA", ["ai chip"]
    )
    assert embedding_repo.list()[0].embedding_version == "v1"

    v2 = _CountingEmbeddings(version="v2")
    _service(news=news, analyses=[], embeddings=v2, embedding_repo=embedding_repo).retrieve(
        "NVDA", ["ai chip"]
    )
    # The stale vector is re-embedded and overwritten in place under the new version.
    assert {record.embedding_version for record in embedding_repo.list()} == {"v2"}
