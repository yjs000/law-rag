"""PostgreSQL adapter for the immutable retrieval-generation catalog."""

from collections.abc import Iterable, Mapping
from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from law_rag_llamaindex.generation.models import (
    GenerationSource,
    RetrievalGeneration,
    generation_table_name,
)


class PostgresGenerationRepository:
    """Persist generation transitions using short, caller-owned transactions."""

    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine

    async def start(
        self,
        source_fingerprint: str,
        transform_fingerprint: str,
        *,
        generation_id: UUID | None = None,
    ) -> RetrievalGeneration:
        """Create an unpublished generation catalog row."""

        identifier = generation_id or uuid4()
        generation = RetrievalGeneration(
            id=identifier,
            table_name=generation_table_name(identifier),
            source_fingerprint=source_fingerprint,
            transform_fingerprint=transform_fingerprint,
            status="building",
            source_count=None,
            node_count=None,
            failure_code=None,
            created_at=datetime.now(UTC),
            verified_at=None,
            published_at=None,
        )
        query = text(
            """
            INSERT INTO llamaindex_retrieval_generations (
              generation_id,physical_table_name,source_fingerprint,transform_fingerprint,status
            ) VALUES (
              :generation_id,:table_name,:source_fingerprint,:transform_fingerprint,'building'
            )
            """
        )
        async with self._engine.begin() as connection:
            await connection.execute(
                query,
                {
                    "generation_id": generation.id,
                    "table_name": generation.table_name,
                    "source_fingerprint": source_fingerprint,
                    "transform_fingerprint": transform_fingerprint,
                },
            )
        return generation

    async def verify(self, generation_id: UUID, *, source_count: int, node_count: int) -> None:
        """Mark a fully validated candidate eligible for atomic publication."""

        query = text(
            """
            UPDATE llamaindex_retrieval_generations
            SET status = 'verified', source_count = :source_count, node_count = :node_count,
                verified_at = now()
            WHERE generation_id = :generation_id AND status = 'building'
            RETURNING generation_id
            """
        )
        async with self._engine.begin() as connection:
            result = await connection.execute(
                query,
                {
                    "generation_id": generation_id,
                    "source_count": source_count,
                    "node_count": node_count,
                },
            )
            result.scalar_one()

    async def record_sources(
        self, generation_id: UUID, sources: Iterable[Mapping[str, object]]
    ) -> None:
        """Persist the source lineage that was written into a candidate generation."""

        query = text(
            """
            INSERT INTO llamaindex_generation_sources (
              generation_id,provision_id,source_fingerprint,node_count,copied_from_generation_id
            ) VALUES (
              :generation_id,:provision_id,:source_fingerprint,:node_count,:copied_from_generation_id
            )
            ON CONFLICT(generation_id,provision_id) DO NOTHING
            """
        )
        async with self._engine.begin() as connection:
            for source in sources:
                await connection.execute(
                    query,
                    {
                        "generation_id": generation_id,
                        "provision_id": source["provision_id"],
                        "source_fingerprint": source["source_fingerprint"],
                        "node_count": source["node_count"],
                        "copied_from_generation_id": source.get("copied_from_generation_id"),
                    },
                )

    async def sources(self, generation_id: UUID) -> list[GenerationSource]:
        """Read the stored lineage required to select safe vector copies."""

        query = text(
            """
            SELECT provision_id,source_fingerprint,node_count,copied_from_generation_id
            FROM llamaindex_generation_sources
            WHERE generation_id = :generation_id
            ORDER BY provision_id
            """
        )
        async with self._engine.connect() as connection:
            rows = (await connection.execute(query, {"generation_id": generation_id})).mappings()
            return [
                GenerationSource(
                    provision_id=str(row["provision_id"]),
                    source_fingerprint=row["source_fingerprint"],
                    node_count=row["node_count"],
                    copied_from_generation_id=row["copied_from_generation_id"],
                )
                for row in rows
            ]

    async def publish(self, generation_id: UUID) -> None:
        """Switch active pointer only if the candidate has been verified."""

        lock = text("SELECT pg_advisory_xact_lock(hashtext('llamaindex_active_generation'))")
        activate = text(
            """
            UPDATE llamaindex_retrieval_generations
            SET status = 'active', published_at = now()
            WHERE generation_id = :generation_id AND status = 'verified'
            RETURNING generation_id
            """
        )
        retire_previous = text(
            """
            UPDATE llamaindex_retrieval_generations
            SET status = 'rollback'
            WHERE status = 'active' AND generation_id <> :generation_id
            """
        )
        retire_older_rollback = text(
            """
            UPDATE llamaindex_retrieval_generations
            SET status = 'retired'
            WHERE status = 'rollback'
            """
        )
        pointer = text(
            """
            INSERT INTO llamaindex_active_generation (singleton,generation_id,updated_at)
            VALUES (true,:generation_id,now())
            ON CONFLICT(singleton) DO UPDATE
            SET generation_id = excluded.generation_id, updated_at = excluded.updated_at
            """
        )
        async with self._engine.begin() as connection:
            await connection.execute(lock)
            await connection.execute(retire_older_rollback)
            await connection.execute(retire_previous, {"generation_id": generation_id})
            result = await connection.execute(activate, {"generation_id": generation_id})
            result.scalar_one()
            await connection.execute(pointer, {"generation_id": generation_id})

    async def fail(self, generation_id: UUID, failure_code: str) -> None:
        """Record a failed candidate while retaining the current active pointer."""

        query = text(
            """
            UPDATE llamaindex_retrieval_generations
            SET status = 'failed', failure_code = :failure_code
            WHERE generation_id = :generation_id AND status IN ('building','verified')
            RETURNING generation_id
            """
        )
        async with self._engine.begin() as connection:
            result = await connection.execute(
                query, {"generation_id": generation_id, "failure_code": failure_code}
            )
            result.scalar_one()

    async def rollback(self, generation_id: UUID) -> None:
        """Atomically restore an explicitly retained rollback generation."""

        lock = text("SELECT pg_advisory_xact_lock(hashtext('llamaindex_active_generation'))")
        activate = text(
            """
            UPDATE llamaindex_retrieval_generations
            SET status = 'active', published_at = now()
            WHERE generation_id = :generation_id AND status = 'rollback'
            RETURNING generation_id
            """
        )
        retire = text(
            """
            UPDATE llamaindex_retrieval_generations
            SET status = 'rollback'
            WHERE status = 'active' AND generation_id <> :generation_id
            """
        )
        retire_older_rollback = text(
            """
            UPDATE llamaindex_retrieval_generations
            SET status = 'retired'
            WHERE status = 'rollback' AND generation_id <> :generation_id
            """
        )
        pointer = text(
            """
            INSERT INTO llamaindex_active_generation (singleton,generation_id,updated_at)
            VALUES (true,:generation_id,now())
            ON CONFLICT(singleton) DO UPDATE
            SET generation_id = excluded.generation_id, updated_at = excluded.updated_at
            """
        )
        async with self._engine.begin() as connection:
            await connection.execute(lock)
            await connection.execute(retire_older_rollback, {"generation_id": generation_id})
            await connection.execute(retire, {"generation_id": generation_id})
            result = await connection.execute(activate, {"generation_id": generation_id})
            result.scalar_one()
            await connection.execute(pointer, {"generation_id": generation_id})

    async def active(self) -> RetrievalGeneration | None:
        """Read the generation selected by the singleton active pointer."""

        query = text(
            """
            SELECT g.generation_id,g.physical_table_name,g.source_fingerprint,
                   g.transform_fingerprint,g.status,g.source_count,g.node_count,
                   g.failure_code,g.created_at,g.verified_at,g.published_at
            FROM llamaindex_retrieval_generations AS g
            JOIN llamaindex_active_generation AS active
              ON active.generation_id = g.generation_id
            """
        )
        async with self._engine.connect() as connection:
            row = (await connection.execute(query)).mappings().one_or_none()
        if row is None:
            return None
        return RetrievalGeneration(
            id=row["generation_id"],
            table_name=row["physical_table_name"],
            source_fingerprint=row["source_fingerprint"],
            transform_fingerprint=row["transform_fingerprint"],
            status=row["status"],
            source_count=row["source_count"],
            node_count=row["node_count"],
            failure_code=row["failure_code"],
            created_at=row["created_at"],
            verified_at=row["verified_at"],
            published_at=row["published_at"],
        )
