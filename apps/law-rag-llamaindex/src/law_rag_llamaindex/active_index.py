"""Request-safe cache for indexes opened from the active generation pointer."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from law_rag_llamaindex.generations import RetrievalGeneration


@dataclass(frozen=True)
class ActiveIndex:
    """One index paired with the immutable generation it reads."""

    generation: RetrievalGeneration
    index: Any


class ActiveGenerationIndexProvider:
    """Cache one index per active generation without changing prior pins."""

    def __init__(self, repository, create_store: Callable, create_index: Callable) -> None:
        self._repository = repository
        self._create_store = create_store
        self._create_index = create_index
        self._cached: ActiveIndex | None = None

    async def active(self) -> ActiveIndex:
        """Resolve the current pointer once and return an immutable request pin."""

        generation = await self._repository.active()
        if generation is None:
            raise LookupError("no active retrieval generation")
        if self._cached is None or self._cached.generation.id != generation.id:
            self._cached = ActiveIndex(
                generation=generation,
                index=self._create_index(self._create_store(generation)),
            )
        return self._cached
