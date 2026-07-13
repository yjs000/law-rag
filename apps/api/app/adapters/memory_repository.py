import re
from datetime import UTC, date, datetime
from uuid import NAMESPACE_URL, UUID, uuid5

from app.domain.catalog import MVP_CATALOG
from app.domain.entities import LegalDocumentRecord
from app.domain.schemas import CorpusItemStatus, SearchHit


class MemoryLegalRepository:
    def __init__(self) -> None:
        self._documents: dict[tuple[str, str, str], LegalDocumentRecord] = {}
        self._document_ids: dict[tuple[str, str, str], UUID] = {}
        self._last_sync: datetime | None = None
        self._usage: dict[tuple[str, date, str], int] = {}

    async def consume_quota(self, subject_hash: str, day: date, kind: str, limit: int) -> bool:
        key = (subject_hash, day, kind)
        used = self._usage.get(key, 0)
        if used >= limit:
            return False
        self._usage[key] = used + 1
        return True

    async def upsert_document(self, document: LegalDocumentRecord) -> UUID:
        key = (document.source_kind.value, document.source_id, document.mst)
        document_id = uuid5(
            NAMESPACE_URL,
            f"law.go.kr:{document.source_kind.value}:{document.source_id}:{document.mst}",
        )
        self._documents[key] = document
        self._document_ids[key] = document_id
        self._last_sync = datetime.now(UTC)
        return document_id

    async def upsert_embeddings(
        self, values: list[tuple[UUID, list[float]]], model: str, dimensions: int
    ) -> None:
        return None

    async def search(
        self,
        query: str,
        as_of_date: date,
        limit: int,
        query_embedding: list[float] | None = None,
    ) -> list[SearchHit]:
        terms = {
            term.casefold() for term in re.findall(r"[가-힣A-Za-z0-9]+", query) if len(term) > 1
        }
        hits: list[SearchHit] = []
        for key, document in self._documents.items():
            if document.effective_from and document.effective_from > as_of_date:
                continue
            for provision in document.provisions:
                haystack = (
                    f"{document.title} {provision.heading or ''} {provision.content}".casefold()
                )
                matched = sum(1 for term in terms if term in haystack)
                if not matched:
                    continue
                hits.append(
                    SearchHit(
                        provision_id=provision.id,
                        document_id=self._document_ids[key],
                        document_title=document.title,
                        source_kind=document.source_kind,
                        version_label=f"MST {document.mst}",
                        effective_from=document.effective_from,
                        effective_to=None,
                        path=provision.path,
                        heading=provision.heading,
                        content=provision.content,
                        source_url=document.source_url,
                        score=matched / max(len(terms), 1),
                    )
                )
        return sorted(hits, key=lambda hit: (-hit.score, hit.document_title, hit.path))[:limit]

    async def provision(self, provision_id: UUID, as_of_date: date) -> SearchHit | None:
        for key, document in self._documents.items():
            if document.effective_from and document.effective_from > as_of_date:
                continue
            for provision in document.provisions:
                if provision.id == provision_id:
                    return SearchHit(
                        provision_id=provision.id,
                        document_id=self._document_ids[key],
                        document_title=document.title,
                        source_kind=document.source_kind,
                        version_label=f"MST {document.mst}",
                        effective_from=document.effective_from,
                        effective_to=None,
                        path=provision.path,
                        heading=provision.heading,
                        content=provision.content,
                        source_url=document.source_url,
                        score=1,
                    )
        return None

    async def corpus_items(self) -> list[CorpusItemStatus]:
        by_title = {document.title: document for document in self._documents.values()}
        return [
            CorpusItemStatus(
                title=entry.title,
                source_kind=entry.source_kind,
                state="ready" if entry.title in by_title else "missing",
                latest_effective_date=by_title[entry.title].effective_from
                if entry.title in by_title
                else None,
            )
            for entry in MVP_CATALOG
        ]

    async def last_sync(self) -> datetime | None:
        return self._last_sync


repository = MemoryLegalRepository()
