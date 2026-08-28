"""법령 RAG API와 v2 LlamaIndex 검색 경계를 제공한다."""

import asyncio
import base64
import hashlib
import json
import re
import time
from contextlib import asynccontextmanager
from datetime import UTC, date, datetime, timedelta
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
from law_rag_llamaindex.retriever import search_index as llamaindex_search_index
from law_rag_llamaindex.store import build_generation_vector_store
from llama_index.core import VectorStoreIndex
from sqlalchemy import create_engine, text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from app.adapters.capacity_leases import (
    MemoryConcurrencyLimiter,
    PostgresCapacityLeaseStore,
    PostgresConcurrencyLimiter,
)
from app.adapters.llamaindex_repository import LlamaIndexLegalRepository
from app.adapters.memory_question_execution import MemoryQuestionExecutionRepository
from app.adapters.memory_repository import repository as memory_repository
from app.adapters.mock_identity import identity_repository
from app.adapters.nvidia_nim_answerer import NvidiaNimAnswerer
from app.adapters.nvidia_nim_embedder import NvidiaNimEmbedder
from app.adapters.nvidia_nim_route_classifier import NvidiaNimQuestionRouter
from app.adapters.openai_answerer import (
    CoreDraft,
    DraftAnswer,
    build_messages_v2,
    select_generation_hits,
    validate_core_draft,
    validate_draft,
)
from app.adapters.postgres_identity import ConsentRequiredError, PostgresIdentityRepository
from app.adapters.postgres_question_execution import PostgresQuestionExecutionRepository
from app.adapters.postgres_repository import PostgresLegalRepository
from app.adapters.supabase_auth import (
    SupabaseAuth,
    SupabaseAuthError,
    SupabaseAuthUnavailableError,
)
from app.api.routes import ApiEndpoints, register_routes
from app.application.answering import (
    clarification_resubmission_summary,
    post_generation_clarification_answer,
    route_guidance_fallback,
    search_only_answer,
)
from app.application.checklist_exports import render_csv, render_markdown, render_pdf
from app.application.question_phase_coordinator import PhaseResult, QuestionPhaseCoordinator
from app.application.question_tasks import QuestionTaskRegistry
from app.application.request_budget import RequestBudget, StageTimeoutError
from app.domain.answer_actions import derive_answer_action
from app.domain.answer_events import AnswerEvent
from app.domain.auth_schemas import MockGoogleLoginRequest, MockLoginResponse
from app.domain.corpus_temporal_contract import (
    UnsupportedCorpusDateError,
    korea_today,
    require_supported_corpus_date,
)
from app.domain.embedding_profiles import NVIDIA_NEMOTRON_512_PROFILE
from app.domain.errors import CorpusSearchUnavailableError
from app.domain.generation_profiles import NVIDIA_NEMOTRON_ULTRA_ANSWER_PROFILE_V2
from app.domain.grounding import CitationRegistry, FrozenCitation, GroundedSentence
from app.domain.pipeline_issues import ExecutionPhase
from app.domain.privacy import anonymous_rate_limit_subject, daily_subject_hash
from app.domain.question_execution import ExecutionSnapshot, ExecutionStatus, next_action_for
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
    emit_execution_phase,
    emit_question_outcome,
    emit_question_stage_timing,
    emit_route_outcome,
)
from app.ports.question_execution import ExecutionConflict, ExecutionNotFound, SystemBusy
from app.settings import get_settings

settings = get_settings()
ai_quota_exhausted = False
question_tasks = QuestionTaskRegistry()
repository = (
    PostgresLegalRepository(settings.database_url) if settings.database_url else memory_repository
)
question_execution_repository = (
    PostgresQuestionExecutionRepository(repository.engine)
    if isinstance(repository, PostgresLegalRepository)
    else MemoryQuestionExecutionRepository()
)
question_phase_limiter = (
    PostgresConcurrencyLimiter(
        provider="ultra",
        slots=settings.v2_provider_slots,
        lease_store=PostgresCapacityLeaseStore(repository.engine),
    )
    if isinstance(repository, PostgresLegalRepository)
    else MemoryConcurrencyLimiter(provider="ultra", slots=settings.v2_provider_slots)
)
question_phase_tasks: dict[UUID, asyncio.Task[object]] = {}
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
    async_engine = create_async_engine(
        _llamaindex_async_database_url(database_url), poolclass=NullPool
    )
    sync_engine = create_engine(_llamaindex_sync_database_url(database_url), poolclass=NullPool)

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
    allow_headers=[
        "Authorization",
        "Content-Type",
        "Idempotency-Key",
        "X-Execution-Capability",
        "X-Terms-Version",
        "X-Privacy-Version",
    ],
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


async def health() -> dict[str, str]:
    """서비스 상태를 반환한다."""
    return {"status": "ok"}


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
            pinned = await active()
        except Exception:
            raise _v2_not_ready_http_error() from None
        hits = await llamaindex_search_index(
            pinned.index, payload.query, payload.as_of_date, payload.limit
        )
    else:
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


async def question(payload: QuestionRequest, request: Request) -> QuestionResponse:
    """v1 검색 저장소로 법령 질문에 응답한다."""
    return await _handle_question(payload, request, repository)


async def _v2_repository() -> LegalRepository:
    resources = _llamaindex_resources()
    if resources is None:
        raise _v2_not_ready_http_error()
    _, _, v2_repository = resources
    if v2_repository is None:
        raise _v2_not_ready_http_error()
    if not await _v2_ready():
        raise _v2_not_ready_http_error()
    return v2_repository


def _sse(event_type: str, payload: dict[str, object]) -> bytes:
    return f"event: {event_type}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n".encode()


async def prepare_question_execution(
    payload: QuestionRequest,
    request: Request,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=1)],
) -> dict[str, object]:
    """Freeze the active generation and evidence before any provider phase starts."""
    user = await _optional_user(request.headers.get("authorization"))
    owner_scope = _question_owner(request, user)
    await question_execution_repository.expire(datetime.now(UTC))
    existing = await question_execution_repository.find_by_prepare_key(owner_scope, idempotency_key)
    if existing is not None:
        return _prepared_execution_response(
            existing,
            execution_capability=(
                _execution_capability(owner_scope, idempotency_key) if user is None else None
            ),
        )
    v2_repository = await _v2_repository()
    await _check_quota("ai" if payload.answer_mode == "terra" else "search", user=user)
    await _require_supported_as_of_date(payload.as_of_date, v2_repository)
    route = "legal_search"
    missing_fields: tuple[str, ...] = ()
    if payload.answer_mode == "terra":
        try:
            decision = await route_question(payload.question, _question_router())
            route = decision.route
            missing_fields = decision.missing_fields
        except Exception:
            route = "routing_unavailable"
    resources = _llamaindex_resources()
    assert resources is not None
    active = await resources[0].active()
    hits, corpus_as_of = (
        await _retrieve_pinned_v2_evidence(payload, active, v2_repository)
        if route == "legal_search"
        else ([], None)
    )
    generation_hits = (
        select_generation_hits(hits, settings.answer_evidence_max_characters)
        if route == "legal_search" and payload.answer_mode == "terra"
        else hits
    )
    frozen_citations = tuple(
        FrozenCitation(id=f"C{index}", quote=hit.content)
        for index, hit in enumerate(generation_hits, 1)
    )
    execution_capability = (
        _execution_capability(owner_scope, idempotency_key) if user is None else None
    )
    execution = await question_execution_repository.prepare_or_get(
        owner_scope=owner_scope,
        prepare_idempotency_key=idempotency_key,
        generation_id=active.generation.id,
        capability_hash=_capability_hash(execution_capability),
        private_payload={
            "request": payload.model_dump(mode="json"),
            "hits": [hit.model_dump(mode="json") for hit in hits],
            "generation_hits": [hit.model_dump(mode="json") for hit in generation_hits],
            "corpus_as_of": corpus_as_of.isoformat() if corpus_as_of is not None else None,
            "route": route,
            "missing_fields": list(missing_fields),
        },
        frozen_citations=frozen_citations,
        expires_at=datetime.now(UTC) + timedelta(minutes=10),
    )
    emit_execution_phase(str(execution.execution_id), "prepare", "prepared")
    return _prepared_execution_response(execution, execution_capability=execution_capability)


def _prepared_execution_response(
    execution, *, execution_capability: str | None = None
) -> dict[str, object]:
    next_action = next_action_for(
        ExecutionSnapshot(status=execution.status, version=execution.version)
    )
    response: dict[str, object] = {
        "execution_id": str(execution.execution_id),
        "status": execution.status.value,
        "next_action": next_action.value if next_action else "complete",
    }
    if execution_capability is not None:
        response["execution_capability"] = execution_capability
    return response


def _capability_hash(value: str | None) -> str | None:
    return hashlib.sha256(value.encode("utf-8")).hexdigest() if value else None


def _execution_capability(owner_scope: str, idempotency_key: str) -> str:
    """Replay the same opaque anonymous capability without storing plaintext."""
    material = f"{owner_scope}\x00{idempotency_key}".encode()
    return hashlib.sha256(settings.rate_limit_secret.encode() + material).hexdigest()


async def _retrieve_pinned_v2_evidence(
    payload: QuestionRequest, active, v2_repository: LegalRepository
):
    """Search the same index whose generation ID is persisted on the execution."""
    hits = await llamaindex_search_index(active.index, payload.question, payload.as_of_date, 10)
    return hits, await v2_repository.last_sync()


async def _stream_execution_phase(
    execution_id: UUID,
    request: Request,
    phase: Literal["core", "finalize"],
    execution_capability: str | None,
):
    user = await _optional_user(request.headers.get("authorization"))
    owner_scope = _question_owner(request, user)
    capability_hash = _capability_hash(execution_capability) if user is None else None
    await question_execution_repository.expire(datetime.now(UTC))
    try:
        execution = await question_execution_repository.get_owned(
            execution_id, owner_scope, capability_hash=capability_hash
        )
    except ExecutionNotFound as exc:
        raise HTTPException(status_code=404, detail="질문 실행을 찾을 수 없습니다.") from exc
    if execution.status is ExecutionStatus.EXPIRED:
        raise HTTPException(status_code=404, detail="질문 실행을 찾을 수 없습니다.")
    coordinator = QuestionPhaseCoordinator(
        question_execution_repository,
        core=lambda execution: _run_v2_core(execution),
        finalize=lambda execution: _run_v2_finalize(execution, user),
        phase_timeout=timedelta(seconds=settings.v2_phase_timeout_seconds),
    )
    existing = question_phase_tasks.get(execution_id)
    owns_task = existing is None or existing.done()
    start_gate = asyncio.Event()

    async def run_after_admission():
        await start_gate.wait()
        return await coordinator.run(
            execution_id,
            owner_scope,
            phase=phase,
            capability_hash=capability_hash,
        )

    task = asyncio.create_task(run_after_admission()) if owns_task else existing
    assert task is not None
    if owns_task:
        question_phase_tasks[execution_id] = task
    try:
        lease = await _admit_v2_provider_phase(execution, phase) if owns_task else None
    except BaseException:
        if owns_task and question_phase_tasks.get(execution_id) is task:
            del question_phase_tasks[execution_id]
        task.cancel()
        raise

    async def release_when_done() -> None:
        if owns_task and question_phase_tasks.get(execution_id) is task:
            del question_phase_tasks[execution_id]
        if owns_task and lease is not None:
            await lease.release()

    def schedule_release(_completed_task) -> None:
        asyncio.create_task(release_when_done())

    if owns_task:
        task.add_done_callback(schedule_release)
        start_gate.set()

    async def events():
        try:
            persisted = await asyncio.shield(task)
        except asyncio.CancelledError:
            if not task.cancelled() and owns_task:
                raise
            if not task.cancelled():
                raise
            persisted = (AnswerEvent.cancelled(),)
        except (ExecutionConflict, ValueError):
            persisted = (AnswerEvent.error("phase_not_ready"),)
        except ExecutionNotFound:
            persisted = (AnswerEvent.error("execution_not_found"),)
        for event in persisted:
            yield _sse(event.event_type, dict(event.payload))

    return StreamingResponse(events(), media_type="text/event-stream")


async def _admit_v2_provider_phase(execution, phase: Literal["core", "finalize"]):
    """Reject provider work before SSE starts; deterministic search-only phases need no slot."""
    request_data = execution.private_payload.get("request")
    if not isinstance(request_data, dict):
        return None
    request_payload = QuestionRequest.model_validate(request_data)
    will_start = (
        (phase == "core" and execution.status is ExecutionStatus.PREPARED)
        or (
            phase == "finalize"
            and execution.status
            in {ExecutionStatus.CORE_ANSWERED, ExecutionStatus.CORE_REPAIR_REQUIRED}
        )
    )
    if not will_start or request_payload.answer_mode != "terra":
        return None
    if phase == "finalize" and isinstance(
        execution.private_payload.get("verified_core_response"), dict
    ):
        return None
    if execution.private_payload.get("route", "legal_search") != "legal_search":
        return None
    try:
        return await question_phase_limiter.acquire(
            execution.execution_id,
            ExecutionPhase.CORE if phase == "core" else ExecutionPhase.FINALIZE,
            datetime.now(UTC) + timedelta(seconds=settings.v2_provider_budget_seconds),
        )
    except SystemBusy as exc:
        emit_execution_phase(str(execution.execution_id), phase, "busy")
        raise HTTPException(status_code=503, detail="system_busy") from exc


async def core_question_execution(
    execution_id: UUID,
    request: Request,
    execution_capability: Annotated[str | None, Header(alias="X-Execution-Capability")] = None,
) -> StreamingResponse:
    return await _stream_execution_phase(execution_id, request, "core", execution_capability)


async def finalize_question_execution(
    execution_id: UUID,
    request: Request,
    execution_capability: Annotated[str | None, Header(alias="X-Execution-Capability")] = None,
) -> StreamingResponse:
    return await _stream_execution_phase(execution_id, request, "finalize", execution_capability)


async def cancel_question_execution(
    execution_id: UUID,
    request: Request,
    execution_capability: Annotated[str | None, Header(alias="X-Execution-Capability")] = None,
) -> dict[str, bool]:
    user = await _optional_user(request.headers.get("authorization"))
    try:
        await question_execution_repository.cancel(
            execution_id,
            _question_owner(request, user),
            capability_hash=_capability_hash(execution_capability) if user is None else None,
        )
    except ExecutionNotFound as exc:
        raise HTTPException(status_code=404, detail="질문 실행을 찾을 수 없습니다.") from exc
    if task := question_phase_tasks.get(execution_id):
        task.cancel()
    return {"cancelled": True}


async def cancel_question(client_request_id: UUID, request: Request) -> dict[str, bool]:
    """같은 요청 소유자가 실행 중인 질문을 취소한다."""
    user = await _optional_user(request.headers.get("authorization"))
    if not await question_tasks.cancel(_question_owner(request, user), client_request_id):
        raise HTTPException(status_code=404, detail="처리 중인 질문을 찾을 수 없습니다.")
    return {"cancelled": True}


def _execution_request_and_hits(
    execution,
) -> tuple[QuestionRequest, list[SearchHit], datetime | None]:
    payload = execution.private_payload
    request_data = payload.get("request")
    hit_data = payload.get("hits")
    if not isinstance(request_data, dict) or not isinstance(hit_data, list):
        raise ValueError("execution payload is incomplete")
    corpus_as_of = payload.get("corpus_as_of")
    return (
        QuestionRequest.model_validate(request_data),
        [SearchHit.model_validate(item) for item in hit_data if isinstance(item, dict)],
        datetime.fromisoformat(corpus_as_of) if isinstance(corpus_as_of, str) else None,
    )


def _execution_generation_hits(execution, hits: list[SearchHit]) -> list[SearchHit]:
    stored = execution.private_payload.get("generation_hits")
    if isinstance(stored, list):
        return [SearchHit.model_validate(item) for item in stored if isinstance(item, dict)]
    return select_generation_hits(hits, settings.answer_evidence_max_characters)


async def _v2_response_from_frozen_evidence(execution) -> QuestionResponse:
    """Generate only from the execution's persisted evidence; never re-retrieve."""
    payload, hits, corpus_as_of = _execution_request_and_hits(execution)
    fallback = search_only_answer(payload, hits, corpus_as_of)
    fallback.request_id = str(payload.client_request_id)
    route = execution.private_payload.get("route", "legal_search")
    if route != "legal_search":
        missing_fields = execution.private_payload.get("missing_fields", [])
        return route_guidance_fallback(
            payload,
            str(route),
            missing_fields=tuple(item for item in missing_fields if isinstance(item, str))
            if isinstance(missing_fields, list)
            else (),
        )
    if payload.answer_mode != "terra" or not _ai_available():
        return fallback
    generation_hits = _execution_generation_hits(execution, hits)
    draft = await _answerer().answer(payload, generation_hits)
    if not validate_draft(draft, generation_hits):
        raise ValueError("generated answer did not satisfy the citation contract")
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
    return QuestionResponse(
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
        route="legal_search",
    )


async def _v2_core_from_frozen_evidence(execution) -> tuple[CoreDraft, list[Citation]]:
    """Generate the only client-visible core payload from frozen execution evidence."""
    payload, hits, corpus_as_of = _execution_request_and_hits(execution)
    fallback = search_only_answer(payload, hits, corpus_as_of)
    route = execution.private_payload.get("route", "legal_search")
    if route != "legal_search" or payload.answer_mode != "terra" or not _ai_available():
        return (
            CoreDraft(
                summary=fallback.summary,
                citation_ids=[citation.id for citation in fallback.citations],
                action=fallback.action or "unanswerable",
            ),
            fallback.citations,
        )
    generation_hits = _execution_generation_hits(execution, hits)
    draft = await _answerer().answer_core(payload, generation_hits)
    if not validate_core_draft(draft, generation_hits):
        raise ValueError("generated core did not satisfy the citation contract")
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
    return draft, citations


async def _run_v2_core(execution) -> PhaseResult:
    core, citations = await _v2_core_from_frozen_evidence(execution)
    if not _v2_core_is_grounded(core, CitationRegistry(execution.frozen_citations)):
        return PhaseResult(
            target=ExecutionStatus.CORE_REPAIR_REQUIRED,
            events=(
                AnswerEvent(
                    event_type="phase_complete",
                    payload={
                        "status": ExecutionStatus.CORE_REPAIR_REQUIRED.value,
                        "next_action": "repair_core",
                    },
                ),
            ),
        )
    core_data = core.model_dump(mode="json")
    return PhaseResult(
        target=ExecutionStatus.CORE_ANSWERED,
        events=(
            AnswerEvent(
                event_type="summary",
                payload={
                    "summary": core.summary,
                    "citations": [citation.model_dump(mode="json") for citation in citations],
                },
            ),
            AnswerEvent(
                event_type="phase_complete",
                payload={
                    "status": ExecutionStatus.CORE_ANSWERED.value,
                    "next_action": "generate_detail",
                },
            ),
        ),
        private_payload={
            "verified_core": core_data,
            "verified_core_citations": [citation.model_dump(mode="json") for citation in citations],
        },
    )


async def _run_v2_finalize(execution, user: MockUser | None) -> PhaseResult:
    payload, _hits, _corpus_as_of = _execution_request_and_hits(execution)
    stored_core = execution.private_payload.get("verified_core")
    core = CoreDraft.model_validate(stored_core) if isinstance(stored_core, dict) else None
    degraded = execution.status is ExecutionStatus.CORE_REPAIR_REQUIRED
    try:
        response = await _v2_response_from_frozen_evidence(execution)
    except Exception:
        response = _v2_core_degraded_response(payload, core, execution.private_payload)
        degraded = True
    if not _v2_response_is_grounded(response, CitationRegistry(execution.frozen_citations)):
        response = _v2_core_degraded_response(payload, core, execution.private_payload)
        degraded = True
    elif core is not None:
        response.summary = core.summary
        response.action = core.action
    response = await _save_if_authenticated(user, payload, response)
    response_data = response.model_dump(mode="json")
    outcome = "degraded" if degraded else "normal"
    return PhaseResult(
        target=ExecutionStatus.COMPLETED,
        response=response_data,
        events=(AnswerEvent.complete({"response": response_data, "outcome": outcome}),),
    )


def _v2_core_degraded_response(
    payload: QuestionRequest, core: CoreDraft | None, private_payload
) -> QuestionResponse:
    if core is None:
        return _v2_grounding_fallback(payload)
    raw_citations = private_payload.get("verified_core_citations", [])
    citations = [Citation.model_validate(item) for item in raw_citations if isinstance(item, dict)]
    return QuestionResponse(
        request_id=str(payload.client_request_id), mode="ai", summary=core.summary,
        scope="상세 설명 검증 실패", sections=[], checklist=[], citations=citations,
        limitations=["검증된 요약만 제공합니다.", "이 서비스는 법률 자문을 대체하지 않습니다."],
        requested_answer_mode=payload.answer_mode, action=core.action, route="legal_search",
    )


def _v2_response_is_grounded(response: QuestionResponse, registry: CitationRegistry) -> bool:
    if not response.citations:
        return not response.sections and not response.checklist
    all_citations = tuple(citation.id for citation in response.citations)
    if not _grounded_text(response.summary, all_citations, registry):
        return False
    for section in response.sections:
        citation_ids = tuple(section.citation_ids)
        if not _grounded_text(section.claim, citation_ids, registry):
            return False
        if not _grounded_text(section.explanation, citation_ids, registry):
            return False
    return all(
        _grounded_text(item.label, tuple(item.citation_ids), registry)
        for item in response.checklist
    )


def _v2_core_is_grounded(core: CoreDraft, registry: CitationRegistry) -> bool:
    if not core.citation_ids:
        return not registry.citations or core.action == "unanswerable"
    return _grounded_text(core.summary, tuple(core.citation_ids), registry)


def _grounded_text(text: str, citation_ids: tuple[str, ...], registry: CitationRegistry) -> bool:
    sentences = tuple(part.strip() for part in re.split(r"(?<=[.!?])\s+", text) if part.strip())
    return bool(sentences) and all(
        registry.verify(GroundedSentence(sentence, citation_ids)) for sentence in sentences
    )


def _v2_grounding_fallback(payload: QuestionRequest) -> QuestionResponse:
    """A legal-claim-free terminal response used only after failed repair."""
    return QuestionResponse(
        request_id=str(payload.client_request_id),
        mode="ai",
        summary="검증된 법률 주장을 만들지 못했습니다. 인용된 공식 원문을 직접 확인해 주세요.",
        scope="근거 검증 실패",
        sections=[],
        checklist=[],
        citations=[],
        limitations=["이 서비스는 법률 자문을 대체하지 않습니다."],
        result_status="no_results",
        requested_answer_mode=payload.answer_mode,
        action="unanswerable",
        route="legal_search",
    )


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


def _requires_legacy_query_embedding(search_repository: LegalRepository) -> bool:
    """Only v1 retrieval consumes the application-owned query embedding."""

    return not isinstance(search_repository, LlamaIndexLegalRepository)


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
    if use_ai and settings.embedding_enabled and _requires_legacy_query_embedding(repository):
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


async def mock_google_login(payload: MockGoogleLoginRequest) -> MockLoginResponse:
    """비운영 환경에서 목업 Google 로그인 세션을 발급한다."""
    _require_mock_auth()
    token, user = identity_repository.login_google(payload.email, payload.display_name)
    return MockLoginResponse(access_token=token, user=user)


async def current_user(
    user: Annotated[MockUser, Depends(_authenticated_user)],
) -> MockUser:
    """현재 인증된 사용자를 반환한다."""
    return user


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


async def question_history(
    user: Annotated[MockUser, Depends(_authenticated_user)],
) -> list[QuestionHistoryEntry]:
    """인증된 사용자가 소유한 질문 이력을 반환한다."""
    if postgres_identity:
        return await postgres_identity.list_history(user.id)
    return identity_repository.list_history(user.id)


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


async def question_history_detail(
    history_id: UUID, user: Annotated[MockUser, Depends(_authenticated_user)]
) -> QuestionHistoryEntry:
    """인증된 사용자가 소유한 질문 이력 항목을 반환한다."""
    return await _owned_history(history_id, user)


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


register_routes(
    app,
    ApiEndpoints(
        health=health,
        search=search,
        search_v2=search_v2,
        provision=provision,
        changes=changes,
        corpus_status=corpus_status,
        question=question,
        prepare_question_execution=prepare_question_execution,
        core_question_execution=core_question_execution,
        finalize_question_execution=finalize_question_execution,
        cancel_question_execution=cancel_question_execution,
        cancel_question=cancel_question,
        mock_google_login=mock_google_login,
        current_user=current_user,
        logout=logout,
        delete_account=delete_account,
        question_history=question_history,
        conversations=conversations,
        conversation_turns=conversation_turns,
        delete_conversation=delete_conversation,
        question_history_detail=question_history_detail,
        delete_question_history=delete_question_history,
        export_checklist=export_checklist,
    ),
)
