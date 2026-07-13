from datetime import date
from uuid import UUID, uuid4

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from openai import APIStatusError

from app.adapters.memory_repository import repository as memory_repository
from app.adapters.openai_answerer import OpenAIAnswerer, validate_draft
from app.adapters.openai_embedder import OpenAIEmbedder
from app.adapters.postgres_repository import PostgresLegalRepository
from app.application.answering import search_only_answer
from app.domain.privacy import daily_subject_hash
from app.domain.schemas import (
    Citation,
    CorpusStatus,
    DocumentChangesResponse,
    ProvisionResponse,
    QuestionRequest,
    QuestionResponse,
    SearchHit,
    SearchRequest,
)
from app.settings import get_settings

settings = get_settings()
ai_quota_exhausted = False
repository = (
    PostgresLegalRepository(settings.database_url) if settings.database_url else memory_repository
)
app = FastAPI(title=settings.app_name, version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.web_origin],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/v1/search", response_model=list[SearchHit])
async def search(payload: SearchRequest, request: Request) -> list[SearchHit]:
    await _check_quota(request, "search", settings.search_daily_limit)
    query_embedding = None
    if _ai_available():
        try:
            query_embedding = (await _embedder().embed([payload.query]))[0]
        except Exception:
            query_embedding = None
    hits = await repository.search(
        payload.query, payload.as_of_date, payload.limit, query_embedding
    )
    if payload.source_kinds:
        hits = [hit for hit in hits if hit.source_kind in payload.source_kinds]
    return hits


@app.post("/v1/questions", response_model=QuestionResponse)
async def question(payload: QuestionRequest, request: Request) -> QuestionResponse:
    await _check_quota(
        request,
        "ai" if _ai_available() else "search",
        settings.ai_daily_limit if _ai_available() else settings.search_daily_limit,
    )
    query_embedding = None
    if _ai_available():
        try:
            query_embedding = (await _embedder().embed([payload.question]))[0]
        except Exception:
            query_embedding = None
    hits = await repository.search(payload.question, payload.as_of_date, 10, query_embedding)
    corpus_as_of = await repository.last_sync()
    fallback = search_only_answer(payload, hits, corpus_as_of)
    if not _ai_available() or not hits:
        return fallback
    try:
        draft = await OpenAIAnswerer(
            api_key=settings.openai_api_key or "", model=settings.openai_answer_model
        ).answer(payload, hits)
    except APIStatusError as exc:
        if exc.status_code in {402, 429}:
            global ai_quota_exhausted
            ai_quota_exhausted = True
            return fallback
        raise HTTPException(status_code=502, detail="답변 모델을 사용할 수 없습니다") from exc
    except Exception:
        return fallback
    if not validate_draft(draft, len(hits)):
        return fallback
    citations = [
        Citation(
            id=f"C{index}",
            provision_id=hit.provision_id,
            document_title=hit.document_title,
            version_label=hit.version_label,
            path=hit.path,
            quote=hit.content,
            source_url=hit.source_url,
        )
        for index, hit in enumerate(hits, 1)
    ]
    return QuestionResponse(
        request_id=str(uuid4()),
        mode="ai",
        summary=draft.summary,
        scope=draft.scope,
        sections=draft.sections,
        checklist=draft.checklist,
        citations=citations,
        limitations=[*draft.limitations, "법률 자문을 대체하지 않습니다."],
        corpus_as_of=corpus_as_of,
    )


@app.get("/v1/provisions/{provision_id}", response_model=ProvisionResponse)
async def provision(provision_id: UUID, as_of_date: date | None = None) -> ProvisionResponse:
    hit = await repository.provision(provision_id, as_of_date or date.today())
    if hit is None:
        raise HTTPException(status_code=404, detail="조문을 찾을 수 없습니다")
    return ProvisionResponse(hit=hit)


@app.get("/v1/documents/{document_id}/changes", response_model=DocumentChangesResponse)
async def changes(document_id: UUID, from_date: date, to_date: date) -> DocumentChangesResponse:
    return DocumentChangesResponse(
        document_id=document_id,
        from_date=from_date,
        to_date=to_date,
        changes=[],
        supported=False,
        message="연혁 본문 계약 검증 후 활성화됩니다. HTML로 우회하지 않습니다.",
    )


@app.get("/v1/corpus/status", response_model=CorpusStatus)
async def corpus_status() -> CorpusStatus:
    items = await repository.corpus_items()
    warnings = []
    if any(item.state != "ready" for item in items):
        warnings.append("MVP 허용 목록 일부가 아직 수집되지 않았습니다.")
    if not _ai_available():
        warnings.append("AI가 비활성화되어 검색 전용 모드로 동작합니다.")
    return CorpusStatus(
        last_successful_sync=await repository.last_sync(),
        ai_available=_ai_available(),
        items=items,
        warnings=warnings,
    )


def _embedder() -> OpenAIEmbedder:
    return OpenAIEmbedder(
        api_key=settings.openai_api_key or "",
        model=settings.openai_embedding_model,
        dimensions=settings.embedding_dimensions,
    )


async def _check_quota(request: Request, kind: str, limit: int) -> None:
    today = date.today()
    subject = request.client.host if request.client else "unknown"
    subject_hash = daily_subject_hash(subject, settings.rate_limit_secret, today)
    if not await repository.consume_quota(subject_hash, today, kind, limit):
        raise HTTPException(status_code=429, detail="오늘의 익명 사용 한도를 초과했습니다")


def _ai_available() -> bool:
    return settings.ai_enabled and not ai_quota_exhausted
