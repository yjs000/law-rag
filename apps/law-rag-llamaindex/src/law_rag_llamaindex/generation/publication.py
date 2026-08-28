"""In-memory publication policy for immutable retrieval generations."""

from dataclasses import replace
from datetime import UTC, datetime
from uuid import UUID, uuid4

from law_rag_llamaindex.generation.models import RetrievalGeneration, generation_table_name


class GenerationStateError(ValueError):
    """Raised when a generation transition would violate the publish contract."""


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
        for retained in self._generations.values():
            if retained.status == "rollback":
                self._generations[retained.id] = replace(retained, status="retired")
        if self._active_id is not None:
            previous = self.get(self._active_id)
            self._generations[previous.id] = replace(previous, status="rollback")
        published = replace(generation, status="active", published_at=datetime.now(UTC))
        self._generations[generation_id] = published
        self._active_id = generation_id
        return published

    def rollback(self, generation_id: UUID) -> RetrievalGeneration:
        """Restore one retained rollback generation as the active pointer target."""

        generation = self.get(generation_id)
        if generation.status != "rollback":
            raise GenerationStateError("only a retained rollback generation can be restored")
        if self._active_id is not None:
            active = self.get(self._active_id)
            self._generations[active.id] = replace(active, status="rollback")
        restored = replace(generation, status="active", published_at=datetime.now(UTC))
        self._generations[generation_id] = restored
        self._active_id = generation_id
        return restored

    def active(self) -> RetrievalGeneration | None:
        """Return the active generation, if any has been published."""

        return self.get(self._active_id) if self._active_id is not None else None
