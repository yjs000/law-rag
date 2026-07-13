from datetime import date, datetime
from typing import Protocol
from uuid import UUID

from app.domain.entities import LegalDocumentRecord
from app.domain.schemas import CorpusItemStatus, SearchHit


class LegalRepository(Protocol):
    async def consume_quota(self, subject_hash: str, day: date, kind: str, limit: int) -> bool: ...

    async def upsert_document(self, document: LegalDocumentRecord) -> UUID: ...

    async def upsert_embeddings(
        self, values: list[tuple[UUID, list[float]]], model: str, dimensions: int
    ) -> None: ...

    async def search(
        self,
        query: str,
        as_of_date: date,
        limit: int,
        query_embedding: list[float] | None = None,
    ) -> list[SearchHit]: ...

    async def provision(self, provision_id: UUID, as_of_date: date) -> SearchHit | None: ...

    async def corpus_items(self) -> list[CorpusItemStatus]: ...

    async def last_sync(self) -> datetime | None: ...
