"""Version 2 search HTTP transport with fail-closed readiness presentation."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from app.api.dependencies import main_module
from app.domain.schemas import SearchHit, SearchRequest
from app.domain.source_urls import is_allowed_source_url

router = APIRouter()


def _not_ready_error() -> HTTPException:
    return HTTPException(
        status_code=503,
        detail={"code": "v2_search_not_ready", "message": "v2 검색을 아직 사용할 수 없습니다."},
    )


@router.post("/v2/search", response_model=list[SearchHit])
async def search_v2(payload: SearchRequest, request: Request) -> list[SearchHit]:
    """Search only a verified active v2 generation or return a stable 503."""

    main = main_module()
    resources = main._llamaindex_resources()
    if resources is None:
        raise _not_ready_error()
    vector_store, embedder, _ = resources
    if vector_store is None or embedder is None or not await main._v2_ready():
        raise _not_ready_error()
    active = getattr(vector_store, "active", None)
    if active is not None:
        try:
            pinned = await active()
        except Exception:
            raise _not_ready_error() from None
        hits = await main.llamaindex_search_index(
            pinned.index, payload.query, payload.as_of_date, payload.limit
        )
    else:
        hits = await main.llamaindex_search(
            vector_store,
            embedder,
            payload.query,
            payload.as_of_date,
            payload.limit,
        )
    if payload.source_kinds:
        hits = [hit for hit in hits if hit.source_kind in payload.source_kinds]
    return [hit for hit in hits if is_allowed_source_url(hit.source_url)]
