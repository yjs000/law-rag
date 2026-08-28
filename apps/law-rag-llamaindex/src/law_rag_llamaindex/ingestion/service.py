"""Application orchestration for mutable and immutable ingestion runs."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from llama_index.core.schema import TextNode

from law_rag_llamaindex.generation.models import (
    RetrievalGeneration,
    generation_source_records,
    provision_fingerprint,
    source_fingerprint,
)
from law_rag_llamaindex.ingestion.source_reader import DatabaseProvisionReader, ProvisionReader
from law_rag_llamaindex.ingestion.transform import (
    build_nodes,
    changed_provision_ids,
    run_generation_pipeline,
)
from law_rag_llamaindex.ingestion.writer import (
    CopyGenerationVectors,
    GenerationVectorWriter,
    IngestionRunRecorder,
    VerifyGeneration,
    delete_nodes,
    existing_hashes,
)
from law_rag_llamaindex.passage import ProvisionRecord


@dataclass(frozen=True)
class IngestionResult:
    """Counts returned by an ingestion run."""

    total_provisions: int
    embedded_count: int
    skipped_count: int


NodeTransformer = Callable[[list[ProvisionRecord], Any], list[TextNode]]
VectorStoreFactory = Callable[[RetrievalGeneration], Any]


class GenerationIngestionService:
    """Execute the immutable generation pipeline in explicit stage order.

    The service owns orchestration only. Database reads, node transformation, vector writes and
    physical validation are supplied as collaborators so the control flow remains testable.
    """

    def __init__(
        self,
        engine: Any,
        generation_repository: Any,
        vector_store_for_generation: VectorStoreFactory,
        embedder: Any,
        transform_fingerprint: str,
        *,
        source_reader: ProvisionReader | None = None,
        transformer: NodeTransformer | None = None,
        copy_vectors: CopyGenerationVectors | None = None,
        verifier: VerifyGeneration | None = None,
    ) -> None:
        self._engine = engine
        self._repository = generation_repository
        self._embedder = embedder
        self._transform_fingerprint = transform_fingerprint
        self._source_reader = source_reader or DatabaseProvisionReader(engine)
        self._transformer = transformer or run_generation_pipeline
        self._writer = GenerationVectorWriter(
            engine,
            vector_store_for_generation,
            copy_vectors=copy_vectors,
            verifier=verifier,
        )

    async def run(self) -> IngestionResult:
        """Read, transform, write, verify and publish one immutable generation."""

        provisions = await self._source_reader.read()
        active_generation = await self._repository.active()
        active_sources = await self._compatible_active_sources(active_generation)
        unchanged_ids = _unchanged_provision_ids(provisions, active_sources)
        changed_provisions = _changed_provisions(provisions, unchanged_ids)

        generation = await self._repository.start(
            source_fingerprint(provisions), self._transform_fingerprint
        )
        stage = "node_build"
        try:
            stage = "embedding"
            nodes = self._transformer(changed_provisions, self._embedder)

            stage = "vector_write"
            self._writer.write_nodes(generation, nodes)

            copied_node_count = 0
            if active_generation is not None and unchanged_ids:
                stage = "vector_copy"
                copied_node_count = await self._writer.copy_unchanged(
                    active_generation,
                    generation,
                    unchanged_ids,
                    active_sources,
                )

            stage = "generation_source_lineage"
            node_counts = _node_counts(provisions, active_sources)
            await self._repository.record_sources(
                generation.id,
                generation_source_records(
                    provisions,
                    node_counts=node_counts,
                    copied_provision_ids=set(unchanged_ids),
                    copied_from_generation_id=(
                        active_generation.id if active_generation is not None else None
                    ),
                ),
            )

            stage = "generation_verify"
            total_node_count = len(nodes) + copied_node_count
            await self._writer.verify(
                generation,
                source_count=len(provisions),
                node_count=total_node_count,
            )
            await self._repository.verify(
                generation.id,
                source_count=len(provisions),
                node_count=total_node_count,
            )

            stage = "generation_publish"
            await self._repository.publish(generation.id)
        except Exception:
            await _mark_generation_failed(self._repository, generation.id, stage)
            raise

        return IngestionResult(
            total_provisions=len(provisions),
            embedded_count=len(changed_provisions),
            skipped_count=len(unchanged_ids),
        )

    async def _compatible_active_sources(
        self, active_generation: RetrievalGeneration | None
    ) -> dict[str, Any]:
        """Read lineage only when the active transformation contract is compatible."""

        if (
            active_generation is None
            or active_generation.transform_fingerprint != self._transform_fingerprint
        ):
            return {}
        return {
            source.provision_id: source
            for source in await self._repository.sources(active_generation.id)
        }


class IncrementalIngestionService:
    """Update a legacy mutable vector table while recording run lifecycle."""

    def __init__(
        self,
        engine: Any,
        vector_store: Any,
        embedder: Any,
        table_name: str,
        *,
        source_reader: ProvisionReader | None = None,
    ) -> None:
        self._engine = engine
        self._vector_store = vector_store
        self._embedder = embedder
        self._table_name = table_name
        self._source_reader = source_reader or DatabaseProvisionReader(engine)

    async def run(self) -> IngestionResult:
        """Read changed rows, replace their vectors and record the terminal run state."""

        recorder = IngestionRunRecorder(self._engine)
        run_id = await recorder.start()
        try:
            provisions = await self._source_reader.read()
            current_hashes = await existing_hashes(self._engine, self._table_name)
            changed_ids = changed_provision_ids(provisions, current_hashes)
            changed_records = [
                provision
                for provision in provisions
                if provision["provision_id"] in changed_ids
            ]

            await delete_nodes(self._engine, self._table_name, changed_ids & current_hashes.keys())
            if changed_records:
                self._write_changed_records(changed_records)

            result = IngestionResult(
                total_provisions=len(provisions),
                embedded_count=len(changed_records),
                skipped_count=len(provisions) - len(changed_records),
            )
            await recorder.finish(
                run_id,
                "completed",
                node_count=result.embedded_count,
            )
            return result
        except Exception:
            try:
                await recorder.finish(run_id, "failed")
            except Exception:
                pass
            raise

    def _write_changed_records(self, provisions: list[ProvisionRecord]) -> None:
        nodes = build_nodes(provisions)
        embeddings = self._embedder.get_text_embedding_batch([node.text for node in nodes])
        for node, embedding in zip(nodes, embeddings, strict=True):
            node.embedding = embedding
        self._vector_store.add(nodes)


async def run_generation_ingestion(
    engine: Any,
    generation_repository: Any,
    vector_store_for_generation: VectorStoreFactory,
    embedder: Any,
    *,
    transform_fingerprint: str,
    verify_generation: VerifyGeneration | None = None,
    source_reader: ProvisionReader | None = None,
    transformer: NodeTransformer | None = None,
    copy_vectors: CopyGenerationVectors | None = None,
) -> IngestionResult:
    """Build and publish an immutable generation with injected pipeline collaborators."""

    service = GenerationIngestionService(
        engine,
        generation_repository,
        vector_store_for_generation,
        embedder,
        transform_fingerprint,
        source_reader=source_reader,
        transformer=transformer,
        copy_vectors=copy_vectors,
        verifier=verify_generation,
    )
    return await service.run()


async def run_ingestion(
    engine: Any,
    vector_store: Any,
    embedder: Any,
    table_name: str,
    *,
    source_reader: ProvisionReader | None = None,
) -> IngestionResult:
    """Run the compatibility mutable-table ingestion path."""

    service = IncrementalIngestionService(
        engine,
        vector_store,
        embedder,
        table_name,
        source_reader=source_reader,
    )
    return await service.run()


def _unchanged_provision_ids(
    provisions: list[ProvisionRecord], active_sources: dict[str, Any]
) -> list[str]:
    return [
        provision["provision_id"]
        for provision in provisions
        if _has_unchanged_source(provision, active_sources)
    ]


def _has_unchanged_source(provision: ProvisionRecord, active_sources: dict[str, Any]) -> bool:
    source = active_sources.get(provision["provision_id"])
    return source is not None and source.source_fingerprint == provision_fingerprint(provision)


def _changed_provisions(
    provisions: list[ProvisionRecord], unchanged_ids: list[str]
) -> list[ProvisionRecord]:
    unchanged = set(unchanged_ids)
    return [provision for provision in provisions if provision["provision_id"] not in unchanged]


def _node_counts(
    provisions: list[ProvisionRecord], active_sources: dict[str, Any]
) -> dict[str, int]:
    return {
        provision["provision_id"]: (
            active_sources[provision["provision_id"]].node_count
            if provision["provision_id"] in active_sources
            else 1
        )
        for provision in provisions
    }


async def _mark_generation_failed(repository: Any, generation_id: Any, stage: str) -> None:
    try:
        await repository.fail(generation_id, f"{stage}_failed")
    except Exception:
        pass


def _async_database_url(database_url: str) -> str:
    """Normalize a shared database URL for SQLAlchemy's async engine."""

    if database_url.startswith("postgresql+asyncpg://"):
        return database_url
    if database_url.startswith("postgresql://"):
        return database_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return database_url


def _sync_database_url(database_url: str) -> str:
    """Normalize a shared database URL for the sync PGVectorStore engine."""

    if database_url.startswith("postgresql+psycopg://"):
        return database_url
    if database_url.startswith("postgresql+asyncpg://"):
        return database_url.replace("postgresql+asyncpg://", "postgresql+psycopg://", 1)
    if database_url.startswith("postgresql://"):
        return database_url.replace("postgresql://", "postgresql+psycopg://", 1)
    return database_url
