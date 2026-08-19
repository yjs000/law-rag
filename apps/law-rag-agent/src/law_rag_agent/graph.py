from collections.abc import Callable
from typing import Any

from langgraph.graph import END, StateGraph

from law_rag_agent.state import AgentState

_BLOCKED_MESSAGES = {
    "clarification_required": "답하려면 정보가 더 필요합니다: {reason}",
    "realtime_required": "이 질문은 실시간 정보가 필요해 현재 법령 검색만으로는 답할 수 없습니다.",
    "external_document_required": (
        "이 질문은 법령 외 문서가 필요해 현재 법령 검색만으로는 답할 수 없습니다."
    ),
}


def _blocked_node(state: AgentState) -> dict[str, Any]:
    route = state["route"]
    message = _BLOCKED_MESSAGES.get(route, "이 질문은 법령 검색으로 답할 수 없습니다.")
    return {"final_answer": message.format(reason=route), "final_citations": []}


def _route_branch(state: AgentState) -> str:
    return "search" if state["route"] == "legal_search" else "blocked"


def build_graph(
    route_node: Callable[..., Any],
    search_node: Callable[..., Any],
    generate_node: Callable[..., Any],
    validate_node: Callable[..., Any],
    checkpointer: Any = None,
) -> Any:
    graph = StateGraph(AgentState)
    graph.add_node("route", route_node)
    graph.add_node("search", search_node)
    graph.add_node("generate", generate_node)
    graph.add_node("validate", validate_node)
    graph.add_node("blocked", _blocked_node)

    graph.set_entry_point("route")
    graph.add_conditional_edges("route", _route_branch, {"search": "search", "blocked": "blocked"})
    graph.add_edge("search", "generate")
    graph.add_edge("generate", "validate")
    graph.add_edge("validate", END)
    graph.add_edge("blocked", END)

    return graph.compile(checkpointer=checkpointer)
