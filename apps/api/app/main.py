"""법령 RAG API와 v2 LlamaIndex 검색 경계를 제공한다."""

import asyncio
import base64
import json
import time
from contextlib import asynccontextmanager
from datetime import date, datetime
from functools import lru_cache
from typing import Annotated, Literal
from uuid import UUID

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from law_rag_core.ports.repository import LegalRepository
from law_rag_llamaindex.active_index import ActiveGenerationIndexProvider
from law_rag_llamaindex.config import get_settings as get_llamaindex_settings
from law_rag_llamaindex.embedding import build_embedder as build_llamaindex_embedder
from law_rag_llamaindex.generations import PostgresGenerationRepository
from law_rag_llamaindex.retriever import search as llamaindex_search
from law_rag_llamaindex.store import build_generation_vector_store
from llama_index.core import VectorStoreIndex
from sqlalchemy import create_engine, text
from sqlalchemy.ext.asyncio import create_async_engine

from app.adapters.llamaindex_repository import LlamaIndexLegalRepository
from app.adapters.memory_repository import repository as memory_repository
from app.adapters.mock_identity import identity_repository
from app.adapters.nvidia_nim_answerer import NvidiaNimAnswerer
from app.adapters.nvidia_nim_embedder import NvidiaNimEmbedder
from app.adapters.nvidia_nim_route_classifier import NvidiaNimQuestionRouter
from app.adapters.openai_answerer import (
    DraftAnswer,
    build_messages_v2,
    select_generation_hits,
    validate_draft,
)
from app.adapters.postgres_identity import ConsentRequiredError, PostgresIdentityRepository
from app.adapters.postgres_repository import PostgresLegalRepository
from app.adapters.supabase_auth import (
    SupabaseAuth,
    SupabaseAuthError,
    SupabaseAuthUnavailableError,
)
from app.application.answering import (
    clarification_resubmission_summary,
    post_generation_clarification_answer,
    route_guidance_fallback,
    search_only_answer,
)
from app.application.checklist_exports import render_csv, render_markdown, render_pdf
from app.application.question_tasks import QuestionTaskRegistry
from app.application.request_budget import RequestBudget, StageTimeoutError
from app.domain.answer_actions import derive_answer_action
from app.domain.auth_schemas import MockGoogleLoginRequest, MockLoginResponse
from app.domain.corpus_temporal_contract import (
    UnsupportedCorpusDateError,
    korea_today,
    require_supported_corpus_date,
)
from app.domain.embedding_profiles import NVIDIA_NEMOTRON_512_PROFILE
from app.domain.errors import CorpusSearchUnavailableError
from app.domain.generation_profiles import NVIDIA_NEMOTRON_ULTRA_ANSWER_PROFILE_V2
from app.domain.privacy import anonymous_rate_limit_subject, daily_subject_hash
from app.domain.routing import RouteDecision, route_question
from app.domain.schemas import (
    AiFallbackReason,
    ChecklistDocument,
    ChecklistExportFormat,
    Citation,
    ConversationPage,
    ConversationTurnPage,
    CorpusStatus,
    CorpusTemporalState,
    DocumentChangesResponse,
    MockUser,
    ProvisionResponse,
    QuestionHistoryEntry,
    QuestionRequest,
    QuestionResponse,
    SearchHit,
    SearchRequest,
)
from app.domain.search_queries import SearchTrace
from app.domain.source_urls import is_allowed_source_url
from app.observability import (
    QuestionStageTimingOutcome,
    emit_question_outcome,
    emit_question_stage_timing,
    emit_route_outcome,
)
from app.settings import get_settings

settings = get_settings()
ai_quota_exhausted = False
question_tasks = QuestionTaskRegistry()
repository = (
    PostgresLegalRepository(settings.database_url) if settings.database_url else memory_repository
)
llamaindex_settings = get_llamaindex_settings()
llamaindex_vector_store = None
llamaindex_embedder = None
llamaindex_repository = None


@lru_cache(maxsize=1)
def _build_llamaindex_resources(
    database_url: str | None, nvidia_api_key: str | None
) -> tuple[object, object, LlamaIndexLegalRepository] | None:
    """v2 검색에 필요한 리소스를 모두 구성하거나 미구성 상태를 반환한다.

    데이터베이스 URL 또는 NVIDIA 키가 없으면 외부 초기화를 시도하지 않는다.
    """
    if not database_url or not nvidia_api_key:
        return None

    embedder = build_llamaindex_embedder(llamaindex_settings)
    async_engine = create_async_engine(_llamaindex_async_database_url(database_url))
    sync_engine = create_engine(_llamaindex_sync_database_url(database_url))

    async def close_engines() -> None:
        sync_engine.dispose()
        await async_engine.dispose()

    provider = ActiveGenerationIndexProvider(
        PostgresGenerationRepository(async_engine),
        lambda generation: build_generation_vector_store(
            llamaindex_settings,
            generation,
            engine=sync_engine,
            async_engine=async_engine,
            perform_setup=False,
        ),
        lambda vector_store: VectorStoreIndex.from_vector_store(vector_store, embed_model=embedder),
        close=close_engines,
    )
    v2_repository = LlamaIndexLegalRepository(repository, provider, embedder)
    return provider, embedder, v2_repository


def _llamaindex_async_database_url(database_url: str) -> str:
    """Normalize the shared URL for the active-generation async catalog reader."""

    if database_url.startswith("postgresql+asyncpg://"):
        return database_url
    if database_url.startswith("postgresql://"):
        return database_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return database_url


def _llamaindex_sync_database_url(database_url: str) -> str:
    """Normalize the shared URL for the active generation's PGVector store."""

    if database_url.startswith("postgresql+psycopg://"):
        return database_url
    if database_url.startswith("postgresql+asyncpg://"):
        return database_url.replace("postgresql+asyncpg://", "postgresql+psycopg://", 1)
    if database_url.startswith("postgresql://"):
        return database_url.replace("postgresql://", "postgresql+psycopg://", 1)
    return database_url


def _llamaindex_resources() -> tuple[object | None, object | None, object | None] | None:
    """테스트 주입 리소스를 보존하며 v2 리소스를 반환한다.

    구성 또는 초기화에 실패하면 호출자가 준비되지 않은 v2 상태로 처리하도록 `None`을 반환한다.
    """
    global llamaindex_embedder, llamaindex_repository, llamaindex_vector_store

    if any(
        resource is not None
        for resource in (llamaindex_vector_store, llamaindex_embedder, llamaindex_repository)
    ):
        return llamaindex_vector_store, llamaindex_embedder, llamaindex_repository

    try:
        resources = _build_llamaindex_resources(
            settings.database_url, llamaindex_settings.nvidia_api_key
        )
    except Exception:
        return None
    if resources is None:
        return None

    llamaindex_vector_store, llamaindex_embedder, llamaindex_repository = resources
    return llamaindex_vector_store, llamaindex_embedder, llamaindex_repository


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
    """애플리케이션 종료 시 선택적 외부 인증 리소스를 정리한다."""
    yield
    if supabase_auth:
        await supabase_auth.aclose()
    if isinstance(llamaindex_vector_store, ActiveGenerationIndexProvider):
        await llamaindex_vector_store.aclose()


app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.web_origins,
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
    """서비스 상태를 반환한다."""
    return {"status": "ok"}


@app.post("/v1/search", response_model=list[SearchHit])
async def search(payload: SearchRequest, request: Request) -> list[SearchHit]:
    """v1 저장소에서 허용된 법령 검색 결과만 반환한다."""
    await _require_supported_as_of_date(payload.as_of_date, repository)
    await _check_quota("search")
    try:
        hits = await repository.search(payload.query, payload.as_of_date, payload.limit, None)
    except CorpusSearchUnavailableError as exc:
        raise _corpus_unready_http_error() from exc
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail="법령 검색을 일시적으로 사용할 수 없습니다.",
        ) from exc
    if payload.source_kinds:
        hits = [hit for hit in hits if hit.source_kind in payload.source_kinds]
    return [hit for hit in hits if is_allowed_source_url(hit.source_url)]


def _v2_not_ready_http_error() -> HTTPException:
    return HTTPException(
        status_code=503,
        detail={"code": "v2_search_not_ready", "message": "v2 검색을 아직 사용할 수 없습니다."},
    )


async def _v2_index_ready() -> bool:
    """active pointer가 가리키는 검증된 generation만 fail-closed로 허용한다."""
    if not settings.database_url:
        return False
    try:
        async with repository.engine.connect() as connection:  # type: ignore[union-attr]
            row = (
                await connection.execute(
                    text(
                        "SELECT generation.status "
                        "FROM llamaindex_active_generation AS active "
                        "JOIN llamaindex_retrieval_generations AS generation "
                        "ON generation.generation_id = active.generation_id"
                    )
                )
            ).first()
    except Exception:
        return False
    return row is not None and row[0] == "active"


async def _v2_ready() -> bool:
    """준비 표지 접근 실패 시 fail-closed로 v2 준비 상태를 확인한다."""
    try:
        return await _v2_index_ready()
    except Exception:
        return False


@app.post("/v2/search", response_model=list[SearchHit])
async def search_v2(payload: SearchRequest, request: Request) -> list[SearchHit]:
    """준비된 v2 인덱스에서 허용된 법령 검색 결과만 반환한다.

    리소스 또는 색인 준비 상태를 확인할 수 없으면 검색 결과 대신 503을 반환한다.
    """
    resources = _llamaindex_resources()
    if resources is None:
        raise _v2_not_ready_http_error()
    vector_store, embedder, _ = resources
    if vector_store is None or embedder is None:
        raise _v2_not_ready_http_error()
    if not await _v2_ready():
        raise _v2_not_ready_http_error()
    active = getattr(vector_store, "active", None)
    if active is not None:
        try:
            vector_store = (await active()).store
        except Exception:
            raise _v2_not_ready_http_error() from None
    hits = await llamaindex_search(
        vector_store,
        embedder,
        payload.query,
        payload.as_of_date,
        payload.limit,
    )
    if payload.source_kinds:
        hits = [hit for hit in hits if hit.source_kind in payload.source_kinds]
    return [hit for hit in hits if is_allowed_source_url(hit.source_url)]


async def _handle_question(
    payload: QuestionRequest, request: Request, repository: LegalRepository
) -> QuestionResponse:
    """질문 요청의 예산, 인증, 중복 등록 및 취소 정리를 조정한다.

    등록한 작업은 모든 성공·실패·취소 경로에서 해제하고, 요청 단계 관측 이벤트는 정확히 한 번
    기록한다.
    """
    budget = RequestBudget.start(
        settings.question_request_timeout_seconds,
        settings.response_reserve_seconds,
    )
    request_id = str(payload.client_request_id)
    request_started = time.monotonic()
    # 0045: 기본값은 "failed" - 아래 어떤 성공 경로에도 도달하지 못하고 조기 반환(인증·검증
    # 실패 등 stage 시작 전 오류 포함)되면 이 값 그대로 finally에서 기록된다.
    outcome: QuestionStageTimingOutcome = "failed"
    try:
        user = await _optional_user(request.headers.get("authorization"))
        owner = _question_owner(request, user)
        task = asyncio.current_task()
        if task is None:
            raise HTTPException(status_code=503, detail="질문 처리를 시작할 수 없습니다.")
        if not await question_tasks.register(owner, payload.client_request_id, task):
            raise HTTPException(status_code=409, detail="같은 요청이 이미 처리 중입니다.")
        try:
            await asyncio.sleep(0)
            async with asyncio.timeout(budget.remaining_seconds()):
                response = await _answer_question(payload, request, user, budget, repository)
        except asyncio.CancelledError as exc:
            outcome = "failed"
            raise HTTPException(status_code=499, detail="질문 처리가 취소되었습니다.") from exc
        except TimeoutError as exc:
            outcome = "timed_out"
            raise HTTPException(
                status_code=503,
                detail="질문 처리 시간이 초과되었습니다. 잠시 후 다시 시도해 주세요.",
            ) from exc
        finally:
            await question_tasks.unregister(owner, payload.client_request_id, task)
        outcome = _request_outcome_for_response(response)
        return response
    finally:
        # 0045: finally라서 위 모든 조기 반환(인증 401/409, corpus 503, quota 429,
        # stage 예외로 인한 503 등)에서도 request 단위 마무리 이벤트가 정확히 한 번 나간다.
        emit_question_stage_timing(
            request_id,
            "request",
            outcome,
            _elapsed_ms(request_started),
            _remaining_ms(budget),
        )


@app.post("/v1/questions", response_model=QuestionResponse)
async def question(payload: QuestionRequest, request: Request) -> QuestionResponse:
    """v1 검색 저장소로 법령 질문에 응답한다."""
    return await _handle_question(payload, request, repository)


@app.post("/v2/questions", response_model=QuestionResponse)
async def question_v2(payload: QuestionRequest, request: Request) -> QuestionResponse:
    """준비된 v2 검색 저장소로 법령 질문에 응답한다.

    v2 리소스 또는 색인 준비 상태를 확인할 수 없으면 질문을 처리하지 않고 503을 반환한다.
    """
    resources = _llamaindex_resources()
    if resources is None:
        raise _v2_not_ready_http_error()
    _, _, v2_repository = resources
    if v2_repository is None:
        raise _v2_not_ready_http_error()
    if not await _v2_ready():
        raise _v2_not_ready_http_error()
    return await _handle_question(payload, request, v2_repository)


@app.post("/v1/questions/{client_request_id}/cancel", status_code=202)
async def cancel_question(client_request_id: UUID, request: Request) -> dict[str, bool]:
    """같은 요청 소유자가 실행 중인 질문을 취소한다."""
    user = await _optional_user(request.headers.get("authorization"))
    if not await question_tasks.cancel(_question_owner(request, user), client_request_id):
        raise HTTPException(status_code=404, detail="처리 중인 질문을 찾을 수 없습니다.")
    return {"cancelled": True}


async def _retrieve_question_evidence(
    payload: QuestionRequest,
    query_embedding: list[float] | None,
    repository: LegalRepository,
) -> tuple[list[SearchHit], SearchTrace, datetime | None]:
    """검색과 corpus 동기화 시각 조회를 하나의 retrieval 단계로 실행한다.

    두 작업이 독립 예산을 소비해 전체 retrieval 허용 시간을 초과하지 않도록 같은 예산 단계에
    묶는다.
    """
    hits, trace = await repository.search_with_trace(
        payload.question,
        payload.as_of_date,
        10,
        query_embedding,
        NVIDIA_NEMOTRON_512_PROFILE.key if query_embedding is not None else None,
    )
    return hits, trace, await repository.last_sync()


def _elapsed_ms(started_at: float) -> int:
    """관측용 실제 경과 시간을 밀리초로 반환한다.

    예산 계산용 clock을 다시 호출하지 않아 테스트가 주입한 clock의 소비 순서를 바꾸지 않는다.
    """
    return max(0, round((time.monotonic() - started_at) * 1000))


def _remaining_ms(budget: RequestBudget) -> int:
    """이미 계산된 마감 시각으로 남은 시간을 밀리초로 반환한다.

    `budget.clock()`을 다시 호출하지 않아 예산 판정에 쓰이는 clock 소비 순서를 보존한다.
    """
    return max(0, round((budget.deadline - time.monotonic()) * 1000))


def _request_outcome_for_response(response: QuestionResponse) -> QuestionStageTimingOutcome:
    """응답의 안전한 fallback 여부로 요청 관측 결과를 분류한다.

    검증된 근거를 제공한 검색 전용 fallback은 실패가 아닌 `degraded`로 기록한다.
    """
    return "degraded" if response.fallback_reason is not None else "succeeded"


def _search_only_disabled_error() -> HTTPException:
    return HTTPException(status_code=503, detail="검색 전용 기능이 비활성화되어 있습니다.")


def _ai_unavailable_error() -> HTTPException:
    return HTTPException(status_code=503, detail="AI 답변을 현재 사용할 수 없습니다.")


def _generation_failed_error() -> HTTPException:
    return HTTPException(
        status_code=503,
        detail="AI 답변을 생성하지 못했습니다. 잠시 후 다시 시도해 주세요.",
    )


async def _answer_question(
    payload: QuestionRequest,
    request: Request,
    user: MockUser | None,
    budget: RequestBudget,
    repository: LegalRepository,
) -> QuestionResponse:
    """근거 우선 질문 답변 흐름을 라우팅·검색·생성 예산 안에서 실행한다.

    정상 법령 경로의 생성 실패·grounding 거부는 기존 검색 전용 fallback 계약을 따른다.
    라우터 불가 경로는 검색을 시작하지 않고 항상 AI-mode의 빈 unanswerable 응답으로 끝난다.
    """
    if payload.answer_mode == "search_only" and not settings.search_only_enabled:
        raise _search_only_disabled_error()
    if not _ai_available() and not settings.search_only_enabled:
        await _require_supported_as_of_date(payload.as_of_date, repository)
        raise _ai_unavailable_error()

    use_ai = payload.answer_mode == "terra" and _ai_available()
    if not use_ai:
        await _require_supported_as_of_date(payload.as_of_date, repository)
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
        "evidence_source_validation": {"attempted": False, "status": "not_attempted"},
        "answer_generation": {"attempted": False, "status": "not_attempted"},
        "answer_validation": {"attempted": False, "status": "not_attempted"},
        "routing": {"attempted": False, "status": "not_attempted"},
        "clarification_generation": {"attempted": False, "status": "not_attempted"},
        "required_source_guidance_generation": {
            "attempted": False,
            "status": "not_attempted",
        },
        "blocked_answer_generation": {"attempted": False, "status": "not_attempted"},
        "blocked_response_validation": {"attempted": False, "status": "not_attempted"},
        "outcome": {},
    }
    await _check_quota("ai" if use_ai else "search", user=user)
    await asyncio.sleep(0)
    # Routing applies only to Terra requests. Search-only requests intentionally retain
    # their existing direct retrieval contract.
    route_decision: RouteDecision | None = None
    if use_ai:
        routing_stage = diagnostics["routing"]
        assert isinstance(routing_stage, dict)
        routing_stage.update({"attempted": True, "status": "started"})
        routing_started = time.monotonic()
        routing_outcome: QuestionStageTimingOutcome = "failed"
        routing_timed_out = False
        try:
            route_decision = await budget.run(
                "routing",
                lambda: route_question(payload.question, _question_router()),
                cap_seconds=settings.route_classifier_timeout_seconds,
            )
            routing_outcome = "succeeded"
        except StageTimeoutError:
            routing_timed_out = True
            routing_outcome = "timed_out"
            route_decision = RouteDecision(
                route="routing_unavailable",
                reason_code="routing_timeout",
                confidence=0.0,
            )
        except Exception:
            routing_outcome = "failed"
            route_decision = RouteDecision(
                route="routing_unavailable",
                reason_code="routing_provider_error",
                confidence=0.0,
            )
        finally:
            emit_question_stage_timing(
                str(payload.client_request_id),
                "routing",
                routing_outcome,
                _elapsed_ms(routing_started),
                _remaining_ms(budget),
            )
        assert route_decision is not None
        real_explanation = (
            route_decision.explanation if route_decision.route != "routing_unavailable" else None
        )
        routing_stage.update(
            {
                "status": (
                    "timed_out"
                    if routing_timed_out
                    else "failed"
                    if routing_outcome == "failed"
                    else "resolved"
                ),
                "route": route_decision.route,
                "reason_code": route_decision.reason_code,
                "confidence": route_decision.confidence,
            }
        )
        emit_route_outcome(str(payload.client_request_id), route_decision)
        if route_decision.route != "legal_search":
            guidance_stage: Literal[
                "clarification_generation",
                "required_source_guidance_generation",
                "blocked_answer_generation",
            ] = (
                "blocked_answer_generation"
                if route_decision.route == "routing_unavailable"
                else "clarification_generation"
                if route_decision.route == "clarification_required"
                else "required_source_guidance_generation"
            )
            blocked_fallback = route_guidance_fallback(
                payload,
                route_decision.route,
                missing_fields=route_decision.missing_fields,
                explanation=real_explanation,
            )
            blocked_fallback.request_id = str(payload.client_request_id)
            route_answer = await _generate_blocked_answer(
                payload,
                route_decision,
                real_explanation,
                blocked_fallback,
                diagnostics,
                budget,
                stage_name=guidance_stage,
            )
            return await _save_if_authenticated(user, payload, route_answer, diagnostics)
        await _require_supported_as_of_date(payload.as_of_date, repository)
    query_embedding = None
    embedding_failed = False
    if use_ai and settings.embedding_enabled:
        embedding_stage = diagnostics["embedding"]
        assert isinstance(embedding_stage, dict)
        embedding_stage.update({"attempted": True, "status": "started"})
        embedding_started = time.monotonic()
        # 성공을 명시적으로 표시한다 - 기본값이 "succeeded"면 asyncio.CancelledError가
        # stage를 죽여도 finally가 잘못된 "succeeded"를 로깅해버린다(Finding 2).
        embedding_outcome: QuestionStageTimingOutcome = "failed"
        try:
            query_embedding = (
                await budget.run(
                    "embedding",
                    lambda: _embedder().embed([payload.question]),
                    cap_seconds=settings.question_embedding_timeout_seconds,
                )
            )[0]
            embedding_outcome = "succeeded"
            embedding_stage.update({"status": "succeeded", "dimensions": len(query_embedding)})
        except StageTimeoutError:
            embedding_failed = True
            embedding_outcome = "timed_out"
            embedding_stage.update({"status": "timed_out", "dimensions": None})
        except Exception:
            embedding_failed = True
            embedding_outcome = "failed"
            embedding_stage.update({"status": "failed", "dimensions": None})
        finally:
            emit_question_stage_timing(
                str(payload.client_request_id),
                "embedding",
                embedding_outcome,
                _elapsed_ms(embedding_started),
                _remaining_ms(budget),
            )
    elif use_ai:
        embedding_stage = diagnostics["embedding"]
        assert isinstance(embedding_stage, dict)
        embedding_stage.update({"attempted": False, "status": "skipped_provider_unavailable"})
    retrieval_started = time.monotonic()
    # 성공을 명시적으로 표시한다 - 기본값이 "succeeded"면 asyncio.CancelledError가
    # stage를 죽여도 finally가 잘못된 "succeeded"를 로깅해버린다(Finding 2).
    retrieval_outcome: QuestionStageTimingOutcome = "failed"
    try:
        hits, search_trace, corpus_as_of = await budget.run(
            "retrieval",
            lambda: _retrieve_question_evidence(payload, query_embedding, repository),
            cap_seconds=settings.retrieval_timeout_seconds,
        )
        retrieval_outcome = "succeeded"
    except StageTimeoutError as exc:
        # 검색 stage 예산을 다 썼다 - 아직 신뢰할 근거가 없으므로(부분 결과로 답을
        # 만들지 않는다) 재시도를 유도하는 고정 503 메시지로 끝낸다. corpus 미준비·일반
        # 검색 실패와는 원인이 다르므로 별도 분기로 유지한다.
        retrieval_outcome = "timed_out"
        raise HTTPException(
            status_code=503,
            detail="법령 검색 시간이 초과되었습니다. 잠시 후 다시 시도해 주세요.",
        ) from exc
    except CorpusSearchUnavailableError as exc:
        retrieval_outcome = "failed"
        raise _corpus_unready_http_error() from exc
    except Exception as exc:
        retrieval_outcome = "failed"
        raise HTTPException(
            status_code=503,
            detail="법령 검색을 일시적으로 사용할 수 없습니다.",
        ) from exc
    finally:
        emit_question_stage_timing(
            str(payload.client_request_id),
            "retrieval",
            retrieval_outcome,
            _elapsed_ms(retrieval_started),
            _remaining_ms(budget),
        )
    original_hit_count = len(hits)
    hits = [hit for hit in hits if is_allowed_source_url(hit.source_url)]
    source_validation_stage = diagnostics["evidence_source_validation"]
    assert isinstance(source_validation_stage, dict)
    source_validation_stage.update(
        {
            "attempted": True,
            "status": "succeeded",
            "input_count": original_hit_count,
            "allowed_count": len(hits),
        }
    )
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
    if use_ai and not hits:
        fallback_reason = (
            AiFallbackReason.EMBEDDING_ERROR if embedding_failed else AiFallbackReason.NO_EVIDENCE
        )
    fallback = search_only_answer(payload, hits, corpus_as_of, fallback_reason=fallback_reason)
    fallback.request_id = str(payload.client_request_id)
    if route_decision is not None:
        fallback.route = route_decision.route
    if not use_ai:
        generation_stage = diagnostics["answer_generation"]
        assert isinstance(generation_stage, dict)
        generation_stage["status"] = (
            "skipped_search_only"
            if payload.answer_mode == "search_only"
            else "skipped_ai_disabled"
        )
        return await _save_if_authenticated(user, payload, fallback, diagnostics)
    generation_stage = diagnostics["answer_generation"]
    assert isinstance(generation_stage, dict)
    generation_hits = select_generation_hits(hits, settings.answer_evidence_max_characters)
    generation_stage.update(
        {
            "attempted": True,
            "status": "started",
            "retrieved_evidence_count": len(hits),
            "selected_evidence_count": len(generation_hits),
            "dropped_evidence_count": len(hits) - len(generation_hits),
            "selected_evidence_characters": sum(len(hit.content) for hit in generation_hits),
            # 0025 M5 item 4: 어떤 model/prompt/schema/context/sampling 조합이 이 답변을
            # 만들었는지 SHA로 남긴다. 생성 경로는 NVIDIA NIM 하나로 고정돼 있다.
            # 0043, 2026-08-10: _answerer()가 build_messages_v2를 기본으로 쓰도록 전환하며
            # 이 프로필 참조도 V2로 맞췄다 - 프로필과 message_builder가 항상 짝을 이뤄야
            # generation_profile_sha256가 실제 생성에 쓰인 프롬프트를 정확히 가리킨다.
            "generation_profile_key": NVIDIA_NEMOTRON_ULTRA_ANSWER_PROFILE_V2.key,
            "generation_profile_sha256": NVIDIA_NEMOTRON_ULTRA_ANSWER_PROFILE_V2.sha256,
        }
    )
    generation_started = time.monotonic()
    # 성공을 명시적으로 표시한다 - 기본값이 "succeeded"면 asyncio.CancelledError가
    # stage를 죽여도 finally가 잘못된 "succeeded"를 로깅해버린다(Finding 2).
    generation_outcome: QuestionStageTimingOutcome = "failed"
    try:
        draft = await budget.run(
            "answer_generation",
            lambda: _answerer().answer(payload, generation_hits),
            cap_seconds=settings.answer_timeout_seconds,
        )
        generation_outcome = "succeeded"
    except StageTimeoutError as exc:
        if not settings.search_only_enabled:
            raise _generation_failed_error() from exc
        # 생성 stage 예산을 다 썼다 - 이미 검증된 근거(fallback)가 있으니 에러가 아니라
        # 200 + search_only로 끝낸다. 웹 클라이언트 재시도 로직이 이 응답 모양에
        # 의존한다(에러 응답으로 바꾸면 안 된다).
        generation_outcome = "timed_out"
        fallback.fallback_reason = AiFallbackReason.GENERATION_ERROR
        generation_stage["status"] = "timed_out"
        return await _save_if_authenticated(user, payload, fallback, diagnostics)
    except Exception as exc:
        generation_outcome = "failed"
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
        if not settings.search_only_enabled:
            raise _generation_failed_error() from exc
        return await _save_if_authenticated(user, payload, fallback, diagnostics)
    finally:
        emit_question_stage_timing(
            str(payload.client_request_id),
            "answer_generation",
            generation_outcome,
            _elapsed_ms(generation_started),
            _remaining_ms(budget),
        )
    validation_stage = diagnostics["answer_validation"]
    assert isinstance(validation_stage, dict)
    validation_stage.update({"attempted": True, "status": "started"})
    validation_started = time.monotonic()
    draft_is_valid = validate_draft(draft, generation_hits)
    emit_question_stage_timing(
        str(payload.client_request_id),
        "answer_validation",
        "succeeded" if draft_is_valid else "failed",
        _elapsed_ms(validation_started),
        _remaining_ms(budget),
    )
    if not draft_is_valid:
        validation_stage["status"] = "succeeded" if draft_is_valid else "grounding_failed"
        if not settings.search_only_enabled:
            raise _generation_failed_error()
        fallback.fallback_reason = AiFallbackReason.GROUNDING_FAILED
        generation_stage["status"] = "grounding_failed"
        return await _save_if_authenticated(user, payload, fallback, diagnostics)
    validation_stage["status"] = "succeeded"
    # 2026-08-08: 모델이 스스로 판단한 action이 checklist 기반 추정(derive_answer_action)과
    # 얼마나 일치하는지 diagnostics에 남긴다 - 라우터 설명을 저장하던 것과 같은 이유로,
    # D-10 표본 검토 때 이 자기보고 신호를 신뢰해도 되는지 나중에 확인하기 위해서다.
    generation_stage["model_action"] = draft.action
    generation_stage["checklist_derived_action"] = derive_answer_action(draft.checklist)
    generation_stage["action_agrees_with_checklist"] = draft.action == generation_stage[
        "checklist_derived_action"
    ]
    if draft.action == "clarification_required":
        clarification = post_generation_clarification_answer(
            payload,
            draft.missing_information,
            mode="search_only" if settings.search_only_enabled else "ai",
        )
        generation_stage["status"] = "clarification_required"
        return await _save_if_authenticated(user, payload, clarification, diagnostics)
    citations = [
        Citation(
            id=f"C{index}",
            provision_id=hit.provision_id,
            document_title=hit.document_title,
            version_label=hit.version_label,
            path=hit.path,
            quote=hit.content,
            source_url=hit.source_url,
            source_kind=hit.source_kind,
            law_type_code=hit.law_type_code,
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
        action=draft.action,
        route=route_decision.route if route_decision is not None else None,
    )
    generation_stage["status"] = "succeeded"
    return await _save_if_authenticated(user, payload, answer, diagnostics)


async def _generate_blocked_answer(
    payload: QuestionRequest,
    route_decision: RouteDecision,
    explanation: str | None,
    blocked_fallback: QuestionResponse,
    diagnostics: dict[str, object],
    budget: RequestBudget,
    *,
    stage_name: Literal[
        "clarification_generation",
        "required_source_guidance_generation",
        "blocked_answer_generation",
    ],
) -> QuestionResponse:
    """Generate guidance for a route that intentionally does not search."""
    if route_decision.route == "routing_unavailable" and stage_name != "blocked_answer_generation":
        raise ValueError("routing_unavailable requires blocked_answer_generation")
    if route_decision.route != "routing_unavailable" and stage_name == "blocked_answer_generation":
        raise ValueError("blocked_answer_generation is reserved for routing_unavailable")
    stage = diagnostics[stage_name]
    assert isinstance(stage, dict)
    stage.update({"attempted": True, "status": "started"})
    started = time.monotonic()
    outcome: QuestionStageTimingOutcome = "failed"
    try:
        draft = await budget.run(
            stage_name,
            lambda: _answerer().answer_blocked_route(
                payload, route_decision.route, explanation
            ),
            cap_seconds=settings.answer_timeout_seconds,
        )
        outcome = "succeeded"
    except StageTimeoutError:
        outcome = "timed_out"
        stage["status"] = "timed_out"
        return blocked_fallback
    except Exception as exc:
        outcome = "failed"
        status_code = getattr(exc, "status_code", None)
        if status_code in {402, 429}:
            global ai_quota_exhausted
            ai_quota_exhausted = True
        stage["status"] = "billing_or_quota_error" if status_code in {402, 429} else "failed"
        return blocked_fallback
    finally:
        emit_question_stage_timing(
            str(payload.client_request_id),
            stage_name,
            outcome,
            _elapsed_ms(started),
            _remaining_ms(budget),
        )
    if route_decision.route == "routing_unavailable":
        validation_stage = diagnostics["blocked_response_validation"]
        assert isinstance(validation_stage, dict)
        validation_stage.update({"attempted": True, "status": "started"})
        valid = _validate_blocked_response(draft)
        validation_stage["status"] = "succeeded" if valid else "failed"
        if not valid:
            stage["status"] = "blocked_response_validation_failed"
            return blocked_fallback
        stage["status"] = "succeeded"
        return QuestionResponse(
            request_id=str(payload.client_request_id),
            mode="ai",
            summary=draft.summary,
            scope="라우팅 분류 일시 중단 (검색 미실행)",
            sections=[],
            checklist=[],
            citations=[],
            limitations=["질문 분류를 완료하지 못해 법령 검색을 시작하지 않았습니다."],
            requested_answer_mode=payload.answer_mode,
            action="unanswerable",
            route="routing_unavailable",
        )
    if not validate_draft(draft, []):
        stage["status"] = "validation_failed"
        return blocked_fallback
    stage["status"] = "succeeded"
    if draft.action == "clarification_required":
        summary = clarification_resubmission_summary(payload.question, draft.missing_information)
    else:
        summary = draft.summary
    return QuestionResponse(
        request_id=str(payload.client_request_id),
        mode="ai",
        summary=summary,
        scope=f"라우팅: {route_decision.route} (검색 미실행)",
        sections=[],
        checklist=[],
        citations=[],
        limitations=[*draft.limitations, "이 서비스는 법률 자문을 대체하지 않습니다."],
        requested_answer_mode=payload.answer_mode,
        action=draft.action,
        route=route_decision.route,
    )


def _validate_blocked_response(draft: DraftAnswer) -> bool:
    """Accept only an empty, explicitly unanswerable unavailable-route draft."""
    return draft.action == "unanswerable" and not draft.sections and not draft.checklist


@app.post("/v1/auth/mock/google", response_model=MockLoginResponse)
async def mock_google_login(payload: MockGoogleLoginRequest) -> MockLoginResponse:
    """비운영 환경에서 목업 Google 로그인 세션을 발급한다."""
    _require_mock_auth()
    token, user = identity_repository.login_google(payload.email, payload.display_name)
    return MockLoginResponse(access_token=token, user=user)


@app.get("/v1/auth/me", response_model=MockUser)
async def current_user(
    user: Annotated[MockUser, Depends(_authenticated_user)],
) -> MockUser:
    """현재 인증된 사용자를 반환한다."""
    return user


@app.post("/v1/auth/logout", status_code=204)
async def logout(authorization: Annotated[str | None, Header()] = None) -> Response:
    """현재 인증 세션을 검증하고 목업 세션을 종료한다."""
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
    """인증된 사용자의 계정과 연결된 데이터를 삭제한다."""
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
    """인증된 사용자가 소유한 질문 이력을 반환한다."""
    if postgres_identity:
        return await postgres_identity.list_history(user.id)
    return identity_repository.list_history(user.id)


@app.get("/v1/conversations", response_model=ConversationPage)
async def conversations(
    user: Annotated[MockUser, Depends(_authenticated_user)],
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
    cursor: str | None = None,
) -> ConversationPage:
    """인증된 사용자의 대화를 페이지 단위로 반환한다."""
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
    """인증된 사용자가 소유한 대화의 턴을 페이지 단위로 반환한다."""
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
    """인증된 사용자가 소유한 대화와 포함된 턴을 삭제한다."""
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
    """인증된 사용자가 소유한 질문 이력 항목을 반환한다."""
    return await _owned_history(history_id, user)


@app.delete("/v1/questions/history/{history_id}", status_code=204)
async def delete_question_history(
    history_id: UUID, user: Annotated[MockUser, Depends(_authenticated_user)]
) -> Response:
    """인증된 사용자가 소유한 질문 이력 항목을 삭제한다."""
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
    """인증된 사용자의 질문 이력에서 체크리스트 파일을 내보낸다."""
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
    """검증된 기준일에 유효한 단일 법령 조문을 반환한다."""
    requested_date = as_of_date or _current_korea_date()
    await _require_supported_as_of_date(requested_date, repository)
    try:
        hit = await repository.provision(provision_id, requested_date)
    except CorpusSearchUnavailableError as exc:
        raise _corpus_unready_http_error() from exc
    if hit is None or not is_allowed_source_url(hit.source_url):
        raise HTTPException(status_code=404, detail="조문을 찾을 수 없습니다")
    return ProvisionResponse(hit=hit)


@app.get("/v1/documents/{document_id}/changes", response_model=DocumentChangesResponse)
async def changes(document_id: UUID, from_date: date, to_date: date) -> DocumentChangesResponse:
    """문서 연혁 비교의 현재 지원 상태를 반환한다."""
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
    """검색 가능 corpus와 AI 가용성 상태를 반환한다."""
    if isinstance(repository, PostgresLegalRepository):
        items, temporal_state, last_successful_sync = await repository.corpus_overview(
            _current_korea_date()
        )
    else:
        items = await repository.corpus_items()
        temporal_state = await _load_corpus_temporal_state(repository)
        last_successful_sync = await repository.last_sync()
    warnings = []
    if not temporal_state.ready:
        warnings.append("법령 corpus를 갱신·검증하는 동안 검색이 일시 중지되었습니다.")
    if any(item.state != "ready" for item in items):
        warnings.append("MVP 허용 목록 일부가 아직 수집되지 않았습니다.")
    if not _ai_available():
        warnings.append(
            "AI가 비활성화되어 검색 전용 모드로 동작합니다."
            if settings.search_only_enabled
            else "AI가 비활성화되어 답변을 생성할 수 없습니다."
        )
    if collector_load_errors:
        warnings.append(f"collector 목업 원문 {len(collector_load_errors)}건을 읽지 못했습니다.")
    return CorpusStatus(
        last_successful_sync=last_successful_sync,
        corpus_snapshot_id=temporal_state.corpus_snapshot_id,
        supported_as_of_from=temporal_state.supported_as_of_from,
        supported_as_of_through=temporal_state.supported_as_of_through,
        corpus_search_ready=temporal_state.ready,
        corpus_search_unavailable_reason=temporal_state.reason,
        ai_available=_ai_available(),
        ai_unavailable_reason=_ai_unavailable_reason(),
        items=items,
        warnings=warnings,
    )


def _corpus_unready_http_error() -> HTTPException:
    return HTTPException(
        status_code=503,
        detail={
            "code": "corpus_unready",
            "message": "법령 corpus를 갱신·검증하는 동안 검색이 일시 중지되었습니다.",
        },
    )


def _current_korea_date() -> date:
    return korea_today()


async def _load_corpus_temporal_state(repository: LegalRepository) -> CorpusTemporalState:
    try:
        return await repository.corpus_temporal_state(_current_korea_date())
    except Exception as exc:
        raise _corpus_unready_http_error() from exc


async def _require_supported_as_of_date(
    requested_date: date, repository: LegalRepository
) -> None:
    state = await _load_corpus_temporal_state(repository)
    if not state.ready:
        raise _corpus_unready_http_error()
    try:
        require_supported_corpus_date(requested_date, state)
    except UnsupportedCorpusDateError as exc:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "unsupported_corpus_date",
                "message": "현재 corpus는 검증된 기준일 범위 안에서만 검색할 수 있습니다.",
                "requested_as_of_date": exc.requested_date.isoformat(),
                "supported_from": exc.supported_from.isoformat(),
                "supported_through": exc.supported_through.isoformat(),
                "corpus_snapshot_id": exc.snapshot_id,
            },
        ) from exc


def _embedder() -> NvidiaNimEmbedder:
    return NvidiaNimEmbedder(
        api_key=settings.nvidia_api_key or "",
        base_url=settings.nvidia_base_url,
        model=settings.nvidia_embedding_model,
        dimensions=settings.embedding_dimensions,
        timeout_seconds=settings.embedding_timeout_seconds,
    )


async def _check_quota(kind: str, *, user: MockUser | None = None) -> None:
    if user is None or not postgres_identity or not settings.account_quota_enabled:
        return
    account_limit = (
        settings.authenticated_ai_daily_limit
        if kind == "ai"
        else settings.authenticated_search_daily_limit
    )
    if not await postgres_identity.consume_quota(user.id, date.today(), kind, account_limit):
        raise HTTPException(status_code=429, detail="오늘의 계정 사용 한도를 초과했습니다.")


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
    return "anonymous:" + daily_subject_hash(subject, settings.rate_limit_secret, date.today())


def _answerer() -> NvidiaNimAnswerer:
    # 2026-08-09: OpenAI 생성 분기와 어댑터는 운영 비교·fallback으로 사용하지 않기로 한
    # 결정을 코드에도 반영해 비활성화했다. 복구가 필요하면 Git 이력에서 별도 결정으로 되살린다.
    # 2026-08-10 (0043): hosted v1/v2 비교(experiment-0043-v1-v2-compare-results.json)에서
    # v2가 근거 없는 주장을 추가하지 않으면서(action 판정 v1=v2) 안내문 문체·행동형
    # 체크리스트로 더 나은 결과를 보여 기본 경로를 v2로 전환했다.
    return NvidiaNimAnswerer(
        api_key=settings.nvidia_api_key or "",
        base_url=settings.nvidia_base_url,
        model=settings.nvidia_answer_model,
        timeout_seconds=settings.answer_timeout_seconds,
        max_output_tokens=settings.answer_max_output_tokens,
        max_attempts=settings.answer_generation_max_attempts,
        message_builder=build_messages_v2,
    )


def _question_router() -> NvidiaNimQuestionRouter:
    return NvidiaNimQuestionRouter(
        api_key=settings.nvidia_api_key or "",
        base_url=settings.nvidia_base_url,
        model=settings.nvidia_route_classifier_model,
        timeout_seconds=settings.route_classifier_timeout_seconds,
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
    emit_question_outcome(
        response.request_id, response.mode, fallback_reason=response.fallback_reason
    )
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
