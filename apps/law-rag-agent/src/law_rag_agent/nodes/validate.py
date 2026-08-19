from law_rag_agent.state import AgentState

_UNGROUNDED_FALLBACK = (
    "이 주장은 인용 근거 없이 만들어져 표시하지 않습니다. 아래 검색된 원문을 직접 확인하세요."
)


def validate_node(state: AgentState) -> dict:
    if state["draft_action"] == "unanswerable":
        return {"final_answer": state["draft_answer"], "final_citations": []}

    if not state["draft_citations"]:
        return {"final_answer": _UNGROUNDED_FALLBACK, "final_citations": []}

    return {
        "final_answer": state["draft_answer"],
        "final_citations": state["draft_citations"],
    }
