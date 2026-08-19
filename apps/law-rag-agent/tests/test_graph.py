import pytest
from langgraph.checkpoint.memory import MemorySaver

from law_rag_agent.graph import build_graph
from law_rag_agent.nodes.validate import validate_node


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


def _recording_node(calls, name, result):
    async def node(state):
        calls.append(name)
        return result

    return node


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
    calls = []
    graph = build_graph(
        _recording_node(calls, "route", {"route": "legal_search"}),
        _recording_node(calls, "search", await fake_search(None)),
        _recording_node(
            calls,
            "generate",
            {"draft_answer": "답변", "draft_citations": [{"id": "C1"}]},
        ),
        _recording_node(
            calls,
            "validate",
            {"final_answer": "답변", "final_citations": [{"id": "C1"}]},
        ),
    )

    result = await graph.ainvoke(_initial_state())

    assert calls == ["route", "search", "generate", "validate"]
    assert result["final_answer"] == "답변"
    assert result["final_citations"] == [{"id": "C1"}]


@pytest.mark.asyncio
async def test_graph_skips_search_and_generate_when_route_is_blocked():
    calls = []
    graph = build_graph(
        _recording_node(calls, "route", {"route": "clarification_required"}),
        _recording_node(calls, "search", {"search_hits": [{"id": "unexpected"}]}),
        _recording_node(calls, "generate", {"draft_answer": "unexpected"}),
        _recording_node(
            calls,
            "validate",
            {"final_answer": "unexpected", "final_citations": [{"id": "unexpected"}]},
        ),
    )

    result = await graph.ainvoke(_initial_state())

    assert calls == ["route"]
    assert result["search_hits"] == []
    assert result["final_answer"] == "답하려면 정보가 더 필요합니다: clarification_required"
    assert result["final_citations"] == []


@pytest.mark.asyncio
async def test_graph_uses_validate_fallback_for_ungrounded_draft():
    graph = build_graph(
        fake_route_legal_search,
        fake_search,
        lambda state: {
            "draft_answer": "근거 없는 법률 주장",
            "draft_citations": [{"id": "C99"}],
            "draft_action": "fully_answerable",
        },
        validate_node,
    )

    result = await graph.ainvoke(_initial_state())

    assert result["final_answer"] == (
        "검색된 근거가 부족하여 답변을 확정할 수 없습니다. 제공된 검색 결과를 직접 확인하세요."
    )
    assert result["final_citations"] == [
        {
            "id": "C1",
            "path": "제1조",
            "document_title": "법",
            "source_url": "https://x",
        }
    ]


@pytest.mark.asyncio
async def test_graph_restores_state_from_memory_checkpointer_for_same_thread():
    checkpointer = MemorySaver()

    graph = build_graph(
        fake_route_legal_search, fake_search, fake_generate, fake_validate, checkpointer
    )
    config = {"configurable": {"thread_id": "thread-restore"}}

    await graph.ainvoke(_initial_state(), config)
    snapshot = await graph.aget_state(config)

    assert snapshot.values["thread_id"] == "t1"
    assert snapshot.values["final_answer"] == "답변"
    assert snapshot.values["final_citations"] == [{"id": "C1"}]
