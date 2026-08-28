"""Temporal retrieval adapters for the v2 vector index."""

from collections.abc import Iterable
from datetime import date
from typing import Any

from law_rag_core.domain.schemas import SearchHit
from llama_index.core.vector_stores.types import (
    FilterOperator,
    MetadataFilter,
    MetadataFilters,
    VectorStoreQuery,
)

_OVER_FETCH_CAP = 100


async def search(
    vector_store: Any,
    embedder: Any,
    query: str,
    as_of_date: date,
    limit: int,
) -> list[SearchHit]:
    """Search with one embedding and return provisions valid on the requested date.

    Candidates are over-fetched before the temporal post-filter so the vector-store metadata
    filter cannot hide the ``effective_to`` boundary that it cannot express by itself.
    """

    query_embedding = embedder.get_query_embedding(query)
    result = await vector_store.aquery(
        VectorStoreQuery(
            query_embedding=query_embedding,
            similarity_top_k=_over_fetch_limit(limit),
            filters=_as_of_filter(as_of_date),
        )
    )
    return _filter_hits(
        zip(result.nodes or [], result.similarities or [], strict=True), as_of_date, limit
    )


async def search_index(
    index: Any, query: str, as_of_date: date, limit: int
) -> list[SearchHit]:
    """Search a pinned ``VectorStoreIndex`` without a second API-owned embedding call."""

    nodes = await index.as_retriever(
        similarity_top_k=_over_fetch_limit(limit),
        filters=_as_of_filter(as_of_date),
    ).aretrieve(query)
    return _filter_hits(((node.node, node.score) for node in nodes), as_of_date, limit)


def _over_fetch_limit(limit: int) -> int:
    return min(limit * 4, _OVER_FETCH_CAP)


def _as_of_filter(as_of_date: date) -> MetadataFilters:
    return MetadataFilters(
        filters=[
            MetadataFilter(
                key="effective_from",
                value=as_of_date.isoformat(),
                operator=FilterOperator.LTE,
            )
        ]
    )


def _filter_hits(
    nodes: Iterable[tuple[Any, float]], as_of_date: date, limit: int
) -> list[SearchHit]:
    """Map vector results and enforce temporal validity independent of store filters."""

    hits: list[SearchHit] = []
    for node, similarity in nodes:
        hit = _to_search_hit(node, similarity)
        if hit is None or not _is_current_on(hit, as_of_date):
            continue
        hits.append(hit)
        if len(hits) >= limit:
            break
    return hits


def _to_search_hit(node: Any, similarity: float) -> SearchHit | None:
    metadata = node.metadata
    try:
        return SearchHit(
            provision_id=metadata["provision_id"],
            document_id=metadata["document_id"],
            document_title=metadata["document_title"],
            source_kind=metadata["source_kind"],
            version_label=metadata["version_label"],
            effective_from=metadata["effective_from"],
            effective_to=metadata["effective_to"],
            path=metadata["path"],
            heading=metadata["heading"],
            content=metadata["content"],
            source_url=metadata["source_url"],
            score=similarity,
            law_type_code=metadata["law_type_code"],
        )
    except (KeyError, TypeError, ValueError):
        return None


def _is_current_on(hit: SearchHit, as_of_date: date) -> bool:
    if hit.effective_from is None or hit.effective_from > as_of_date:
        return False
    return hit.effective_to is None or hit.effective_to > as_of_date
