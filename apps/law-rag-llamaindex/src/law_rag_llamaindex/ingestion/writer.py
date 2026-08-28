"""Database and vector-store writers used by the ingestion services."""

import re
from collections.abc import Awaitable, Callable, Mapping
from typing import Any

from llama_index.core.schema import TextNode
from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import AsyncEngine

_GENERATION_TABLE_NAME = re.compile(r"^law_rag_li_[a-f0-9]{32}$")


class IngestionRunRecorder:
    """Persist the lifecycle of a mutable, incremental ingestion run."""

    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine

    async def start(self) -> str:
        query = text(
            """
            INSERT INTO law_rag_llamaindex_ingestion_runs (started_at, status)
            VALUES (CURRENT_TIMESTAMP, :status)
            RETURNING id
            """
        )
        async with self._engine.begin() as connection:
            result = await connection.execute(query, {"status": "running"})
        return result.scalar_one()

    async def finish(
        self, run_id: str, status: str, *, node_count: int | None = None
    ) -> None:
        if node_count is None:
            query = text(
                """
                UPDATE law_rag_llamaindex_ingestion_runs
                SET status = :status, finished_at = CURRENT_TIMESTAMP
                WHERE id = :run_id
                """
            )
            parameters = {"status": status, "run_id": run_id}
        else:
            query = text(
                """
                UPDATE law_rag_llamaindex_ingestion_runs
                SET status = :status, finished_at = CURRENT_TIMESTAMP, node_count = :node_count
                WHERE id = :run_id
                """
            )
            parameters = {"status": status, "node_count": node_count, "run_id": run_id}
        async with self._engine.begin() as connection:
            await connection.execute(query, parameters)


async def _start_ingestion_run(engine: AsyncEngine) -> str:
    """Compatibility helper for callers that used the old module-local function."""

    return await IngestionRunRecorder(engine).start()


async def _finish_ingestion_run(
    engine: AsyncEngine, run_id: str, status: str, *, node_count: int | None = None
) -> None:
    """Compatibility helper for callers that used the old module-local function."""

    await IngestionRunRecorder(engine).finish(run_id, status, node_count=node_count)


async def existing_hashes(engine: AsyncEngine, table_name: str) -> dict[str, str]:
    """Read source hashes from an existing vector table, if it exists."""

    physical_table = f"data_{table_name}"
    async with engine.connect() as connection:
        table_exists = await connection.run_sync(
            lambda sync_conn: inspect(sync_conn).has_table(physical_table)
        )
        if not table_exists:
            return {}
        query = text(
            f'''SELECT node_id, metadata_->>'source_text_sha256' AS sha FROM "{physical_table}"'''
        )
        result = await connection.execute(query)
        return {row.node_id: row.sha for row in result}


async def delete_nodes(engine: AsyncEngine, table_name: str, node_ids: set[str]) -> None:
    """Delete stale nodes before writing their replacement embeddings."""

    if not node_ids:
        return
    physical_table = f"data_{table_name}"
    query = text(f'DELETE FROM "{physical_table}" WHERE node_id = ANY(:ids)')
    async with engine.begin() as connection:
        await connection.execute(query, {"ids": list(node_ids)})


def _generation_data_table_name(table_name: str) -> str:
    """Return a safely derived physical vector-table identifier."""

    if _GENERATION_TABLE_NAME.fullmatch(table_name) is None:
        raise ValueError("generation table name is not allowlisted")
    return f"data_{table_name}"


async def copy_generation_vectors(
    engine: AsyncEngine, source_table_name: str, target_table_name: str, node_ids: list[str]
) -> int:
    """Copy compatible vectors DB-to-DB without loading embeddings into the process."""

    if not node_ids:
        return 0
    source_table = _generation_data_table_name(source_table_name)
    target_table = _generation_data_table_name(target_table_name)
    query = text(
        f'''INSERT INTO "{target_table}" (text,metadata_,node_id,embedding)
            SELECT text,metadata_,node_id,embedding FROM "{source_table}"
            WHERE node_id = ANY(:node_ids)'''
    )
    async with engine.begin() as connection:
        result = await connection.execute(query, {"node_ids": node_ids})
    return result.rowcount


async def verify_generation_vectors(
    engine: AsyncEngine,
    generation: Any,
    *,
    source_count: int,
    node_count: int,
) -> None:
    """Reject a candidate whose physical table cannot prove source coverage."""

    table_name = _generation_data_table_name(generation.table_name)
    query = text(
        f'''SELECT count(*) AS node_count,
                   count(DISTINCT node_id) AS distinct_node_count,
                   count(DISTINCT metadata_->>'provision_id') AS source_count,
                   count(*) FILTER (
                     WHERE metadata_->>'provision_id' IS NULL
                        OR metadata_->>'document_id' IS NULL
                        OR metadata_->>'source_url' IS NULL
                        OR metadata_->>'effective_from' IS NULL
                   ) AS invalid_metadata_count
            FROM "{table_name}"'''
    )
    async with engine.connect() as connection:
        row = (await connection.execute(query)).mappings().one()
    if (
        row["node_count"] != node_count
        or row["distinct_node_count"] != node_count
        or row["source_count"] != source_count
        or row["invalid_metadata_count"] != 0
    ):
        raise ValueError("generation vector table failed source coverage validation")


CopyGenerationVectors = Callable[[AsyncEngine, str, str, list[str]], Awaitable[int]]
VerifyGeneration = Callable[..., Awaitable[None]]
VectorStoreFactory = Callable[[Any], Any]


class GenerationVectorWriter:
    """Write transformed nodes and compatible copied vectors for one generation."""

    def __init__(
        self,
        engine: AsyncEngine,
        vector_store_factory: VectorStoreFactory,
        *,
        copy_vectors: CopyGenerationVectors | None = None,
        verifier: VerifyGeneration | None = None,
    ) -> None:
        self._engine = engine
        self._vector_store_factory = vector_store_factory
        self._copy_vectors = copy_vectors or copy_generation_vectors
        self._verifier = verifier or verify_generation_vectors

    def write_nodes(self, generation: Any, nodes: list[TextNode]) -> None:
        """Persist transformed nodes in the newly allocated generation table."""

        self._vector_store_factory(generation).add(nodes)

    async def copy_unchanged(
        self,
        active_generation: Any,
        generation: Any,
        unchanged_ids: list[str],
        active_sources: Mapping[str, Any],
    ) -> int:
        """Copy unchanged source vectors and verify their lineage count."""

        copied_count = await self._copy_vectors(
            self._engine,
            active_generation.table_name,
            generation.table_name,
            unchanged_ids,
        )
        expected_count = sum(
            active_sources[provision_id].node_count for provision_id in unchanged_ids
        )
        if copied_count != expected_count:
            raise ValueError("copied vector count does not match source lineage")
        return copied_count

    async def verify(
        self, generation: Any, *, source_count: int, node_count: int
    ) -> None:
        """Run the physical-table verifier before the catalog transition."""

        await self._verifier(
            self._engine,
            generation,
            source_count=source_count,
            node_count=node_count,
        )
