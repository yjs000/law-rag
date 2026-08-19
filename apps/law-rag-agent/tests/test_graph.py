import pytest
from langgraph.checkpoint.memory import MemorySaver

from law_rag_agent.graph import build_graph


async def fake_route_legal_search(state):
    return {"route": "legal_search"}


async def fake_route_blocked(state):
    return {"route": "clarification_required"}


async def fake_search(state):
    return {
        "search_hits": [
            {
                "path": "제1조",
                "document_title": "법",
                "source_url": "https://x",
                "content": "본문",
            }
        ]
    }


async def fake_generate(state):
    return {
        "draft_answer": "답변",
        "draft_citations": [{"id": "C1"}],
        "draft_action": "fully_answerable",
    }


def fake_validate(state):
    return {
        "final_answer": state["draft_answer"],
        "final_citations": state["draft_citations"],
    }


def _initial_state():
    return {
        "thread_id": "t1",
        "turns": [],
        "question": "질문",
        "as_of_date": "2026-08-19",
        "route": None,
        "search_hits": [],
        "draft_answer": None,
        "draft_citations": [],
        "draft_action": None,
        "final_answer": None,
        "final_citations": [],
    }


@pytest.mark.asyncio
async def test_graph_runs_full_pipeline_when_route_is_legal_search():
    graph = build_graph(fake_route_legal_search, fake_search, fake_generate, fake_validate)

    result = await graph.ainvoke(_initial_state())

    assert result["final_answer"] == "답변"
    assert result["final_citations"] == [{"id": "C1"}]


@pytest.mark.asyncio
async def test_graph_skips_search_and_generate_when_route_is_blocked():
    graph = build_graph(fake_route_blocked, fake_search, fake_generate, fake_validate)

    result = await graph.ainvoke(_initial_state())

    assert result["search_hits"] == []
    assert "clarification_required" in result["final_answer"] or result["final_answer"]


def test_graph_uses_supplied_checkpointer():
    checkpointer = MemorySaver()

    graph = build_graph(
        fake_route_legal_search, fake_search, fake_generate, fake_validate, checkpointer
    )

    assert graph.checkpointer is checkpointer
