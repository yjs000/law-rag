"""Backward-compatible imports for the v2 query adapter."""

from law_rag_llamaindex.query.retriever import search, search_index

__all__ = ["search", "search_index"]
