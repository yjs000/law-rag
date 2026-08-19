from collections.abc import Callable
from datetime import date

from law_rag_llamaindex.retriever import search as retriever_search

from law_rag_agent.state import AgentState


async def search_node(state: AgentState, vector_store, embedder, limit: int) -> dict:
    hits = await retriever_search(
        vector_store,
        embedder,
        state["question"],
        date.fromisoformat(state["as_of_date"]),
        limit,
    )
    return {"search_hits": [hit.model_dump(mode="json") for hit in hits]}


def build_search_node(vector_store, embedder, limit: int = 10) -> Callable[[AgentState], dict]:
    async def _node(state: AgentState) -> dict:
        return await search_node(state, vector_store, embedder, limit)

    return _node
