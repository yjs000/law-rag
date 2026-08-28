"""FastAPI composition entry point and backward-compatible test seams."""

from __future__ import annotations

from datetime import date
from functools import lru_cache
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from law_rag_core.ports.repository import LegalRepository
from law_rag_llamaindex.embedding import build_embedder as build_llamaindex_embedder
from law_rag_llamaindex.retriever import search as llamaindex_search
from law_rag_llamaindex.retriever import search_index as llamaindex_search_index
from sqlalchemy import text

from app.adapters.llamaindex_repository import LlamaIndexLegalRepository
from app.adapters.nvidia_nim_answerer import NvidiaNimAnswerer
from app.adapters.nvidia_nim_embedder import NvidiaNimEmbedder
from app.adapters.nvidia_nim_route_classifier import NvidiaNimQuestionRouter
from app.api.dependencies import (
    _authenticated_user,
    _optional_user,
    _save_if_authenticated,
)
from app.api.v1 import build_router as build_v1_router
from app.api.v1.questions import cancel_question, question
from app.api.v2 import build_router as build_v2_router
from app.api.v2.executions import (
    _capability_hash,
    _execution_capability,
    _retrieve_pinned_v2_evidence,
    _run_v2_core,
    _run_v2_finalize,
    _v2_active_provider,
    _v2_core_from_frozen_evidence,
    _v2_repository,
    _v2_response_from_frozen_evidence,
)
from app.api.v2.sse import _admit_v2_provider_phase, _sse, _stream_execution_phase
from app.application.question_tasks import QuestionTaskRegistry
from app.application.v1.answering import _answer_question
from app.application.v1.retrieval import (
    elapsed_ms as _elapsed_ms,
)
from app.application.v1.retrieval import (
    remaining_ms as _remaining_ms,
)
from app.application.v1.retrieval import (
    requires_legacy_query_embedding as _requires_legacy_query_embedding,
)
from app.application.v1.retrieval import (
    retrieve_question_evidence as _retrieve_question_evidence,
)
from app.bootstrap import (
    AppDependencies,
    V2ApplicationCallbacks,
    build_app_dependencies,
    build_llamaindex_resources,
    build_nvidia_answerer,
    build_nvidia_embedder,
    build_nvidia_question_router,
    build_v2_execution_dependencies,
    normalize_async_database_url,
    normalize_sync_database_url,
)
from app.domain.corpus_temporal_contract import (
    UnsupportedCorpusDateError,
    korea_today,
    require_supported_corpus_date,
)
from app.domain.privacy import anonymous_rate_limit_subject, daily_subject_hash
from app.domain.question_execution import ExecutionStatus
from app.domain.routing import route_question
from app.domain.schemas import CorpusTemporalState, MockUser, QuestionRequest
from app.settings import get_settings

_DEFAULT_LLAMAINDEX_EMBEDDER_FACTORY = build_llamaindex_embedder
_DEFAULT_LLAMAINDEX_REPOSITORY_FACTORY = LlamaIndexLegalRepository

settings = get_settings()
ai_quota_exhausted = False
question_tasks = QuestionTaskRegistry()


def _v2_service_dependencies():
    """Bind v2 use cases to patchable compatibility seams at call time."""

    return build_v2_execution_dependencies(
        settings,
        executions=question_execution_repository,
        callbacks=V2ApplicationCallbacks(
            resolve_repository=_v2_repository,
            active_provider=_v2_active_provider,
            retrieve_evidence=_retrieve_pinned_v2_evidence,
            route=lambda question: route_question(question, _question_router()),
            answerer=_answerer,
            ai_available=_ai_available,
            check_quota=_check_v2_quota,
            require_supported_date=_require_supported_as_of_date,
            save_authenticated=_save_if_authenticated,
            execution_capability=_execution_capability,
            capability_hash=_capability_hash,
            admit_phase=_admit_v2_provider_phase,
            run_core=_run_v2_core,
            run_finalize=_run_v2_finalize,
        ),
    )


dependencies = build_app_dependencies(settings, v2_dependency_provider=_v2_service_dependencies)
repository = dependencies.repository
question_execution_repository = dependencies.question_executions
question_phase_limiter = dependencies.question_phase_limiter
question_phase_tasks = dependencies.v2_service._phase_tasks
llamaindex_settings = dependencies.llamaindex_settings
llamaindex_vector_store = None
llamaindex_embedder = None
llamaindex_repository = None
v2_question_execution_service = dependencies.v2_service
supabase_auth = dependencies.supabase_auth
postgres_identity = dependencies.postgres_identity
collector_load_errors = dependencies.collector_load_errors


@lru_cache(maxsize=1)
def _build_llamaindex_resources(
    database_url: str | None, nvidia_api_key: str | None
) -> tuple[object, object, LlamaIndexLegalRepository] | None:
    """Compatibility facade over bootstrap's only LlamaIndex resource builder."""

    return build_llamaindex_resources(
        database_url,
        nvidia_api_key,
        llamaindex_settings=llamaindex_settings,
        delegate=repository,
        embedder_factory=build_llamaindex_embedder,
        repository_factory=LlamaIndexLegalRepository,
    )


def _llamaindex_async_database_url(database_url: str) -> str:
    return normalize_async_database_url(database_url)


def _llamaindex_sync_database_url(database_url: str) -> str:
    return normalize_sync_database_url(database_url)


def _llamaindex_resources() -> tuple[object | None, object | None, object | None] | None:
    """Return injected resources first, otherwise resolve the lazy production bundle."""

    global llamaindex_embedder, llamaindex_repository, llamaindex_vector_store
    if any(
        resource is not None
        for resource in (llamaindex_vector_store, llamaindex_embedder, llamaindex_repository)
    ):
        return llamaindex_vector_store, llamaindex_embedder, llamaindex_repository
    try:
        resources = (
            dependencies.v2_resources.resolve()
            if (
                build_llamaindex_embedder is _DEFAULT_LLAMAINDEX_EMBEDDER_FACTORY
                and LlamaIndexLegalRepository is _DEFAULT_LLAMAINDEX_REPOSITORY_FACTORY
            )
            else _build_llamaindex_resources(
                settings.database_url, llamaindex_settings.nvidia_api_key
            )
        )
    except Exception:
        return None
    if resources is None:
        return None
    llamaindex_vector_store, llamaindex_embedder, llamaindex_repository = resources
    return llamaindex_vector_store, llamaindex_embedder, llamaindex_repository


async def _v2_index_ready() -> bool:
    """Allow v2 only when the active pointer references an active generation."""

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
    try:
        return await _v2_index_ready()
    except Exception:
        return False


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


async def _load_corpus_temporal_state(current_repository: LegalRepository) -> CorpusTemporalState:
    try:
        return await current_repository.corpus_temporal_state(_current_korea_date())
    except Exception as exc:
        raise _corpus_unready_http_error() from exc


async def _require_supported_as_of_date(
    requested_date: date, current_repository: LegalRepository
) -> None:
    state = await _load_corpus_temporal_state(current_repository)
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
    return build_nvidia_embedder(settings)


async def _check_quota(kind: str, *, user: MockUser | None = None) -> None:
    if user is None or not postgres_identity or not settings.account_quota_enabled:
        return
    limit = (
        settings.authenticated_ai_daily_limit
        if kind == "ai"
        else settings.authenticated_search_daily_limit
    )
    if not await postgres_identity.consume_quota(user.id, date.today(), kind, limit):
        raise HTTPException(status_code=429, detail="오늘의 계정 사용 한도를 초과했습니다.")


async def _check_v2_quota(kind: str, user: MockUser | None) -> None:
    await _check_quota(kind, user=user)


def _ai_available() -> bool:
    return settings.ai_enabled and not ai_quota_exhausted


def _question_owner(request: Any, user: MockUser | None) -> str:
    if user is not None:
        return f"user:{user.id}"
    subject = anonymous_rate_limit_subject(
        request.headers,
        request.client.host if request.client else None,
        trust_vercel_proxy=settings.environment == "production",
    )
    return "anonymous:" + daily_subject_hash(subject, settings.rate_limit_secret, date.today())


def _answerer() -> NvidiaNimAnswerer:
    return build_nvidia_answerer(settings)


def _question_router() -> NvidiaNimQuestionRouter:
    return build_nvidia_question_router(settings)


def _ai_unavailable_reason() -> str | None:
    if not settings.ai_enabled:
        return "ai_disabled"
    if ai_quota_exhausted:
        return "quota_exhausted"
    return None


def _initial_fallback_reason(payload: QuestionRequest) -> Any:
    if payload.answer_mode == "search_only":
        return None
    reason = _ai_unavailable_reason()
    from app.domain.schemas import AiFallbackReason

    return AiFallbackReason(reason) if reason else None


def create_app(app_dependencies: AppDependencies) -> FastAPI:
    """Create one FastAPI app by composing versioned delivery routers."""

    application = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        lifespan=app_dependencies.lifespan,
    )
    application.add_middleware(
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
    application.include_router(build_v1_router())
    application.include_router(build_v2_router())
    return application


app = create_app(dependencies)

__all__ = [
    "_answer_question",
    "_authenticated_user",
    "_build_llamaindex_resources",
    "_capability_hash",
    "_check_quota",
    "_current_korea_date",
    "_elapsed_ms",
    "_load_corpus_temporal_state",
    "_optional_user",
    "_remaining_ms",
    "_requires_legacy_query_embedding",
    "_retrieve_pinned_v2_evidence",
    "_retrieve_question_evidence",
    "_run_v2_core",
    "_run_v2_finalize",
    "_sse",
    "_stream_execution_phase",
    "_v2_active_provider",
    "_v2_core_from_frozen_evidence",
    "_v2_repository",
    "_v2_response_from_frozen_evidence",
    "ExecutionStatus",
    "app",
    "cancel_question",
    "create_app",
    "dependencies",
    "llamaindex_search",
    "llamaindex_search_index",
    "question",
]
