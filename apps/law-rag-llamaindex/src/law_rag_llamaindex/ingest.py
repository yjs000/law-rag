"""Compatibility facade and CLI for the v2 LlamaIndex ingestion pipeline.

The implementation is grouped by stage in :mod:`law_rag_llamaindex.ingestion`.
This module preserves the original import surface and its test injection seams.
"""

import asyncio
from typing import Any

from llama_index.core.ingestion import IngestionPipeline
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from law_rag_llamaindex.ingestion.service import (
    IngestionResult,
    _async_database_url,
    _sync_database_url,
)
from law_rag_llamaindex.ingestion.service import (
    run_generation_ingestion as _run_generation_ingestion,
)
from law_rag_llamaindex.ingestion.service import (
    run_ingestion as _run_ingestion,
)
from law_rag_llamaindex.ingestion.transform import (
    build_nodes,
    changed_provision_ids,
)
from law_rag_llamaindex.ingestion.transform import (
    run_generation_pipeline as _run_generation_pipeline,
)
from law_rag_llamaindex.ingestion.writer import (
    _finish_ingestion_run,
    _start_ingestion_run,
    copy_generation_vectors,
    delete_nodes,
    existing_hashes,
    verify_generation_vectors,
)

__all__ = [
    "IngestionResult",
    "IngestionPipeline",
    "_async_database_url",
    "_finish_ingestion_run",
    "_start_ingestion_run",
    "_sync_database_url",
    "build_nodes",
    "changed_provision_ids",
    "copy_generation_vectors",
    "delete_nodes",
    "existing_hashes",
    "main",
    "run_generation_ingestion",
    "run_generation_pipeline",
    "run_ingestion",
    "verify_generation_vectors",
]


async def run_generation_ingestion(
    engine: Any,
    generation_repository: Any,
    vector_store_for_generation: Any,
    embedder: Any,
    *,
    transform_fingerprint: str,
    verify_generation: Any | None = None,
    source_reader: Any | None = None,
    transformer: Any | None = None,
    copy_vectors: Any | None = None,
) -> IngestionResult:
    """Run the generation service while retaining the established injection seams."""

    return await _run_generation_ingestion(
        engine,
        generation_repository,
        vector_store_for_generation,
        embedder,
        transform_fingerprint=transform_fingerprint,
        verify_generation=(
            verify_generation if verify_generation is not None else verify_generation_vectors
        ),
        source_reader=source_reader,
        transformer=transformer if transformer is not None else run_generation_pipeline,
        copy_vectors=copy_vectors if copy_vectors is not None else copy_generation_vectors,
    )


def run_generation_pipeline(provisions: list[Any], embedder: Any) -> list[Any]:
    """Run the transform stage through the original pipeline-factory seam."""

    return _run_generation_pipeline(
        provisions,
        embedder,
        pipeline_factory=IngestionPipeline,
    )


async def run_ingestion(
    engine: Any,
    vector_store: Any,
    embedder: Any,
    table_name: str,
    *,
    source_reader: Any | None = None,
) -> IngestionResult:
    """Run the legacy mutable-table service through its original import path."""

    return await _run_ingestion(
        engine,
        vector_store,
        embedder,
        table_name,
        source_reader=source_reader,
    )


async def main() -> None:
    """Build and publish the next retrieval generation from configured services."""

    from law_rag_llamaindex.config import get_settings
    from law_rag_llamaindex.embedding import build_embedder
    from law_rag_llamaindex.generations import PostgresGenerationRepository, transform_fingerprint
    from law_rag_llamaindex.store import build_generation_vector_store

    settings = get_settings()
    if not settings.database_url:
        raise SystemExit("DATABASE_URL is not configured")
    if not settings.nvidia_api_key:
        raise SystemExit("NVIDIA_API_KEY is not configured")

    engine = create_async_engine(_async_database_url(settings.database_url), poolclass=NullPool)
    sync_engine = create_engine(_sync_database_url(settings.database_url), poolclass=NullPool)
    try:
        result = await run_generation_ingestion(
            engine,
            PostgresGenerationRepository(engine),
            lambda generation: build_generation_vector_store(
                settings,
                generation,
                engine=sync_engine,
                async_engine=engine,
                perform_setup=True,
            ),
            build_embedder(settings),
            transform_fingerprint=transform_fingerprint(
                chunker_version="law-chunker-v1",
                embedding_provider="nvidia",
                embedding_model=settings.nvidia_embedding_model,
                embedding_profile="truncate=end",
                embed_dim=settings.embed_dim,
            ),
        )
        print(
            f"ingestion complete: total={result.total_provisions} "
            f"embedded={result.embedded_count} skipped={result.skipped_count}"
        )
    finally:
        await engine.dispose()
        sync_engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
