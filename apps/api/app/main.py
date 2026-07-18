import asyncio
import base64
import json
from contextlib import asynccontextmanager
from datetime import date, datetime
from typing import Annotated
from uuid import UUID

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from app.adapters.memory_repository import repository as memory_repository
from app.adapters.mock_identity import identity_repository
from app.adapters.nvidia_nim_answerer import NvidiaNimAnswerer
from app.adapters.openai_answerer import OpenAIAnswerer, select_generation_hits, validate_draft
from app.adapters.openai_embedder import OpenAIEmbedder
from app.adapters.postgres_identity import ConsentRequiredError, PostgresIdentityRepository
from app.adapters.postgres_repository import PostgresLegalRepository
from app.adapters.supabase_auth import (
    SupabaseAuth,
    SupabaseAuthError,
    SupabaseAuthUnavailableError,
)
from app.application.answering import search_only_answer
from app.application.checklist_exports import render_csv, render_markdown, render_pdf
from app.application.question_tasks import QuestionTaskRegistry
from app.domain.auth_schemas import MockGoogleLoginRequest, MockLoginResponse
from app.domain.privacy import anonymous_rate_limit_subject, daily_subject_hash
from app.domain.schemas import (
    AiFallbackReason,
    ChecklistDocument,
    ChecklistExportFormat,
    Citation,
    ConversationPage,
    ConversationTurnPage,
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
question_tasks = QuestionTaskRegistry()
repository = (
    PostgresLegalRepository(settings.database_url) if settings.database_url else memory_repository
)
supabase_auth = (
    SupabaseAuth(
        settings.supabase_url,
        settings.supabase_secret_key,
        settings.request_timeout_seconds,
    )
    if settings.supabase_url and settings.supabase_secret_key
    else None
)
postgres_identity = (
    PostgresIdentityRepository(repository.engine)
    if isinstance(repository, PostgresLegalRepository) and supabase_auth
    else None
)
collector_load_errors: list[str] = []
if repository is memory_repository:
    _, collector_load_errors = memory_repository.load_collector_state(settings.collector_state_dir)
@asynccontextmanager
async def lifespan(_: FastAPI):
    yield
    if supabase_auth:
        await supabase_auth.aclose()


app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.web_origin],
    allow_credentials=False,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Authorization", "Content-Type", "X-Terms-Version", "X-Privacy-Version"],
)


def _require_mock_auth() -> None:
    if settings.environment == "production":
        raise HTTPException(status_code=404, detail="찾을 수 없습니다")


def _bearer_token(authorization: str | None) -> str:
    if not authorization:
        raise HTTPException(status_code=401, detail="로그인이 필요합니다")
    scheme, separator, token = authorization.partition(" ")
    token = token.strip()
    if (
        not separator
        or scheme.casefold() != "bearer"
        or not token
        or any(char.isspace() for char in token)
    ):
        raise HTTPException(status_code=401, detail="유효하지 않은 인증 헤더입니다")
    return token


async def _optional_user(authorization: str | None) -> MockUser | None:
    if authorization is None:
        return None
    token = _bearer_token(authorization)
    if supabase_auth and postgres_identity:
        try:
            return await postgres_identity.ensure_profile(await supabase_auth.verify_user(token))
        except ConsentRequiredError as exc:
            raise HTTPException(status_code=409, detail="회원가입 동의가 필요합니다.") from exc
        except SupabaseAuthUnavailableError as exc:
            raise HTTPException(
                status_code=503, detail="인증 서비스를 일시적으로 사용할 수 없습니다."
            ) from exc
        except SupabaseAuthError as exc:
            raise HTTPException(status_code=401, detail="유효하지 않은 인증 세션입니다.") from exc
    _require_mock_auth()
    user = identity_repository.user_for_token(token)
    if user is None:
        raise HTTPException(status_code=401, detail="유효하지 않은 세션입니다")
    return user


async def _authenticated_user(
    authorization: Annotated[str | None, Header()] = None,
    x_terms_version: Annotated[str | None, Header()] = None,
    x_privacy_version: Annotated[str | None, Header()] = None,
) -> MockUser:
    if supabase_auth and postgres_identity:
        try:
            user = await supabase_auth.verify_user(_bearer_token(authorization))
            if (x_terms_version is None) != (x_privacy_version is None):
                raise ConsentRequiredError
            if x_terms_version is not None and (
                x_terms_version != settings.terms_version
                or x_privacy_version != settings.privacy_version
            ):
                raise ConsentRequiredError
            return await postgres_identity.ensure_profile(user, x_terms_version, x_privacy_version)
        except ConsentRequiredError as exc:
            raise HTTPException(status_code=409, detail="회원가입 동의가 필요합니다.") from exc
        except SupabaseAuthUnavailableError as exc:
            raise HTTPException(
                status_code=503, detail="인증 서비스를 일시적으로 사용할 수 없습니다."
            ) from exc
        except SupabaseAuthError as exc:
            raise HTTPException(status_code=401, detail="유효하지 않은 인증 세션입니다.") from exc
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
    try:
        hits = await repository.search(payload.query, payload.as_of_date, payload.limit, None)
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail="법령 검색을 일시적으로 사용할 수 없습니다.",
        ) from exc
    if payload.source_kinds:
        hits = [hit for hit in hits if hit.source_kind in payload.source_kinds]
    return [hit for hit in hits if is_allowed_source_url(hit.source_url)]


@app.post("/v1/questions", response_model=QuestionResponse)
async def question(payload: QuestionRequest, request: Request) -> QuestionResponse:
    user = await _optional_user(request.headers.get("authorization"))
    owner = _question_owner(request, user)
    task = asyncio.current_task()
    if task is None:
        raise HTTPException(status_code=503, detail="질문 처리를 시작할 수 없습니다.")
    if not await question_tasks.register(owner, payload.client_request_id, task):
        raise HTTPException(status_code=409, detail="같은 요청이 이미 처리 중입니다.")
    try:
        await asyncio.sleep(0)
        return await _answer_question(payload, request, user)
    except asyncio.CancelledError as exc:
        raise HTTPException(status_code=499, detail="질문 처리가 취소되었습니다.") from exc
    finally:
        await question_tasks.unregister(owner, payload.client_request_id, task)


@app.post("/v1/questions/{client_request_id}/cancel", status_code=202)
async def cancel_question(client_request_id: UUID, request: Request) -> dict[str, bool]:
    user = await _optional_user(request.headers.get("authorization"))
    if not await question_tasks.cancel(_question_owner(request, user), client_request_id):
        raise HTTPException(status_code=404, detail="처리 중인 질문을 찾을 수 없습니다.")
    return {"cancelled": True}


async def _answer_question(
    payload: QuestionRequest, request: Request, user: MockUser | None
) -> QuestionResponse:
    use_ai = payload.answer_mode == "terra" and _ai_available()
    fallback_reason = _initial_fallback_reason(payload)
    diagnostics: dict[str, object] = {
        "schema_version": "1",
        "input_validation": {
            "status": "passed",
            "as_of_date": payload.as_of_date.isoformat(),
            "project_stage": payload.project_stage.value,
            "answer_mode": payload.answer_mode,
        },
        "parsing": {},
        "embedding": {
            "requested": payload.answer_mode == "terra",
            "attempted": False,
            "status": (
                "skipped_search_only"
                if payload.answer_mode == "search_only"
                else f"skipped_{_ai_unavailable_reason() or 'not_started'}"
            ),
            "dimensions": None,
        },
        "retrieval": {},
        "generation": {"attempted": False, "status": "not_attempted"},
        "outcome": {},
    }
    await _check_quota(
        request,
        "ai" if use_ai else "search",
        settings.ai_daily_limit if use_ai else settings.search_daily_limit,
        user=user,
    )
    await asyncio.sleep(0)
    query_embedding = None
    embedding_failed = False
    if use_ai and settings.openai_api_key:
        embedding_stage = diagnostics["embedding"]
        assert isinstance(embedding_stage, dict)
        embedding_stage.update({"attempted": True, "status": "started"})
        try:
            query_embedding = (await _embedder().embed([payload.question]))[0]
            embedding_stage.update(
                {"status": "succeeded", "dimensions": len(query_embedding)}
            )
        except Exception:
            embedding_failed = True
            embedding_stage.update({"status": "failed", "dimensions": None})
    elif use_ai:
        embedding_stage = diagnostics["embedding"]
        assert isinstance(embedding_stage, dict)
        embedding_stage.update({"attempted": False, "status": "skipped_provider_unavailable"})
    try:
        hits, search_trace = await repository.search_with_trace(
            payload.question, payload.as_of_date, 10, query_embedding
        )
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail="법령 검색을 일시적으로 사용할 수 없습니다.",
        ) from exc
    hits = [hit for hit in hits if is_allowed_source_url(hit.source_url)]
    diagnostics["retrieval"] = {
        **search_trace.as_dict(),
        "allowed_candidate_count": len(hits),
    }
    diagnostics["parsing"] = {
        "normalized_query": search_trace.normalized_query,
        "terms": list(search_trace.terms),
        "reference_detected": search_trace.reference_path is not None,
        "reference_title": search_trace.reference_title,
        "reference_path": search_trace.reference_path,
    }
    corpus_as_of = await repository.last_sync()
    if use_ai and not hits:
        fallback_reason = (
            AiFallbackReason.EMBEDDING_ERROR if embedding_failed else AiFallbackReason.NO_EVIDENCE
        )
    fallback = search_only_answer(payload, hits, corpus_as_of, fallback_reason=fallback_reason)
    fallback.request_id = str(payload.client_request_id)
    if not use_ai or not hits:
        generation_stage = diagnostics["generation"]
        assert isinstance(generation_stage, dict)
        generation_stage["status"] = (
            "skipped_no_evidence"
            if use_ai
            else "skipped_search_only"
            if payload.answer_mode == "search_only"
            else "skipped_ai_disabled"
        )
        return await _save_if_authenticated(user, payload, fallback, diagnostics)
    generation_stage = diagnostics["generation"]
    assert isinstance(generation_stage, dict)
    generation_hits = select_generation_hits(hits, settings.answer_evidence_max_characters)
    generation_stage.update({
        "attempted": True,
        "status": "started",
        "retrieved_evidence_count": len(hits),
        "selected_evidence_count": len(generation_hits),
        "dropped_evidence_count": len(hits) - len(generation_hits),
        "selected_evidence_characters": sum(len(hit.content) for hit in generation_hits),
    })
    try:
        draft = await _answerer().answer(payload, generation_hits)
    except Exception as exc:
        status_code = getattr(exc, "status_code", None)
        if status_code in {402, 429}:
            global ai_quota_exhausted
            ai_quota_exhausted = True
            fallback.fallback_reason = AiFallbackReason.BILLING_OR_QUOTA_ERROR
        else:
            fallback.fallback_reason = AiFallbackReason.GENERATION_ERROR
        generation_stage["status"] = (
            "billing_or_quota_error" if status_code in {402, 429} else "failed"
        )
        return await _save_if_authenticated(user, payload, fallback, diagnostics)
    if not validate_draft(draft, generation_hits):
        fallback.fallback_reason = AiFallbackReason.GROUNDING_FAILED
        generation_stage["status"] = "grounding_failed"
        return await _save_if_authenticated(user, payload, fallback, diagnostics)
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
        for index, hit in enumerate(generation_hits, 1)
    ]
    answer = QuestionResponse(
        request_id=str(payload.client_request_id),
        mode="ai",
        summary=draft.summary,
        scope=draft.scope,
        sections=draft.sections,
        checklist=draft.checklist,
        citations=citations,
        limitations=[*draft.limitations, "이 서비스는 법률 자문을 대체하지 않습니다."],
        corpus_as_of=corpus_as_of,
        requested_answer_mode=payload.answer_mode,
    )
    generation_stage["status"] = "succeeded"
    return await _save_if_authenticated(user, payload, answer, diagnostics)


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
    if supabase_auth and postgres_identity:
        try:
            await supabase_auth.verify_user(_bearer_token(authorization))
        except SupabaseAuthUnavailableError as exc:
            raise HTTPException(
                status_code=503, detail="인증 서비스를 일시적으로 사용할 수 없습니다."
            ) from exc
        except SupabaseAuthError as exc:
            raise HTTPException(status_code=401, detail="유효하지 않은 인증 세션입니다.") from exc
        return Response(status_code=204)
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
    if supabase_auth and postgres_identity:
        try:
            await supabase_auth.delete_user(await postgres_identity.auth_user_id(user.id))
            await postgres_identity.delete_account_data(user.id)
        except SupabaseAuthError as exc:
            raise HTTPException(status_code=502, detail="계정 삭제를 완료하지 못했습니다.") from exc
        return Response(status_code=204)
    identity_repository.delete_account(user.id)
    return Response(status_code=204)


@app.get("/v1/questions/history", response_model=list[QuestionHistoryEntry])
async def question_history(
    user: Annotated[MockUser, Depends(_authenticated_user)],
) -> list[QuestionHistoryEntry]:
    if postgres_identity:
        return await postgres_identity.list_history(user.id)
    return identity_repository.list_history(user.id)


@app.get("/v1/conversations", response_model=ConversationPage)
async def conversations(
    user: Annotated[MockUser, Depends(_authenticated_user)],
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
    cursor: str | None = None,
) -> ConversationPage:
    decoded = _decode_conversation_cursor(cursor) if cursor else None
    items, has_more = (
        await postgres_identity.list_conversations(user.id, limit, decoded)
        if postgres_identity
        else identity_repository.list_conversations(user.id, limit, decoded)
    )
    next_cursor = (
        _encode_cursor("conversation", items[-1].updated_at.isoformat(), items[-1].id)
        if has_more and items
        else None
    )
    return ConversationPage(items=items, has_more=has_more, next_cursor=next_cursor)


@app.get("/v1/conversations/{conversation_id}/turns", response_model=ConversationTurnPage)
async def conversation_turns(
    conversation_id: UUID,
    user: Annotated[MockUser, Depends(_authenticated_user)],
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
    cursor: str | None = None,
) -> ConversationTurnPage:
    decoded = _decode_turn_cursor(cursor) if cursor else None
    result = (
        await postgres_identity.list_conversation_turns(conversation_id, user.id, limit, decoded)
        if postgres_identity
        else identity_repository.list_conversation_turns(conversation_id, user.id, limit, decoded)
    )
    if result is None:
        raise HTTPException(status_code=404, detail="대화를 찾을 수 없습니다")
    items, has_more = result
    next_cursor = (
        _encode_cursor("turn", items[-1].turn_index or 0, items[-1].id)
        if has_more and items
        else None
    )
    return ConversationTurnPage(items=items, has_more=has_more, next_cursor=next_cursor)


@app.delete("/v1/conversations/{conversation_id}", status_code=204)
async def delete_conversation(
    conversation_id: UUID,
    user: Annotated[MockUser, Depends(_authenticated_user)],
) -> Response:
    deleted = (
        await postgres_identity.delete_conversation(conversation_id, user.id)
        if postgres_identity
        else identity_repository.delete_conversation(conversation_id, user.id)
    )
    if not deleted:
        raise HTTPException(status_code=404, detail="대화를 찾을 수 없습니다")
    return Response(status_code=204)


@app.get("/v1/questions/history/{history_id}", response_model=QuestionHistoryEntry)
async def question_history_detail(
    history_id: UUID, user: Annotated[MockUser, Depends(_authenticated_user)]
) -> QuestionHistoryEntry:
    return await _owned_history(history_id, user)


@app.delete("/v1/questions/history/{history_id}", status_code=204)
async def delete_question_history(
    history_id: UUID, user: Annotated[MockUser, Depends(_authenticated_user)]
) -> Response:
    deleted = (
        await postgres_identity.delete_history(history_id, user.id)
        if postgres_identity
        else identity_repository.delete_history(history_id, user.id)
    )
    if not deleted:
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
    entry = await _owned_history(history_id, user)
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
    if postgres_identity:
        await postgres_identity.record_export(user.id, history_id, export_format.value)
    else:
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
        ai_unavailable_reason=_ai_unavailable_reason(),
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
    request: Request, kind: str, limit: int, *, user: MockUser | None = None
) -> None:
    if user is not None and postgres_identity:
        account_limit = (
            settings.authenticated_ai_daily_limit
            if kind == "ai"
            else settings.authenticated_search_daily_limit
        )
        if not await postgres_identity.consume_quota(user.id, date.today(), kind, account_limit):
            raise HTTPException(status_code=429, detail="오늘의 계정 사용 한도를 초과했습니다.")
        return
    if user is not None:
        return
    today = date.today()
    subject = anonymous_rate_limit_subject(
        request.headers,
        request.client.host if request.client else None,
        trust_vercel_proxy=settings.environment == "production",
    )
    subject_hash = daily_subject_hash(subject, settings.rate_limit_secret, today)
    if not await repository.consume_quota(subject_hash, today, kind, limit):
        raise HTTPException(status_code=429, detail="오늘의 익명 사용 한도를 초과했습니다")


def _ai_available() -> bool:
    return settings.ai_enabled and not ai_quota_exhausted


def _question_owner(request: Request, user: MockUser | None) -> str:
    if user is not None:
        return f"user:{user.id}"
    subject = anonymous_rate_limit_subject(
        request.headers,
        request.client.host if request.client else None,
        trust_vercel_proxy=settings.environment == "production",
    )
    return "anonymous:" + daily_subject_hash(
        subject, settings.rate_limit_secret, date.today()
    )


def _answerer() -> OpenAIAnswerer | NvidiaNimAnswerer:
    if settings.answer_provider == "nvidia_nim":
        return NvidiaNimAnswerer(
            api_key=settings.nvidia_api_key or "",
            base_url=settings.nvidia_base_url,
            model=settings.nvidia_answer_model,
            timeout_seconds=settings.answer_timeout_seconds,
            max_output_tokens=settings.answer_max_output_tokens,
        )
    return OpenAIAnswerer(
        api_key=settings.openai_api_key or "", model=settings.openai_answer_model
    )
def _ai_unavailable_reason() -> str | None:
    if not settings.ai_enabled:
        return AiFallbackReason.AI_DISABLED.value
    if ai_quota_exhausted:
        return AiFallbackReason.QUOTA_EXHAUSTED.value
    return None


def _initial_fallback_reason(payload: QuestionRequest) -> AiFallbackReason | None:
    if payload.answer_mode == "search_only":
        return None
    unavailable_reason = _ai_unavailable_reason()
    return AiFallbackReason(unavailable_reason) if unavailable_reason else None


async def _save_if_authenticated(
    user: MockUser | None,
    payload: QuestionRequest,
    response: QuestionResponse,
    diagnostics: dict[str, object] | None = None,
) -> QuestionResponse:
    emit_question_outcome(response.request_id, response.mode)
    if diagnostics is not None:
        diagnostics["outcome"] = {
            "mode": response.mode,
            "result_status": response.result_status,
            "no_results_reason": response.no_results_reason,
            "fallback_reason": (
                response.fallback_reason.value if response.fallback_reason else None
            ),
            "sections_count": len(response.sections),
            "citations_count": len(response.citations),
        }
    if user is not None:
        # Previous turns are transient model input. Persisting them on every new
        # history row would duplicate prior answers and expand retained user data.
        stored_payload = payload.model_copy(update={"conversation_context": []})
        if postgres_identity:
            try:
                await postgres_identity.save_question(
                    user.id, stored_payload, response, diagnostics=diagnostics
                )
            except ValueError as exc:
                raise HTTPException(status_code=404, detail="대화를 찾을 수 없습니다") from exc
        else:
            try:
                identity_repository.save_question(user.id, stored_payload, response)
            except ValueError as exc:
                raise HTTPException(status_code=404, detail="대화를 찾을 수 없습니다") from exc
    return response


def _encode_cursor(kind: str, value: str | int, item_id: UUID) -> str:
    payload = json.dumps(
        {"v": 1, "kind": kind, "value": value, "id": str(item_id)},
        separators=(",", ":"),
    )
    return base64.urlsafe_b64encode(payload.encode()).decode().rstrip("=")


def _decode_cursor(cursor: str, kind: str) -> tuple[object, UUID]:
    try:
        padded = cursor + "=" * (-len(cursor) % 4)
        payload = json.loads(base64.urlsafe_b64decode(padded).decode())
        if payload != {"v": 1, "kind": kind, "value": payload["value"], "id": payload["id"]}:
            raise ValueError
        return payload["value"], UUID(payload["id"])
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=400, detail="유효하지 않은 페이지 커서입니다") from exc


def _decode_conversation_cursor(cursor: str) -> tuple[datetime, UUID]:
    value, item_id = _decode_cursor(cursor, "conversation")
    try:
        return datetime.fromisoformat(str(value)), item_id
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="유효하지 않은 페이지 커서입니다") from exc


def _decode_turn_cursor(cursor: str) -> tuple[int, UUID]:
    value, item_id = _decode_cursor(cursor, "turn")
    if not isinstance(value, int) or value < 1:
        raise HTTPException(status_code=400, detail="유효하지 않은 페이지 커서입니다")
    return value, item_id


async def _owned_history(history_id: UUID, user: MockUser) -> QuestionHistoryEntry:
    entry = (
        await postgres_identity.get_history(history_id, user.id)
        if postgres_identity
        else identity_repository.get_history(history_id, user.id)
    )
    if entry is None:
        # 존재 여부를 숨겨 다른 사용자의 ID 열거를 막는다.
        raise HTTPException(status_code=404, detail="질문 이력을 찾을 수 없습니다")
    return entry
