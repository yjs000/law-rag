"""Production composition root for API adapters and v2 framework resources."""

from __future__ import annotations

from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

from law_rag_core.ports.repository import LegalRepository
from law_rag_llamaindex.active_index import ActiveGenerationIndexProvider
from law_rag_llamaindex.config import get_settings as get_llamaindex_settings
from law_rag_llamaindex.embedding import build_embedder as build_llamaindex_embedder
from law_rag_llamaindex.generations import PostgresGenerationRepository
from law_rag_llamaindex.store import build_generation_vector_store
from llama_index.core import VectorStoreIndex
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from app.adapters.capacity_leases import (
    MemoryConcurrencyLimiter,
    PostgresCapacityLeaseStore,
    PostgresConcurrencyLimiter,
)
from app.adapters.llamaindex_clarification_workflow import LlamaIndexClarificationWorkflow
from app.adapters.llamaindex_repository import LlamaIndexLegalRepository
from app.adapters.memory_clarification_case import MemoryClarificationCaseRepository
from app.adapters.memory_question_execution import MemoryQuestionExecutionRepository
from app.adapters.memory_repository import repository as memory_repository
from app.adapters.nvidia_nim_answerer import NvidiaNimAnswerer
from app.adapters.nvidia_nim_clarification import NvidiaNimClarificationInterpreter
from app.adapters.nvidia_nim_embedder import NvidiaNimEmbedder
from app.adapters.nvidia_nim_route_classifier import NvidiaNimQuestionRouter
from app.adapters.openai_answerer import (
    CoreDraft,
    build_messages_v2,
    select_generation_hits,
    validate_core_draft,
    validate_draft,
)
from app.adapters.postgres_clarification_case import PostgresClarificationCaseRepository
from app.adapters.postgres_identity import PostgresIdentityRepository
from app.adapters.postgres_question_execution import PostgresQuestionExecutionRepository
from app.adapters.postgres_repository import PostgresLegalRepository
from app.adapters.structured_clarification_continuation import (
    StructuredClarificationContinuationExtractor,
)
from app.adapters.supabase_auth import SupabaseAuth
from app.application.clarification_workflow import ClarificationTurnOrchestrator
from app.application.v1.dependencies import QueryEmbeddingCapability, V1AnswerDependencies
from app.application.v2.dependencies import (
    ClarificationWorkflowDependencies,
    V2ExecutionDependencies,
)
from app.application.v2.phase_service import V2QuestionExecutionService
from app.domain.schemas import MockUser, QuestionRequest, QuestionResponse, SearchHit
from app.ports.question_execution import QuestionExecutionRecord
from app.settings import Settings


class V2LlamaIndexResources:
    """Lazily create and own the active-generation adapter bundle."""

    def __init__(
        self,
        build: Callable[[], tuple[object, object, LlamaIndexLegalRepository] | None],
    ) -> None:
        self._build = build
        self._resources: tuple[object, object, LlamaIndexLegalRepository] | None = None
        self._initialized = False

    def resolve(self) -> tuple[object, object, LlamaIndexLegalRepository] | None:
        """Build at first use; retain the single shared framework bundle afterwards."""

        if not self._initialized:
            self._resources = self._build()
            self._initialized = True
        return self._resources

    async def aclose(self) -> None:
        """Dispose the provider and its engines when the API process ends."""

        if self._resources is None:
            return
        provider = self._resources[0]
        if hasattr(provider, "aclose"):
            await provider.aclose()


@dataclass(frozen=True)
class LegacyQueryEmbeddingCapability:
    """Composition-owned policy for v1 query-vector generation."""

    required: bool

    def requires_application_query_embedding(self) -> bool:
        return self.required


@dataclass(frozen=True)
class AppDependencies:
    """Long-lived application adapters assembled once for one API process."""

    repository: LegalRepository
    question_executions: Any
    question_phase_limiter: Any
    v2_service: V2QuestionExecutionService
    llamaindex_settings: Any
    v2_resources: V2LlamaIndexResources
    v1_query_embedding_capability: QueryEmbeddingCapability
    nvidia_embedder: NvidiaNimEmbedder | None
    nvidia_answerer: NvidiaNimAnswerer | None
    clarification_cases: Any
    nvidia_clarification_interpreter: NvidiaNimClarificationInterpreter | None
    clarification_workflow: ClarificationTurnOrchestrator | None
    nvidia_question_router: NvidiaNimQuestionRouter | None
    supabase_auth: SupabaseAuth | None
    postgres_identity: PostgresIdentityRepository | None
    collector_load_errors: tuple[str, ...]

    @asynccontextmanager
    async def lifespan(self, _app: Any) -> AsyncIterator[None]:
        """Close resources created by this composition root exactly once."""

        yield
        if self.supabase_auth:
            await self.supabase_auth.aclose()
        for adapter in (
            self.nvidia_embedder,
            self.nvidia_answerer,
            self.nvidia_clarification_interpreter,
            self.nvidia_question_router,
        ):
            if adapter:
                await adapter.aclose()
        await self.v2_resources.aclose()


@dataclass(frozen=True)
class V2ApplicationCallbacks:
    """Application policy and compatibility seams supplied outside bootstrap."""

    resolve_repository: Callable[[], Awaitable[LegalRepository]]
    active_provider: Callable[[], Any]
    retrieve_evidence: Callable[
        [QuestionRequest, Any, LegalRepository],
        Awaitable[tuple[list[SearchHit], datetime | None]],
    ]
    route: Callable[[str], Awaitable[Any]]
    answerer: Callable[[], Any]
    ai_available: Callable[[], bool]
    check_quota: Callable[[str, MockUser | None], Awaitable[None]]
    require_supported_date: Callable[[Any, LegalRepository], Awaitable[None]]
    save_authenticated: Callable[
        [MockUser | None, QuestionRequest, QuestionResponse], Awaitable[QuestionResponse]
    ]
    clarification_cases: Any
    execution_capability: Callable[[str, str], str]
    capability_hash: Callable[[str | None], str | None]
    admit_phase: Callable[[QuestionExecutionRecord, Literal["core", "finalize"]], Awaitable[Any]]
    run_core: Callable[[QuestionExecutionRecord], Awaitable[Any]]
    run_finalize: Callable[[QuestionExecutionRecord, MockUser | None], Awaitable[Any]]


@dataclass(frozen=True)
class V1ApplicationCallbacks:
    """Application seams supplied by the entry point for v1 answer execution."""

    ai_available: Callable[[], bool]
    ai_unavailable_reason: Callable[[], str | None]
    initial_fallback_reason: Callable[[QuestionRequest], Any]
    check_quota: Callable[[str, MockUser | None], Awaitable[None]]
    require_supported_date: Callable[[Any, LegalRepository], Awaitable[None]]
    route: Callable[[str], Awaitable[Any]]
    embed: Callable[[list[str]], Awaitable[list[list[float]]]]
    retrieve_evidence: Callable[
        [QuestionRequest, list[float] | None, LegalRepository], Awaitable[Any]
    ]
    answer: Callable[[QuestionRequest, list[SearchHit]], Awaitable[Any]]
    answer_blocked_route: Callable[[QuestionRequest, str, str | None], Awaitable[Any]]
    save_response: Callable[
        [MockUser | None, QuestionRequest, QuestionResponse, dict[str, object]],
        Awaitable[QuestionResponse],
    ]
    mark_ai_quota_exhausted: Callable[[], None]


def build_v1_answer_dependencies(
    settings: Settings,
    *,
    query_embedding_capability: QueryEmbeddingCapability,
    callbacks: V1ApplicationCallbacks,
) -> V1AnswerDependencies:
    """Assemble the v1 use case without exposing its adapter implementations."""

    return V1AnswerDependencies(
        search_only_enabled=settings.search_only_enabled,
        embedding_enabled=settings.embedding_enabled,
        answer_evidence_max_characters=settings.answer_evidence_max_characters,
        route_classifier_timeout_seconds=settings.route_classifier_timeout_seconds,
        question_embedding_timeout_seconds=settings.question_embedding_timeout_seconds,
        retrieval_timeout_seconds=settings.retrieval_timeout_seconds,
        answer_timeout_seconds=settings.answer_timeout_seconds,
        ai_available=callbacks.ai_available,
        ai_unavailable_reason=callbacks.ai_unavailable_reason,
        initial_fallback_reason=callbacks.initial_fallback_reason,
        check_quota=callbacks.check_quota,
        require_supported_date=callbacks.require_supported_date,
        route=callbacks.route,
        query_embedding_capability=query_embedding_capability,
        embed=callbacks.embed,
        retrieve_evidence=callbacks.retrieve_evidence,
        answer=callbacks.answer,
        answer_blocked_route=callbacks.answer_blocked_route,
        select_generation_hits=select_generation_hits,
        validate_draft=validate_draft,
        save_response=callbacks.save_response,
        mark_ai_quota_exhausted=callbacks.mark_ai_quota_exhausted,
    )


def build_v2_execution_dependencies(
    settings: Settings,
    *,
    executions: Any,
    callbacks: V2ApplicationCallbacks,
) -> V2ExecutionDependencies:
    """Assemble the v2 use case while retaining explicit transport seams."""

    return V2ExecutionDependencies(
        executions=executions,
        clarification_cases=callbacks.clarification_cases,
        resolve_repository=callbacks.resolve_repository,
        active_provider=callbacks.active_provider,
        retrieve_evidence=callbacks.retrieve_evidence,
        route=callbacks.route,
        answerer=callbacks.answerer,
        ai_available=callbacks.ai_available,
        check_quota=callbacks.check_quota,
        require_supported_date=callbacks.require_supported_date,
        save_authenticated=callbacks.save_authenticated,
        select_generation_hits=select_generation_hits,
        validate_core=validate_core_draft,
        validate_response=validate_draft,
        make_core_draft=lambda summary, citation_ids, action: CoreDraft(
            summary=summary,
            citation_ids=citation_ids,
            action=action,
        ),
        answer_evidence_max_characters=settings.answer_evidence_max_characters,
        phase_timeout=timedelta(seconds=settings.v2_phase_timeout_seconds),
        now=lambda: datetime.now(UTC),
        execution_capability=callbacks.execution_capability,
        capability_hash=callbacks.capability_hash,
        admit_phase=callbacks.admit_phase,
        run_core=callbacks.run_core,
        run_finalize=callbacks.run_finalize,
    )


def build_app_dependencies(
    settings: Settings,
    *,
    v2_dependency_provider: Callable[[], V2ExecutionDependencies],
) -> AppDependencies:
    """Create shared adapters without opening optional v2 framework resources.

    The LlamaIndex bundle remains lazy so a database URL alone never performs
    vector-store or provider construction during import.
    """

    repository: LegalRepository = (
        PostgresLegalRepository(settings.database_url)
        if settings.database_url
        else memory_repository
    )
    question_executions = (
        PostgresQuestionExecutionRepository(repository.engine)
        if isinstance(repository, PostgresLegalRepository)
        else MemoryQuestionExecutionRepository()
    )
    clarification_cases = (
        PostgresClarificationCaseRepository(repository.engine)
        if isinstance(repository, PostgresLegalRepository)
        else MemoryClarificationCaseRepository()
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
        _, collector_load_errors = memory_repository.load_collector_state(
            settings.collector_state_dir
        )

    llamaindex_settings = get_llamaindex_settings()
    nvidia_embedder = build_nvidia_embedder(settings) if settings.ai_enabled else None
    nvidia_answerer = build_nvidia_answerer(settings) if settings.ai_enabled else None
    nvidia_clarification_interpreter = (
        build_nvidia_clarification_interpreter(settings) if settings.ai_enabled else None
    )
    nvidia_question_router = build_nvidia_question_router(settings) if settings.ai_enabled else None
    clarification_workflow = (
        LlamaIndexClarificationWorkflow(
            ClarificationWorkflowDependencies(
                repository=clarification_cases,
                initial_judge=nvidia_clarification_interpreter,
                continuation_extractor=build_structured_clarification_continuation_extractor(),
                now=lambda: datetime.now(UTC),
                case_ttl=timedelta(days=1),
            )
        )
        if nvidia_clarification_interpreter is not None
        else None
    )
    v2_resources = V2LlamaIndexResources(
        lambda: build_llamaindex_resources(
            settings.database_url,
            llamaindex_settings.nvidia_api_key,
            llamaindex_settings=llamaindex_settings,
            delegate=repository,
        )
    )
    return AppDependencies(
        repository=repository,
        question_executions=question_executions,
        question_phase_limiter=question_phase_limiter,
        v2_service=V2QuestionExecutionService(v2_dependency_provider),
        llamaindex_settings=llamaindex_settings,
        v2_resources=v2_resources,
        v1_query_embedding_capability=build_v1_query_embedding_capability(repository),
        nvidia_embedder=nvidia_embedder,
        nvidia_answerer=nvidia_answerer,
        clarification_cases=clarification_cases,
        nvidia_clarification_interpreter=nvidia_clarification_interpreter,
        clarification_workflow=clarification_workflow,
        nvidia_question_router=nvidia_question_router,
        supabase_auth=supabase_auth,
        postgres_identity=postgres_identity,
        collector_load_errors=tuple(collector_load_errors),
    )


def build_nvidia_embedder(settings: Settings) -> NvidiaNimEmbedder:
    """Create the legacy embedding adapter from the single API configuration."""

    return NvidiaNimEmbedder(
        api_key=settings.nvidia_api_key or "",
        base_url=settings.nvidia_base_url,
        model=settings.nvidia_embedding_model,
        dimensions=settings.embedding_dimensions,
        timeout_seconds=settings.embedding_timeout_seconds,
    )


def build_v1_query_embedding_capability(
    repository: LegalRepository,
) -> QueryEmbeddingCapability:
    """Keep framework-specific v1 embedding policy at the composition boundary."""

    return LegacyQueryEmbeddingCapability(
        required=not isinstance(repository, LlamaIndexLegalRepository)
    )


def build_nvidia_answerer(settings: Settings) -> NvidiaNimAnswerer:
    """Create the shared v1/v2 answer adapter with the selected prompt version."""

    return NvidiaNimAnswerer(
        api_key=settings.nvidia_api_key or "",
        base_url=settings.nvidia_base_url,
        model=settings.nvidia_answer_model,
        timeout_seconds=settings.answer_timeout_seconds,
        max_output_tokens=settings.answer_max_output_tokens,
        max_attempts=settings.answer_generation_max_attempts,
        message_builder=build_messages_v2,
    )


def build_nvidia_clarification_interpreter(settings: Settings) -> NvidiaNimClarificationInterpreter:
    """Create the single configured Ultra interpreter for clarification turns."""

    return NvidiaNimClarificationInterpreter(
        api_key=settings.nvidia_api_key or "",
        base_url=settings.nvidia_base_url,
        model=settings.nvidia_route_classifier_model,
        timeout_seconds=settings.route_classifier_timeout_seconds,
    )


def build_structured_clarification_continuation_extractor() -> (
    StructuredClarificationContinuationExtractor
):
    """Create the non-NVIDIA structured extractor used after the initial turn."""

    return StructuredClarificationContinuationExtractor()


def build_nvidia_question_router(settings: Settings) -> NvidiaNimQuestionRouter:
    """Create the shared question-routing adapter from API configuration."""

    return NvidiaNimQuestionRouter(
        api_key=settings.nvidia_api_key or "",
        base_url=settings.nvidia_base_url,
        model=settings.nvidia_route_classifier_model,
        timeout_seconds=settings.route_classifier_timeout_seconds,
    )


def build_llamaindex_resources(
    database_url: str | None,
    nvidia_api_key: str | None,
    *,
    llamaindex_settings: Any,
    delegate: LegalRepository,
    embedder_factory: Callable[[Any], object] = build_llamaindex_embedder,
    repository_factory: Callable[
        [LegalRepository, object, object], LlamaIndexLegalRepository
    ] = LlamaIndexLegalRepository,
) -> tuple[object, object, LlamaIndexLegalRepository] | None:
    """Build v2 engines, active-index adapter, and repository in one place."""

    if not database_url or not nvidia_api_key:
        return None
    embedder = embedder_factory(llamaindex_settings)
    async_engine = create_async_engine(
        normalize_async_database_url(database_url),
        poolclass=NullPool,
        connect_args={"statement_cache_size": 0},
    )
    sync_engine = create_engine(normalize_sync_database_url(database_url), poolclass=NullPool)

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
    return provider, embedder, repository_factory(delegate, provider, embedder)


def normalize_async_database_url(database_url: str) -> str:
    """Normalize the shared URL for the active-generation async catalog reader."""

    if database_url.startswith("postgresql+asyncpg://"):
        return database_url
    if database_url.startswith("postgresql://"):
        return database_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return database_url


def normalize_sync_database_url(database_url: str) -> str:
    """Normalize the shared URL for the active generation's PGVector store."""

    if database_url.startswith("postgresql+psycopg://"):
        return database_url
    if database_url.startswith("postgresql+asyncpg://"):
        return database_url.replace("postgresql+asyncpg://", "postgresql+psycopg://", 1)
    if database_url.startswith("postgresql://"):
        return database_url.replace("postgresql://", "postgresql+psycopg://", 1)
    return database_url
