"""RAG retrieval service (AI_PIPELINE.md section 5).

Builds the ``retrieved_context`` injected into the GPT-5 prompt: for the current
event it finds the most semantically similar prior documents (past news
headlines and past AI reasoning summaries) so the model reasons with historical
precedent. Orchestration only — embeddings come from the ``EmbeddingProvider``
seam and ranking from the pure ``retrieval_engine``; the corpus and the cached
vectors come from repositories.

Corpus embeddings are persisted to ``ai_embeddings/`` keyed by source document
(AI_PIPELINE.md sections 5.1 / 8), so each request only embeds the query and
any not-yet-indexed documents instead of re-embedding the whole corpus. Cached
vectors are re-embedded when the ``embedding_version`` changes (section 13).

Retrieval is best-effort enrichment: any failure (e.g. the embedding API) is
logged and yields an empty context. It never raises into the AI path, which is
itself enrichment-only and never an execution authority (.cursor/rules.md 3.3).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from app.engines.retrieval_engine import RetrievalDocument, rank_by_similarity
from app.models.entities import EmbeddingRecord
from app.models.enums import LogLevel
from app.repositories.repositories import (
    AiAnalysisRepository,
    EmbeddingRepository,
    NewsRepository,
)
from app.services.embedding_provider import EmbeddingProvider
from app.services.log_writer import LogWriter
from app.utils.ids import embedding_id


@dataclass(frozen=True)
class _Candidate:
    source_id: str
    source_type: str
    ticker: str
    text: str


@dataclass(frozen=True)
class RetrievalResult:
    """RAG output: prompt snippets plus their source document ids for provenance."""

    context: list[str]
    source_ids: list[str]


class RetrievalService:
    def __init__(
        self,
        news_repo: NewsRepository,
        ai_repo: AiAnalysisRepository,
        embedding_repo: EmbeddingRepository,
        embedding_provider: EmbeddingProvider,
        log_writer: LogWriter,
        top_k: int = 5,
    ) -> None:
        self._news = news_repo
        self._ai = ai_repo
        self._embedding_repo = embedding_repo
        self._embeddings = embedding_provider
        self._log = log_writer
        self._top_k = top_k

    @property
    def embedding_version(self) -> str:
        return self._embeddings.embedding_version

    def retrieve(self, ticker: str, query_texts: list[str]) -> list[str]:
        return self.retrieve_with_provenance(ticker, query_texts).context

    def retrieve_with_provenance(self, ticker: str, query_texts: list[str]) -> RetrievalResult:
        query = " ".join(text for text in query_texts if text).strip()
        if not query:
            return RetrievalResult(context=[], source_ids=[])

        candidates = self._candidates(exclude=set(query_texts))
        if not candidates:
            return RetrievalResult(context=[], source_ids=[])

        try:
            vectors_by_source = self._index(candidates)
            query_vector = self._embeddings.embed([query])[0]
        except RuntimeError as exc:
            self._log.log(
                event="retrieval_failed",
                message=f"{ticker}: embedding failed, no retrieved context: {exc}",
                level=LogLevel.WARNING,
                metadata={"ticker": ticker},
            )
            return RetrievalResult(context=[], source_ids=[])

        text_to_source = {candidate.text: candidate.source_id for candidate in candidates}
        documents = [
            RetrievalDocument(text=candidate.text, embedding=vectors_by_source[candidate.source_id])
            for candidate in candidates
        ]
        ranked = rank_by_similarity(query_vector, documents, self._top_k, min_score=0.0)
        context: list[str] = []
        source_ids: list[str] = []
        for doc in ranked:
            if doc.score <= 0.0:
                continue
            context.append(doc.text)
            source_id = text_to_source.get(doc.text)
            if source_id is not None:
                source_ids.append(source_id)

        if context:
            self._log.log(
                event="retrieval_completed",
                message=f"{ticker}: retrieved {len(context)} similar documents",
                metadata={"ticker": ticker, "count": len(context)},
            )
        return RetrievalResult(context=context, source_ids=source_ids)

    def _index(self, candidates: list[_Candidate]) -> dict[str, list[float]]:
        """Return source_id -> embedding, reusing cached vectors and persisting new ones."""
        version = self._embeddings.embedding_version
        vectors: dict[str, list[float]] = {}
        missing: list[_Candidate] = []
        for candidate in candidates:
            record = self._embedding_repo.get(embedding_id(candidate.source_id))
            if record is not None and record.embedding_version == version:
                vectors[candidate.source_id] = record.vector
            else:
                missing.append(candidate)

        if missing:
            now = datetime.now(UTC)
            new_vectors = self._embeddings.embed([candidate.text for candidate in missing])
            for candidate, vector in zip(missing, new_vectors, strict=True):
                self._embedding_repo.save(
                    EmbeddingRecord(
                        id=embedding_id(candidate.source_id),
                        source_id=candidate.source_id,
                        source_type=candidate.source_type,
                        ticker=candidate.ticker,
                        text=candidate.text,
                        vector=vector,
                        embedding_version=version,
                        created_at=now,
                    )
                )
                vectors[candidate.source_id] = vector
        return vectors

    def _candidates(self, exclude: set[str]) -> list[_Candidate]:
        """Deduplicated corpus of prior AI summaries + news headlines.

        Past reasoning summaries come first (the learning-loop precedent), then
        historical headlines. The current event's own texts are excluded so
        retrieval never trivially returns the query back to itself.
        """
        seen: set[str] = set()
        candidates: list[_Candidate] = []
        for analysis in self._ai.list():
            self._add(
                _Candidate(analysis.id, "insight", analysis.ticker, analysis.summary),
                exclude,
                seen,
                candidates,
            )
        for item in self._news.list():
            self._add(
                _Candidate(item.id, "news", item.ticker, item.headline),
                exclude,
                seen,
                candidates,
            )
        return candidates

    @staticmethod
    def _add(
        candidate: _Candidate,
        exclude: set[str],
        seen: set[str],
        candidates: list[_Candidate],
    ) -> None:
        text = candidate.text
        if text and text not in exclude and text not in seen:
            seen.add(text)
            candidates.append(candidate)
