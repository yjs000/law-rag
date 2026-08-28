"""Active-generation query resources and temporal retrieval adapters."""

from law_rag_llamaindex.query.active_index import ActiveGenerationIndexProvider, ActiveIndex
from law_rag_llamaindex.query.retriever import search, search_index

__all__ = ["ActiveGenerationIndexProvider", "ActiveIndex", "search", "search_index"]
