from datetime import date
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest
from law_rag_core.domain.catalog import SourceKind
from law_rag_core.domain.entities import LegalDocumentRecord

from app.adapters.llamaindex_repository import LlamaIndexLegalRepository
from app.domain.search_queries import SearchTrace


@pytest.mark.asyncio
async def test_search_with_trace_uses_v2_retriever_and_returns_dense_trace(monkeypatch) -> None:
    delegate = MagicMock()
    delegate.search = AsyncMock(side_effect=AssertionError("v1 search must not be called"))
    delegate.search_with_trace = AsyncMock(
        side_effect=AssertionError("v1 search_with_trace must not be called")
    )
    vector_store = object()
    embedder = object()
    fake_hits = [MagicMock(name="hit-1"), MagicMock(name="hit-2")]
    retriever_args: dict[str, object] = {}

    async def fake_search(store, emb, query, as_of_date, limit):
        retriever_args.update(
            store=store,
            embedder=emb,
            query=query,
            as_of_date=as_of_date,
            limit=limit,
        )
        return fake_hits

    monkeypatch.setattr(
        "app.adapters.llamaindex_repository.llamaindex_search", fake_search
    )
    perf_values = iter((10.0, 10.125))
    monkeypatch.setattr(
        "app.adapters.llamaindex_repository.perf_counter", lambda: next(perf_values)
    )

    repository = LlamaIndexLegalRepository(delegate, vector_store, embedder)
    requested_date = date(2026, 1, 1)
    hits, trace = await repository.search_with_trace(
        "질문",
        requested_date,
        5,
        query_embedding=[0.1, 0.2],
        embedding_profile_key="legacy-profile",
    )

    assert hits == fake_hits
    assert retriever_args == {
        "store": vector_store,
        "embedder": embedder,
        "query": "질문",
        "as_of_date": requested_date,
        "limit": 5,
    }
    assert trace == SearchTrace(
        strategy="v2_llamaindex_dense",
        normalized_query="질문",
        terms=(),
        executed_query=None,
        relaxed=False,
        reference_title=None,
        reference_path=None,
        candidate_count=2,
        total_duration_ms=125.0,
    )
    delegate.search.assert_not_awaited()
    delegate.search_with_trace.assert_not_awaited()


@pytest.mark.asyncio
async def test_search_returns_hits_from_this_adapter_search_with_trace() -> None:
    delegate = MagicMock()
    repository = LlamaIndexLegalRepository(delegate, object(), object())
    fake_hits = [MagicMock(name="hit")]
    repository.search_with_trace = AsyncMock(
        return_value=(fake_hits, MagicMock(name="trace"))
    )

    requested_date = date(2026, 1, 1)
    hits = await repository.search(
        "질문",
        requested_date,
        5,
        query_embedding=[0.1, 0.2],
        embedding_profile_key="legacy-profile",
    )

    assert hits == fake_hits
    repository.search_with_trace.assert_awaited_once_with("질문", requested_date, 5)
    delegate.search.assert_not_called()


@pytest.mark.asyncio
async def test_search_with_trace_pins_the_active_generation_store_for_one_request(
    monkeypatch,
) -> None:
    delegate = MagicMock()
    active_store = object()
    observed: dict[str, object] = {}

    class ActiveProvider:
        async def active(self):
            return type("Pinned", (), {"store": active_store})()

    async def fake_search(store, emb, query, as_of_date, limit):
        observed["store"] = store
        return []

    monkeypatch.setattr("app.adapters.llamaindex_repository.llamaindex_search", fake_search)

    repository = LlamaIndexLegalRepository(delegate, ActiveProvider(), object())
    await repository.search_with_trace("질문", date(2026, 1, 1), 5)

    assert observed["store"] is active_store


@pytest.mark.asyncio
async def test_non_search_methods_forward_concrete_arguments_to_delegate() -> None:
    delegate = MagicMock()
    delegate.consume_quota = AsyncMock(return_value=True)
    delegate.upsert_document = AsyncMock(return_value=UUID("00000000-0000-0000-0000-000000000001"))
    delegate.upsert_embeddings = AsyncMock(return_value=None)
    delegate.provision = AsyncMock(return_value=None)
    delegate.corpus_items = AsyncMock(return_value=[])
    delegate.corpus_search_status = AsyncMock(return_value="ready")
    delegate.corpus_temporal_state = AsyncMock(return_value="state")
    delegate.last_sync = AsyncMock(return_value=None)

    repository = LlamaIndexLegalRepository(delegate, object(), object())
    requested_date = date(2026, 1, 1)
    document = LegalDocumentRecord(
        source_id="source-id",
        mst="MST-20260101",
        title="전기사업법",
        source_kind=SourceKind.LAW,
        promulgation_number=None,
        promulgated_on=None,
        effective_from=requested_date,
        ministry=None,
        source_url="https://law.example.test/source",
        raw_format="JSON",
        raw_sha256="a" * 64,
    )
    embeddings = [(uuid4(), "sha256", [0.1, 0.2])]
    provision_id = uuid4()

    assert await repository.consume_quota("subject-hash", requested_date, "search", 100) is True
    assert await repository.upsert_document(document) == UUID(
        "00000000-0000-0000-0000-000000000001"
    )
    assert await repository.upsert_embeddings(embeddings, "profile", 2) is None
    assert await repository.provision(provision_id, requested_date) is None
    assert await repository.corpus_items() == []
    assert await repository.corpus_search_status() == "ready"
    assert await repository.corpus_temporal_state(requested_date) == "state"
    assert await repository.last_sync() is None

    delegate.consume_quota.assert_awaited_once_with("subject-hash", requested_date, "search", 100)
    delegate.upsert_document.assert_awaited_once_with(document)
    delegate.upsert_embeddings.assert_awaited_once_with(embeddings, "profile", 2)
    delegate.provision.assert_awaited_once_with(provision_id, requested_date)
    delegate.corpus_items.assert_awaited_once_with()
    delegate.corpus_search_status.assert_awaited_once_with()
    delegate.corpus_temporal_state.assert_awaited_once_with(requested_date)
    delegate.last_sync.assert_awaited_once_with()
