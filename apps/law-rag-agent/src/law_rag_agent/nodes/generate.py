from collections.abc import Callable

from law_rag_agent.state import AgentState

_GENERATE_PROMPT = """다음 근거 조문만 사용해서 질문에 답하세요. 근거에 없는 내용은 답하지 마세요.

질문: {question}

근거:
{evidence}
"""


def _format_evidence(search_hits: list[dict]) -> str:
    lines = []
    for index, hit in enumerate(search_hits, start=1):
        lines.append(f"[C{index}] {hit['document_title']} {hit['path']}: {hit['content']}")
    return "\n".join(lines)


async def generate_node(state: AgentState, llm) -> dict:
    search_hits = state["search_hits"]
    prompt = _GENERATE_PROMPT.format(
        question=state["question"], evidence=_format_evidence(search_hits)
    )
    result = await llm.ainvoke([{"role": "user", "content": prompt}])

    id_to_index = {f"C{i}": i - 1 for i in range(1, len(search_hits) + 1)}
    citations = []
    for citation_id in result.citation_ids:
        index = id_to_index.get(citation_id)
        if index is None:
            continue
        hit = search_hits[index]
        citations.append(
            {
                "id": citation_id,
                "path": hit["path"],
                "document_title": hit["document_title"],
                "source_url": hit["source_url"],
            }
        )

    return {
        "draft_answer": result.answer,
        "draft_citations": citations,
        "draft_action": result.action,
    }


def build_generate_node(llm) -> Callable[[AgentState], dict]:
    async def _node(state: AgentState) -> dict:
        return await generate_node(state, llm)

    return _node
