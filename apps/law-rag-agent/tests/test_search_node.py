from datetime import date

import pytest
from law_rag_core.domain.schemas import SearchHit

from law_rag_agent.nodes.search import search_node


@pytest.mark.asyncio
async def test_search_node_calls_retriever_search_and_returns_hit_dicts(monkeypatch):
    hit = SearchHit(
        provision_id="11111111-1111-1111-1111-111111111111",
        document_id="22222222-2222-2222-2222-222222222222",
        document_title="에너지법",
        source_kind="law",
        version_label="MST 1",
        effective_from=date(2024, 1, 1),
        effective_to=None,
        path="제1조",
        heading=None,
        content="본문",
        source_url="https://example.test",
        score=0.9,
        law_type_code="A0002",
    )

    captured = {}

    async def fake_search(vector_store, embedder, query, as_of_date, limit):
        captured["args"] = (vector_store, embedder, query, as_of_date, limit)
        return [hit]

    monkeypatch.setattr("law_rag_agent.nodes.search.retriever_search", fake_search)

    vector_store = object()
    embedder = object()
    state = {"question": "태양광 정의", "as_of_date": "2026-08-19"}

    update = await search_node(state, vector_store, embedder, limit=5)

    assert update == {"search_hits": [hit.model_dump(mode="json")]}
    assert captured["args"][0] is vector_store
    assert captured["args"][1] is embedder
    assert captured["args"][2] == "태양광 정의"
    assert captured["args"][3] == date(2026, 8, 19)
    assert captured["args"][4] == 5
