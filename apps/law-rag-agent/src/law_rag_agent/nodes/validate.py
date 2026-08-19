from law_rag_agent.state import AgentState

_SAFE_FALLBACK = (
    "검색된 근거가 부족하여 답변을 확정할 수 없습니다. 제공된 검색 결과를 직접 확인하세요."
)
_PROVENANCE_FIELDS = ("path", "document_title", "source_url")


def _citations_from_search_hits(search_hits: list[dict]) -> list[dict]:
    citations = []
    for index, hit in enumerate(search_hits, start=1):
        citation = {"id": f"C{index}"}
        for field in _PROVENANCE_FIELDS:
            value = hit.get(field)
            if value is not None:
                citation[field] = value
        citations.append(citation)
    return citations


def _citation_matches_hit(citation: dict, hit: dict, index: int) -> bool:
    if citation.get("id") != f"C{index}":
        return False
    return all(
        field not in citation or citation[field] == hit.get(field) for field in _PROVENANCE_FIELDS
    )


def validate_node(state: AgentState) -> dict:
    search_hits = state.get("search_hits", [])
    fallback = {
        "final_answer": _SAFE_FALLBACK,
        "final_citations": _citations_from_search_hits(search_hits),
    }

    if state["draft_action"] == "unanswerable":
        return fallback

    draft_citations = state["draft_citations"]
    if not draft_citations or not all(
        isinstance(citation, dict)
        and any(
            _citation_matches_hit(citation, hit, index)
            for index, hit in enumerate(search_hits, start=1)
        )
        for citation in draft_citations
    ):
        return fallback

    return {
        "final_answer": state["draft_answer"],
        "final_citations": draft_citations,
    }
