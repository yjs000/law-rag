from datetime import date, datetime
from time import perf_counter
from uuid import UUID

from law_rag_core.domain.entities import LegalDocumentRecord
from law_rag_core.domain.schemas import (
    CorpusItemStatus,
    CorpusSearchStatus,
    CorpusTemporalState,
    SearchHit,
)
from law_rag_core.ports.repository import LegalRepository
from law_rag_llamaindex.retriever import search as llamaindex_search

from app.domain.search_queries import SearchTrace


class LlamaIndexLegalRepository:
    """Use the v2 retriever for search and delegate all other operations to v1."""

    def __init__(self, delegate: LegalRepository, vector_store, embedder) -> None:
        self._delegate = delegate
        self._vector_store = vector_store
        self._embedder = embedder

    async def search(
        self,
        query: str,
        as_of_date: date,
        limit: int,
        query_embedding: list[float] | None = None,
        embedding_profile_key: str | None = None,
    ) -> list[SearchHit]:
        hits, _ = await self.search_with_trace(query, as_of_date, limit)
        return hits

    async def search_with_trace(
        self,
        query: str,
        as_of_date: date,
        limit: int,
        query_embedding: list[float] | None = None,
        embedding_profile_key: str | None = None,
    ) -> tuple[list[SearchHit], SearchTrace]:
        started = perf_counter()
        hits = await llamaindex_search(
            self._vector_store,
            self._embedder,
            query,
            as_of_date,
            limit,
        )
        trace = SearchTrace(
            strategy="v2_llamaindex_dense",
            normalized_query=query,
            terms=(),
            executed_query=None,
            relaxed=False,
            reference_title=None,
            reference_path=None,
            candidate_count=len(hits),
            total_duration_ms=(perf_counter() - started) * 1000,
        )
        return hits, trace

    async def consume_quota(self, subject_hash: str, day: date, kind: str, limit: int) -> bool:
        return await self._delegate.consume_quota(subject_hash, day, kind, limit)

    async def upsert_document(self, document: LegalDocumentRecord) -> UUID:
        return await self._delegate.upsert_document(document)

    async def upsert_embeddings(
        self,
        values: list[tuple[UUID, str, list[float]]],
        profile_key: str,
        dimensions: int,
    ) -> None:
        await self._delegate.upsert_embeddings(values, profile_key, dimensions)

    async def provision(self, provision_id: UUID, as_of_date: date) -> SearchHit | None:
        return await self._delegate.provision(provision_id, as_of_date)

    async def corpus_items(self) -> list[CorpusItemStatus]:
        return await self._delegate.corpus_items()

    async def corpus_search_status(self) -> CorpusSearchStatus:
        return await self._delegate.corpus_search_status()

    async def corpus_temporal_state(self, supported_through: date) -> CorpusTemporalState:
        return await self._delegate.corpus_temporal_state(supported_through)

    async def last_sync(self) -> datetime | None:
        return await self._delegate.last_sync()
