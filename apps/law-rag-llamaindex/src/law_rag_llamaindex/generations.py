"""Immutable v2 retrieval-generation catalog primitives.

The database adapter added in this milestone persists these state transitions.
This module deliberately contains no SQLAlchemy or LlamaIndex dependency so
the publish invariant remains testable without a database.
"""

import hashlib
import json
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine


class GenerationStateError(ValueError):
    """Raised when a generation transition would violate the publish contract."""


@dataclass(frozen=True)
class RetrievalGeneration:
    """A candidate or published immutable vector generation."""

    id: UUID
    table_name: str
    source_fingerprint: str
    transform_fingerprint: str
    status: str
    source_count: int | None
    node_count: int | None
    failure_code: str | None
    created_at: datetime
    verified_at: datetime | None
    published_at: datetime | None


def generation_table_name(generation_id: UUID) -> str:
    """Return the server-derived, SQL-identifier-safe vector table name."""

    return f"law_rag_li_{generation_id.hex}"


def _sha256_json(value: object) -> str:
    encoded = json.dumps(
        value, ensure_ascii=False, separators=(",", ":"), sort_keys=True
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def provision_fingerprint(record: Mapping[str, object]) -> str:
    """Fingerprint every canonical field that can affect search or citation."""

    return _sha256_json(
        {
            "provision_id": record["provision_id"],
            "document_id": record["document_id"],
            "document_title": record["document_title"],
            "source_kind": record["source_kind"],
            "law_type_code": record.get("law_type_code"),
            "version_label": record["version_label"],
            "effective_from": record.get("effective_from"),
            "effective_to": record.get("effective_to"),
            "path": record["path"],
            "heading": record.get("heading"),
            "content": record["content"],
            "source_url": record["source_url"],
        }
    )


def source_fingerprint(records: Iterable[Mapping[str, object]]) -> str:
    """Fingerprint a source snapshot independently of database return order."""

    entries = [
        {"provision_id": str(record["provision_id"]), "fingerprint": provision_fingerprint(record)}
        for record in records
    ]
    return _sha256_json(sorted(entries, key=lambda entry: entry["provision_id"]))


def transform_fingerprint(
    *, chunker_version: str, embedding_provider: str, embedding_model: str, embed_dim: int
) -> str:
    """Fingerprint the transformation contract that defines vector compatibility."""

    if not chunker_version or not embedding_provider or not embedding_model or embed_dim < 1:
        raise ValueError("transform fingerprint requires a complete transformation contract")
    return _sha256_json(
        {
            "chunker_version": chunker_version,
            "embedding_provider": embedding_provider,
            "embedding_model": embedding_model,
            "embed_dim": embed_dim,
        }
    )


class GenerationCatalog:
    """In-memory state model for the generation publish invariant.

    Production persistence must implement the same transitions atomically.
    """

    def __init__(self) -> None:
        self._generations: dict[UUID, RetrievalGeneration] = {}
        self._active_id: UUID | None = None

    def start(self, source_fingerprint: str, transform_fingerprint: str) -> RetrievalGeneration:
        """Register a fresh, unpublished vector generation."""

        generation_id = uuid4()
        generation = RetrievalGeneration(
            id=generation_id,
            table_name=generation_table_name(generation_id),
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
        self._generations[generation_id] = generation
        return generation

    def get(self, generation_id: UUID) -> RetrievalGeneration:
        """Return a registered generation or raise for an unknown identifier."""

        try:
            return self._generations[generation_id]
        except KeyError as exc:
            raise GenerationStateError("unknown generation") from exc

    def verify(
        self, generation_id: UUID, *, source_count: int, node_count: int
    ) -> RetrievalGeneration:
        """Mark a fully validated candidate eligible for publication."""

        if source_count < 0 or node_count < 0:
            raise GenerationStateError("generation counts must be non-negative")
        generation = self.get(generation_id)
        if generation.status != "building":
            raise GenerationStateError("only a building generation can be verified")
        verified = replace(
            generation,
            status="verified",
            source_count=source_count,
            node_count=node_count,
            verified_at=datetime.now(UTC),
        )
        self._generations[generation_id] = verified
        return verified

    def fail(self, generation_id: UUID, failure_code: str) -> RetrievalGeneration:
        """Record an unsuccessful candidate without changing the active pointer."""

        if not failure_code:
            raise GenerationStateError("failure code is required")
        generation = self.get(generation_id)
        if generation.status not in {"building", "verified"}:
            raise GenerationStateError("only an unfinished generation can fail")
        failed = replace(generation, status="failed", failure_code=failure_code)
        self._generations[generation_id] = failed
        return failed

    def publish(self, generation_id: UUID) -> RetrievalGeneration:
        """Atomically model switching the active pointer to a verified generation."""

        generation = self.get(generation_id)
        if generation.status != "verified":
            raise GenerationStateError("generation must be verified before publish")
        if self._active_id is not None:
            previous = self.get(self._active_id)
            self._generations[previous.id] = replace(previous, status="rollback")
        published = replace(generation, status="active", published_at=datetime.now(UTC))
        self._generations[generation_id] = published
        self._active_id = generation_id
        return published

    def active(self) -> RetrievalGeneration | None:
        """Return the active generation, if any has been published."""

        return self.get(self._active_id) if self._active_id is not None else None


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

    async def publish(self, generation_id: UUID) -> None:
        """Switch active pointer only if the candidate has been verified."""

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
        pointer = text(
            """
            INSERT INTO llamaindex_active_generation (singleton,generation_id,updated_at)
            VALUES (true,:generation_id,now())
            ON CONFLICT(singleton) DO UPDATE
            SET generation_id = excluded.generation_id, updated_at = excluded.updated_at
            """
        )
        async with self._engine.begin() as connection:
            result = await connection.execute(activate, {"generation_id": generation_id})
            result.scalar_one()
            await connection.execute(retire_previous, {"generation_id": generation_id})
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
