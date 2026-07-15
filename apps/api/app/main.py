from datetime import date
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from app.adapters.memory_repository import repository as memory_repository
from app.adapters.mock_identity import identity_repository
from app.adapters.openai_answerer import OpenAIAnswerer, validate_draft
from app.adapters.openai_embedder import OpenAIEmbedder
from app.adapters.postgres_repository import PostgresLegalRepository
from app.application.answering import search_only_answer
from app.application.checklist_exports import render_csv, render_markdown, render_pdf
from app.domain.auth_schemas import MockGoogleLoginRequest, MockLoginResponse
from app.domain.privacy import daily_subject_hash
from app.domain.schemas import (
    ChecklistDocument,
    ChecklistExportFormat,
    Citation,
    CorpusStatus,
    DocumentChangesResponse,
    MockUser,
    ProvisionResponse,
    QuestionHistoryEntry,
    QuestionRequest,
    QuestionResponse,
    SearchHit,
    SearchRequest,
)
from app.domain.source_urls import is_allowed_source_url
from app.observability import emit_question_outcome
from app.settings import get_settings

settings = get_settings()
ai_quota_exhausted = False
repository = (
    PostgresLegalRepository(settings.database_url) if settings.database_url else memory_repository
)
collector_load_errors: list[str] = []
if repository is memory_repository:
    _, collector_load_errors = memory_repository.load_collector_state(
        settings.collector_state_dir
    )
app = FastAPI(title=settings.app_name, version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.web_origin],
    allow_credentials=False,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)


def _require_mock_auth() -> None:
    if settings.environment == "production":
        raise HTTPException(status_code=404, detail="찾을 수 없습니다")


def _bearer_token(authorization: str | None) -> str:
    if not authorization:
        raise HTTPException(status_code=401, detail="로그인이 필요합니다")
    scheme, separator, token = authorization.partition(" ")
    if not separator or scheme.casefold() != "bearer" or not token:
        raise HTTPException(status_code=401, detail="유효하지 않은 인증 헤더입니다")
    return token


def _optional_user(authorization: str | None) -> MockUser | None:
    if authorization is None:
        return None
    _require_mock_auth()
    token = _bearer_token(authorization)
    user = identity_repository.user_for_token(token)
    if user is None:
        raise HTTPException(status_code=401, detail="유효하지 않은 세션입니다")
    return user


def _authenticated_user(
    authorization: Annotated[str | None, Header()] = None,
) -> MockUser:
    _require_mock_auth()
    user = identity_repository.user_for_token(_bearer_token(authorization))
    if user is None:
        raise HTTPException(status_code=401, detail="유효하지 않은 세션입니다")
    return user


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
    return [hit for hit in hits if is_allowed_source_url(hit.source_url)]


@app.post("/v1/questions", response_model=QuestionResponse)
async def question(payload: QuestionRequest, request: Request) -> QuestionResponse:
    user = _optional_user(request.headers.get("authorization"))
    use_ai = payload.answer_mode == "terra" and _ai_available()
    await _check_quota(
        request,
        "ai" if use_ai else "search",
        settings.ai_daily_limit if use_ai else settings.search_daily_limit,
        authenticated=user is not None,
    )
    query_embedding = None
    if use_ai:
        try:
            query_embedding = (await _embedder().embed([payload.question]))[0]
        except Exception:
            query_embedding = None
    hits = await repository.search(payload.question, payload.as_of_date, 10, query_embedding)
    hits = [hit for hit in hits if is_allowed_source_url(hit.source_url)]
    corpus_as_of = await repository.last_sync()
    fallback = search_only_answer(payload, hits, corpus_as_of)
    if not use_ai or not hits:
        return _save_if_authenticated(user, payload, fallback)
    try:
        draft = await OpenAIAnswerer(
            api_key=settings.openai_api_key or "", model=settings.openai_answer_model
        ).answer(payload, hits)
    except Exception as exc:
        status_code = getattr(exc, "status_code", None)
        if status_code in {402, 429}:
            global ai_quota_exhausted
            ai_quota_exhausted = True
        return _save_if_authenticated(user, payload, fallback)
    if not validate_draft(draft, hits):
        return _save_if_authenticated(user, payload, fallback)
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
    answer = QuestionResponse(
        request_id=str(uuid4()),
        mode="ai",
        summary=draft.summary,
        scope=draft.scope,
        sections=draft.sections,
        checklist=draft.checklist,
        citations=citations,
        limitations=[*draft.limitations, "이 서비스는 법률 자문을 대체하지 않습니다."],
        corpus_as_of=corpus_as_of,
    )
    return _save_if_authenticated(user, payload, answer)


@app.post("/v1/auth/mock/google", response_model=MockLoginResponse)
async def mock_google_login(payload: MockGoogleLoginRequest) -> MockLoginResponse:
    _require_mock_auth()
    token, user = identity_repository.login_google(payload.email, payload.display_name)
    return MockLoginResponse(access_token=token, user=user)


@app.get("/v1/auth/me", response_model=MockUser)
async def current_user(
    user: Annotated[MockUser, Depends(_authenticated_user)],
) -> MockUser:
    return user


@app.post("/v1/auth/logout", status_code=204)
async def logout(authorization: Annotated[str | None, Header()] = None) -> Response:
    _require_mock_auth()
    token = _bearer_token(authorization)
    if identity_repository.user_for_token(token) is None:
        raise HTTPException(status_code=401, detail="유효하지 않은 세션입니다")
    identity_repository.logout(token)
    return Response(status_code=204)


@app.delete("/v1/account", status_code=204)
async def delete_account(
    user: Annotated[MockUser, Depends(_authenticated_user)],
) -> Response:
    identity_repository.delete_account(user.id)
    return Response(status_code=204)


@app.get("/v1/questions/history", response_model=list[QuestionHistoryEntry])
async def question_history(
    user: Annotated[MockUser, Depends(_authenticated_user)],
) -> list[QuestionHistoryEntry]:
    return identity_repository.list_history(user.id)


@app.get("/v1/questions/history/{history_id}", response_model=QuestionHistoryEntry)
async def question_history_detail(
    history_id: UUID, user: Annotated[MockUser, Depends(_authenticated_user)]
) -> QuestionHistoryEntry:
    return _owned_history(history_id, user)


@app.delete("/v1/questions/history/{history_id}", status_code=204)
async def delete_question_history(
    history_id: UUID, user: Annotated[MockUser, Depends(_authenticated_user)]
) -> Response:
    if not identity_repository.delete_history(history_id, user.id):
        raise HTTPException(status_code=404, detail="질문 이력을 찾을 수 없습니다")
    return Response(status_code=204)


@app.get("/v1/questions/history/{history_id}/checklist")
async def export_checklist(
    history_id: UUID,
    user: Annotated[MockUser, Depends(_authenticated_user)],
    export_format: Annotated[ChecklistExportFormat, Query(alias="format")] = (
        ChecklistExportFormat.MARKDOWN
    ),
) -> StreamingResponse:
    entry = _owned_history(history_id, user)
    document = ChecklistDocument(
        title="에너지 법령 체크리스트",
        as_of_date=entry.request.as_of_date,
        project_stage=entry.request.project_stage,
        items=entry.response.checklist,
        citations=entry.response.citations,
    )
    renderers = {
        ChecklistExportFormat.MARKDOWN: (render_markdown, "text/markdown; charset=utf-8"),
        ChecklistExportFormat.CSV: (render_csv, "text/csv; charset=utf-8"),
        ChecklistExportFormat.PDF: (render_pdf, "application/pdf"),
    }
    renderer, media_type = renderers[export_format]
    content = renderer(document)
    identity_repository.record_export(user.id, history_id, export_format.value)
    filename = f"checklist-{history_id}.{export_format.value}"
    return StreamingResponse(
        iter([content]),
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.get("/v1/provisions/{provision_id}", response_model=ProvisionResponse)
async def provision(provision_id: UUID, as_of_date: date | None = None) -> ProvisionResponse:
    hit = await repository.provision(provision_id, as_of_date or date.today())
    if hit is None or not is_allowed_source_url(hit.source_url):
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
    if collector_load_errors:
        warnings.append(f"collector 목업 원문 {len(collector_load_errors)}건을 읽지 못했습니다.")
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


async def _check_quota(
    request: Request, kind: str, limit: int, *, authenticated: bool = False
) -> None:
    if authenticated:
        return
    today = date.today()
    subject = request.client.host if request.client else "unknown"
    subject_hash = daily_subject_hash(subject, settings.rate_limit_secret, today)
    if not await repository.consume_quota(subject_hash, today, kind, limit):
        raise HTTPException(status_code=429, detail="오늘의 익명 사용 한도를 초과했습니다")


def _ai_available() -> bool:
    return settings.ai_enabled and not ai_quota_exhausted


def _save_if_authenticated(
    user: MockUser | None, payload: QuestionRequest, response: QuestionResponse
) -> QuestionResponse:
    emit_question_outcome(response.request_id, response.mode)
    if user is not None:
        identity_repository.save_question(user.id, payload, response)
    return response


def _owned_history(history_id: UUID, user: MockUser) -> QuestionHistoryEntry:
    entry = identity_repository.get_history(history_id, user.id)
    if entry is None:
        # 존재 여부를 숨겨 다른 사용자의 ID 열거를 막는다.
        raise HTTPException(status_code=404, detail="질문 이력을 찾을 수 없습니다")
    return entry
