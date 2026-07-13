from dataclasses import dataclass

from app.clients.law_open_api import LawOpenApiClient
from app.domain.catalog import MVP_CATALOG, CatalogEntry, SourceKind
from app.ports.repository import LegalRepository


@dataclass(slots=True)
class IngestionResult:
    title: str
    state: str
    wire_format: str | None = None
    fallback_reason: str | None = None
    detail: str | None = None


class IngestionService:
    def __init__(
        self, client: LawOpenApiClient, repository: LegalRepository, embedder=None, raw_storage=None
    ) -> None:
        self.client = client
        self.repository = repository
        self.embedder = embedder
        self.raw_storage = raw_storage

    async def ingest_entry(self, entry: CatalogEntry) -> IngestionResult:
        search = (
            await self.client.search_current_law(entry.title)
            if entry.source_kind is SourceKind.LAW
            else await self.client.search_admin_rule(entry.title)
        )
        exact = [item for item in search.value if item.title == entry.title]
        if len(exact) != 1:
            return IngestionResult(entry.title, "failed", detail=f"정확 명칭 결과 {len(exact)}건")
        item = exact[0]
        parsed = await self.client.get_document(
            expected_title=entry.title,
            source_kind=entry.source_kind,
            source_id=item.source_id,
            mst=item.mst or None,
        )
        if self.raw_storage:
            extension = parsed.raw.wire_format.lower()
            parsed.value.raw_storage_path = await self.raw_storage.put(
                f"{entry.source_kind.value}/{item.source_id}/{item.mst}.{extension}",
                parsed.raw.body,
                parsed.raw.wire_format,
            )
        await self.repository.upsert_document(parsed.value)
        if self.embedder:
            provisions = parsed.value.provisions
            embeddings = await self.embedder.embed(
                [
                    f"{parsed.value.title} {item.path} {item.heading or ''} {item.content}"
                    for item in provisions
                ]
            )
            await self.repository.upsert_embeddings(
                [(item.id, vector) for item, vector in zip(provisions, embeddings, strict=True)],
                self.embedder.model,
                self.embedder.dimensions,
            )
        return IngestionResult(
            entry.title,
            "ready",
            parsed.raw.wire_format,
            parsed.raw.fallback_reason,
        )

    async def ingest_mvp(self) -> list[IngestionResult]:
        results: list[IngestionResult] = []
        for entry in MVP_CATALOG:
            try:
                results.append(await self.ingest_entry(entry))
            except Exception as exc:  # 경계에서 비밀/원문 없이 실패 유형만 기록한다.
                results.append(IngestionResult(entry.title, "failed", detail=type(exc).__name__))
        return results
