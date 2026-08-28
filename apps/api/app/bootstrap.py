"""Production composition root for API adapters and v2 framework resources."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

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
from app.adapters.llamaindex_repository import LlamaIndexLegalRepository
from app.adapters.memory_question_execution import MemoryQuestionExecutionRepository
from app.adapters.memory_repository import repository as memory_repository
from app.adapters.postgres_identity import PostgresIdentityRepository
from app.adapters.postgres_question_execution import PostgresQuestionExecutionRepository
from app.adapters.postgres_repository import PostgresLegalRepository
from app.adapters.supabase_auth import SupabaseAuth
from app.application.v2.dependencies import V2ExecutionDependencies
from app.application.v2.phase_service import V2QuestionExecutionService
from app.settings import Settings


@dataclass(frozen=True)
class AppDependencies:
    """Long-lived application adapters assembled once for one API process."""

    repository: LegalRepository
    question_executions: Any
    question_phase_limiter: Any
    v2_service: V2QuestionExecutionService
    llamaindex_settings: Any
    llamaindex_resource_builder: Callable[
        [str | None, str | None, LegalRepository],
        tuple[object, object, LlamaIndexLegalRepository] | None,
    ]
    supabase_auth: SupabaseAuth | None
    postgres_identity: PostgresIdentityRepository | None
    collector_load_errors: tuple[str, ...]


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
    return AppDependencies(
        repository=repository,
        question_executions=question_executions,
        question_phase_limiter=question_phase_limiter,
        v2_service=V2QuestionExecutionService(v2_dependency_provider),
        llamaindex_settings=llamaindex_settings,
        llamaindex_resource_builder=lambda database_url, nvidia_api_key, delegate: (
            build_llamaindex_resources(
                database_url,
                nvidia_api_key,
                llamaindex_settings=llamaindex_settings,
                delegate=delegate,
            )
        ),
        supabase_auth=supabase_auth,
        postgres_identity=postgres_identity,
        collector_load_errors=tuple(collector_load_errors),
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
        normalize_async_database_url(database_url), poolclass=NullPool
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
