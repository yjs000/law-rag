"""Request-safe cache for indexes opened from the active generation pointer."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from law_rag_llamaindex.generation.models import RetrievalGeneration


@dataclass(frozen=True)
class ActiveIndex:
    """One index paired with the immutable generation it reads."""

    generation: RetrievalGeneration
    store: Any
    index: Any


class ActiveGenerationIndexProvider:
    """Cache one index per active generation without changing prior pins."""

    def __init__(
        self,
        repository,
        create_store: Callable,
        create_index: Callable,
        *,
        close: Callable[[], Awaitable[None]] | None = None,
    ) -> None:
        self._repository = repository
        self._create_store = create_store
        self._create_index = create_index
        self._close = close
        self._cached: ActiveIndex | None = None

    async def active(self) -> ActiveIndex:
        """Resolve the current pointer once and return an immutable request pin."""

        generation = await self._repository.active()
        if generation is None:
            raise LookupError("no active retrieval generation")
        if self._cached is None or self._cached.generation.id != generation.id:
            store = self._create_store(generation)
            self._cached = ActiveIndex(
                generation=generation,
                store=store,
                index=self._create_index(store),
            )
        return self._cached

    async def aclose(self) -> None:
        """Release the caller-owned database engines, if this provider owns them."""

        if self._close is not None:
            await self._close()
