import inspect
from collections.abc import Awaitable
from datetime import date
from typing import Any, Protocol

from law_rag_core.domain.entities import LegalDocumentRecord

from law_rag_collector.client import RawResponse
from law_rag_collector.deletions import DeletionRecord


async def resolve[T](value: T | Awaitable[T]) -> T:
    return await value if inspect.isawaitable(value) else value


class CollectorRepository(Protocol):
    def upsert(
        self,
        document: LegalDocumentRecord,
        raw: RawResponse,
        *,
        effective_to: date | None,
    ) -> bool | Awaitable[bool]: ...

    def record_run(self, command: str, results: list[dict[str, Any]]) -> None | Awaitable[None]: ...

    def deletion_window(
        self, *, today: date
    ) -> tuple[date, date] | Awaitable[tuple[date, date]]: ...

    def apply_source_deletions(
        self, records: list[DeletionRecord], *, completed_on: date
    ) -> dict[str, dict[str, int]] | Awaitable[dict[str, dict[str, int]]]: ...

    def status(self) -> dict[str, Any] | Awaitable[dict[str, Any]]: ...
