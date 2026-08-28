"""v2 LlamaIndex 검색과 v1 저장소 위임을 결합한다."""

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
from law_rag_llamaindex.retriever import search_index as llamaindex_search_index

from app.domain.search_queries import SearchTrace


class LlamaIndexLegalRepository:
    """v2 검색기는 사용하고 나머지 저장소 계약은 v1에 위임한다."""

    def __init__(self, delegate: LegalRepository, vector_store, embedder) -> None:
        """v1 위임 저장소와 v2 검색 의존성을 연결한다."""
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
        """v2 검색 결과만 반환하고 검색 추적 정보는 숨긴다."""
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
        """v2 dense 검색 결과와 관측용 검색 추적 정보를 반환한다.

        호출자가 제공한 v1 임베딩 인자는 사용하지 않는다. v2 검색기가 자체 query embedding을
        생성해 검색 구현 경계를 유지한다.
        """
        started = perf_counter()
        vector_store = self._vector_store
        active = getattr(vector_store, "active", None)
        if active is not None:
            pinned = await active()
            hits = await llamaindex_search_index(pinned.index, query, as_of_date, limit)
        else:
            hits = await llamaindex_search(
                vector_store,
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
        """사용량 한도 소비를 v1 저장소에 위임한다."""
        return await self._delegate.consume_quota(subject_hash, day, kind, limit)

    async def upsert_document(self, document: LegalDocumentRecord) -> UUID:
        """문서 upsert를 v1 저장소에 위임한다."""
        return await self._delegate.upsert_document(document)

    async def upsert_embeddings(
        self,
        values: list[tuple[UUID, str, list[float]]],
        profile_key: str,
        dimensions: int,
    ) -> None:
        """임베딩 upsert를 v1 저장소에 위임한다."""
        await self._delegate.upsert_embeddings(values, profile_key, dimensions)

    async def provision(self, provision_id: UUID, as_of_date: date) -> SearchHit | None:
        """단일 조문 조회를 v1 저장소에 위임한다."""
        return await self._delegate.provision(provision_id, as_of_date)

    async def corpus_items(self) -> list[CorpusItemStatus]:
        """Corpus 항목 상태 조회를 v1 저장소에 위임한다."""
        return await self._delegate.corpus_items()

    async def corpus_search_status(self) -> CorpusSearchStatus:
        """Corpus 검색 상태 조회를 v1 저장소에 위임한다."""
        return await self._delegate.corpus_search_status()

    async def corpus_temporal_state(self, supported_through: date) -> CorpusTemporalState:
        """Corpus 기준일 범위 상태 조회를 v1 저장소에 위임한다."""
        return await self._delegate.corpus_temporal_state(supported_through)

    async def last_sync(self) -> datetime | None:
        """마지막 corpus 동기화 시각 조회를 v1 저장소에 위임한다."""
        return await self._delegate.last_sync()
