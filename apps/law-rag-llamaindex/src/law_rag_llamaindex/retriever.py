"""v2 벡터 검색에서 기준일에 유효한 법령 조문만 반환한다."""

from datetime import date

from law_rag_core.domain.schemas import SearchHit
from llama_index.core.vector_stores.types import (
    FilterOperator,
    MetadataFilter,
    MetadataFilters,
    VectorStoreQuery,
)

_OVER_FETCH_CAP = 100


async def search(
    vector_store, embedder, query: str, as_of_date: date, limit: int
) -> list[SearchHit]:
    """질문 임베딩으로 검색하고 요청 기준일에 유효한 결과만 반환한다.

    후보를 넉넉히 가져온 뒤 시행일 범위로 다시 걸러, 벡터 저장소의 metadata filter만으로는
    표현할 수 없는 종료일 경계를 보장한다.
    """
    query_embedding = embedder.get_query_embedding(query)
    over_fetch = min(limit * 4, _OVER_FETCH_CAP)
    filters = MetadataFilters(
        filters=[
            MetadataFilter(
                key="effective_from",
                value=as_of_date.isoformat(),
                operator=FilterOperator.LTE,
            )
        ]
    )
    result = await vector_store.aquery(
        VectorStoreQuery(
            query_embedding=query_embedding,
            similarity_top_k=over_fetch,
            filters=filters,
        )
    )

    hits: list[SearchHit] = []
    for node, similarity in zip(result.nodes or [], result.similarities or [], strict=True):
        metadata = node.metadata
        hit = SearchHit(
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
        if hit.effective_from is None or hit.effective_from > as_of_date:
            continue
        if hit.effective_to is not None and hit.effective_to <= as_of_date:
            continue
        hits.append(hit)
        if len(hits) >= limit:
            break
    return hits
