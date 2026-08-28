"""Version 1 health, search and corpus HTTP transport."""

from __future__ import annotations

from datetime import date
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request

from app.adapters.postgres_repository import PostgresLegalRepository
from app.api.dependencies import main_module
from app.domain.errors import CorpusSearchUnavailableError
from app.domain.schemas import (
    CorpusStatus,
    DocumentChangesResponse,
    ProvisionResponse,
    SearchHit,
    SearchRequest,
)
from app.domain.source_urls import is_allowed_source_url

router = APIRouter()


@router.get("/health")
async def health() -> dict[str, str]:
    """Return the public service health response."""

    return {"status": "ok"}


@router.post("/v1/search", response_model=list[SearchHit])
async def search(payload: SearchRequest, request: Request) -> list[SearchHit]:
    """Return allowed legal-search results from the v1 repository."""

    main = main_module()
    await main._require_supported_as_of_date(payload.as_of_date, main.repository)
    await main._check_quota("search")
    try:
        hits = await main.repository.search(payload.query, payload.as_of_date, payload.limit, None)
    except CorpusSearchUnavailableError as exc:
        raise main._corpus_unready_http_error() from exc
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail="법령 검색을 일시적으로 사용할 수 없습니다.",
        ) from exc
    if payload.source_kinds:
        hits = [hit for hit in hits if hit.source_kind in payload.source_kinds]
    return [hit for hit in hits if is_allowed_source_url(hit.source_url)]


@router.get("/v1/provisions/{provision_id}", response_model=ProvisionResponse)
async def provision(provision_id: UUID, as_of_date: date | None = None) -> ProvisionResponse:
    """Return one provision valid at the requested supported date."""

    main = main_module()
    requested_date = as_of_date or main._current_korea_date()
    await main._require_supported_as_of_date(requested_date, main.repository)
    try:
        hit = await main.repository.provision(provision_id, requested_date)
    except CorpusSearchUnavailableError as exc:
        raise main._corpus_unready_http_error() from exc
    if hit is None or not is_allowed_source_url(hit.source_url):
        raise HTTPException(status_code=404, detail="조문을 찾을 수 없습니다")
    return ProvisionResponse(hit=hit)


@router.get("/v1/documents/{document_id}/changes", response_model=DocumentChangesResponse)
async def changes(document_id: UUID, from_date: date, to_date: date) -> DocumentChangesResponse:
    """Return the explicit unsupported response for unverified change bodies."""

    return DocumentChangesResponse(
        document_id=document_id,
        from_date=from_date,
        to_date=to_date,
        changes=[],
        supported=False,
        message="연혁 본문 계약 검증 후 활성화됩니다. HTML로 우회하지 않습니다.",
    )


@router.get("/v1/corpus/status", response_model=CorpusStatus)
async def corpus_status() -> CorpusStatus:
    """Expose corpus readiness and AI availability without leaking internals."""

    main = main_module()
    if isinstance(main.repository, PostgresLegalRepository):
        items, temporal_state, last_successful_sync = await main.repository.corpus_overview(
            main._current_korea_date()
        )
    else:
        items = await main.repository.corpus_items()
        temporal_state = await main._load_corpus_temporal_state(main.repository)
        last_successful_sync = await main.repository.last_sync()
    warnings = []
    if not temporal_state.ready:
        warnings.append("법령 corpus를 갱신·검증하는 동안 검색이 일시 중지되었습니다.")
    if any(item.state != "ready" for item in items):
        warnings.append("MVP 허용 목록 일부가 아직 수집되지 않았습니다.")
    if not main._ai_available():
        warnings.append(
            "AI가 비활성화되어 검색 전용 모드로 동작합니다."
            if main.settings.search_only_enabled
            else "AI가 비활성화되어 답변을 생성할 수 없습니다."
        )
    if main.collector_load_errors:
        warnings.append(
            f"collector 목업 원문 {len(main.collector_load_errors)}건을 읽지 못했습니다."
        )
    return CorpusStatus(
        last_successful_sync=last_successful_sync,
        corpus_snapshot_id=temporal_state.corpus_snapshot_id,
        supported_as_of_from=temporal_state.supported_as_of_from,
        supported_as_of_through=temporal_state.supported_as_of_through,
        corpus_search_ready=temporal_state.ready,
        corpus_search_unavailable_reason=temporal_state.reason,
        ai_available=main._ai_available(),
        ai_unavailable_reason=main._ai_unavailable_reason(),
        items=items,
        warnings=warnings,
    )
