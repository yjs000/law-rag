from datetime import date

import pytest
from llama_index.core.schema import TextNode
from llama_index.core.vector_stores.types import (
    FilterOperator,
    VectorStoreQuery,
    VectorStoreQueryResult,
)

from law_rag_llamaindex.retriever import search


class _FakeEmbedder:
    def __init__(self) -> None:
        self.queries: list[str] = []

    def get_query_embedding(self, query: str) -> list[float]:
        self.queries.append(query)
        return [0.25, 0.75]


class _FakeVectorStore:
    def __init__(self, nodes: list[TextNode], similarities: list[float]) -> None:
        self._result = VectorStoreQueryResult(nodes=nodes, similarities=similarities)
        self.queries: list[VectorStoreQuery] = []

    async def aquery(self, query: VectorStoreQuery) -> VectorStoreQueryResult:
        self.queries.append(query)
        return self._result


def _node(
    *,
    provision_id: str,
    document_id: str = "00000000-0000-0000-0000-000000000001",
    document_title: str = "전기사업법",
    effective_from: str = "2026-01-01",
    effective_to: str | None = None,
    path: str = "제1조",
    heading: str | None = "목적",
    content: str = "전기사업에 관한 기본 사항을 정한다.",
    law_type_code: str | None = "01",
) -> TextNode:
    return TextNode(
        id_=provision_id,
        text=content,
        metadata={
            "provision_id": provision_id,
            "document_id": document_id,
            "document_title": document_title,
            "source_kind": "law",
            "law_type_code": law_type_code,
            "version_label": "MST 20260101",
            "effective_from": effective_from,
            "effective_to": effective_to,
            "path": path,
            "heading": heading,
            "content": content,
            "source_url": "https://law.example.test/electricity",
        },
    )


@pytest.mark.asyncio
async def test_search_excludes_provision_starting_after_requested_date() -> None:
    future = _node(
        provision_id="10000000-0000-0000-0000-000000000001",
        effective_from="2026-02-01",
    )
    vector_store = _FakeVectorStore([future], [0.91])

    hits = await search(
        vector_store,
        _FakeEmbedder(),
        "전기사업",
        date(2026, 1, 31),
        5,
    )

    assert hits == []
    assert len(vector_store.queries) == 1
    query = vector_store.queries[0]
    assert query.filters is not None
    assert len(query.filters.filters) == 1
    filter_ = query.filters.filters[0]
    assert filter_.key == "effective_from"
    assert filter_.value == "2026-01-31"
    assert filter_.operator is FilterOperator.LTE


@pytest.mark.asyncio
async def test_search_excludes_provision_closed_on_requested_date() -> None:
    closed = _node(
        provision_id="10000000-0000-0000-0000-000000000002",
        effective_to="2026-01-31",
    )
    vector_store = _FakeVectorStore([closed], [0.91])

    hits = await search(
        vector_store,
        _FakeEmbedder(),
        "전기사업",
        date(2026, 1, 31),
        5,
    )

    assert hits == []


@pytest.mark.asyncio
async def test_search_maps_current_provision_metadata_and_score() -> None:
    current = _node(provision_id="10000000-0000-0000-0000-000000000003")
    vector_store = _FakeVectorStore([current], [0.87])

    hits = await search(
        vector_store,
        _FakeEmbedder(),
        "전기사업",
        date(2026, 2, 1),
        5,
    )

    assert len(hits) == 1
    hit = hits[0]
    assert str(hit.provision_id) == "10000000-0000-0000-0000-000000000003"
    assert str(hit.document_id) == "00000000-0000-0000-0000-000000000001"
    assert hit.document_title == "전기사업법"
    assert hit.source_kind == "law"
    assert hit.law_type_code == "01"
    assert hit.version_label == "MST 20260101"
    assert hit.effective_from == date(2026, 1, 1)
    assert hit.effective_to is None
    assert hit.path == "제1조"
    assert hit.heading == "목적"
    assert hit.content == "전기사업에 관한 기본 사항을 정한다."
    assert hit.source_url == "https://law.example.test/electricity"
    assert hit.score == 0.87


@pytest.mark.asyncio
async def test_search_applies_limit_after_temporal_post_filtering() -> None:
    closed = _node(
        provision_id="10000000-0000-0000-0000-000000000004",
        effective_to="2026-01-01",
    )
    first_current = _node(provision_id="10000000-0000-0000-0000-000000000005")
    second_current = _node(
        provision_id="10000000-0000-0000-0000-000000000006",
        path="제2조",
    )
    vector_store = _FakeVectorStore(
        [closed, first_current, second_current],
        [0.99, 0.98, 0.97],
    )

    hits = await search(
        vector_store,
        _FakeEmbedder(),
        "전기사업",
        date(2026, 2, 1),
        2,
    )

    assert [str(hit.provision_id) for hit in hits] == [
        "10000000-0000-0000-0000-000000000005",
        "10000000-0000-0000-0000-000000000006",
    ]
    assert vector_store.queries[0].similarity_top_k == 8
