from collections.abc import Callable, Sequence
from datetime import date

from law_rag_core.domain.catalog import MVP_CATALOG, CatalogEntry
from law_rag_core.domain.schemas import IngestionResult

from law_rag_collector.client import LawOpenApiClient, SearchRecord
from law_rag_collector.history import HistoryVersion, effective_periods
from law_rag_collector.repository import MockCorpusRepository


class CollectorService:
    def __init__(
        self,
        client: LawOpenApiClient,
        repository: MockCorpusRepository,
        *,
        today: Callable[[], date] = date.today,
    ) -> None:
        self.client = client
        self.repository = repository
        self._today = today

    async def sync_current(
        self, entries: Sequence[CatalogEntry] = MVP_CATALOG
    ) -> list[IngestionResult]:
        results = [await self._safe_current(entry) for entry in entries]
        self.repository.record_run(
            "sync-current", [item.model_dump(mode="json") for item in results]
        )
        return results

    async def sync_history(
        self, entries: Sequence[CatalogEntry] = MVP_CATALOG
    ) -> list[IngestionResult]:
        results: list[IngestionResult] = []
        for entry in entries:
            try:
                results.extend(await self._history(entry))
            except Exception as exc:
                results.append(
                    IngestionResult(title=entry.title, state="failed", detail=_safe_detail(exc))
                )
        results.extend(await self._sync_deletions())
        self.repository.record_run(
            "sync-history", [item.model_dump(mode="json") for item in results]
        )
        return results

    async def _sync_deletions(self) -> list[IngestionResult]:
        today = self._today()
        from_date, to_date = self.repository.deletion_window(today=today)
        responses = {}
        failures = {}
        for kind, label in ((1, "법령"), (2, "행정규칙")):
            try:
                responses[kind] = await self.client.deleted_records(
                    kind=kind, from_date=from_date, to_date=to_date
                )
            except Exception as exc:
                failures[kind] = IngestionResult(
                    title=f"삭제 데이터({label})",
                    state="failed",
                    detail=_safe_detail(exc),
                )
        if failures:
            return [
                failures.get(kind)
                or IngestionResult(
                    title=f"삭제 데이터({label})",
                    state="failed",
                    detail="다른 삭제 목록 조회 실패로 활성 manifest를 보존했습니다",
                )
                for kind, label in ((1, "법령"), (2, "행정규칙"))
            ]

        records = [record for response in responses.values() for record in response.value]
        try:
            stats = self.repository.apply_source_deletions(records, completed_on=to_date)
        except Exception as exc:
            detail = _safe_detail(exc)
            return [
                IngestionResult(
                    title=f"삭제 데이터({label})",
                    state="failed",
                    detail=f"활성 manifest 원자 반영 실패: {detail}",
                )
                for label in ("법령", "행정규칙")
            ]
        results: list[IngestionResult] = []
        for kind, label, source_kind in (
            (1, "법령", "law"),
            (2, "행정규칙", "administrative_rule"),
        ):
            response = responses[kind]
            changed = stats[source_kind]["changed"]
            matched = stats[source_kind]["matched"]
            results.append(
                IngestionResult(
                    title=f"삭제 데이터({label})",
                    state="ready" if changed else "unchanged",
                    wire_format=response.raw.wire_format,
                    fallback_reason=response.raw.fallback_reason,
                    detail=(
                        f"조회 {len(response.value)}건, "
                        f"허용 코퍼스 {matched}건, 변경 {changed}건"
                    ),
                )
            )
        return results

    async def _safe_current(self, entry: CatalogEntry) -> IngestionResult:
        try:
            search_item = await self._exact_search(entry)
            parsed = await self.client.document(
                expected_title=entry.title,
                source_kind=entry.source_kind,
                source_id=search_item.source_id,
                mst=search_item.mst,
                historical=False,
            )
            changed = self.repository.upsert(parsed.value, parsed.raw, effective_to=None)
            return IngestionResult(
                title=entry.title,
                state="ready" if changed else "unchanged",
                wire_format=parsed.raw.wire_format,
                fallback_reason=parsed.raw.fallback_reason,
                source_id=parsed.value.source_id,
                mst=parsed.value.mst,
            )
        except Exception as exc:
            return IngestionResult(title=entry.title, state="failed", detail=_safe_detail(exc))

    async def _history(self, entry: CatalogEntry) -> list[IngestionResult]:
        current = await self._exact_search(entry)
        response = await self.client.history(
            exact_title=entry.title,
            source_kind=entry.source_kind,
            source_id=current.source_id,
        )
        versions = _merge_current(response.value, current)
        periods = effective_periods(versions)
        results: list[IngestionResult] = []
        for period in periods:
            parsed = await self.client.document(
                expected_title=entry.title,
                source_kind=entry.source_kind,
                source_id=period.source_id or current.source_id,
                mst=period.mst,
                historical=period.mst != current.mst,
                effective_date=period.effective_from,
            )
            # eflaw는 최신 MST 본문을 과거 efYd로 조회할 수 있어 본문 메타데이터의
            # 시행일과 조회 스냅샷 시작일이 다를 수 있다. 효력 경계는 목록의 efYd가 권위다.
            parsed.value.effective_from = period.effective_from
            changed = self.repository.upsert(
                parsed.value,
                parsed.raw,
                effective_to=period.effective_to,
            )
            results.append(
                IngestionResult(
                    title=entry.title,
                    state="ready" if changed else "unchanged",
                    wire_format=parsed.raw.wire_format,
                    fallback_reason=parsed.raw.fallback_reason,
                    source_id=parsed.value.source_id,
                    mst=parsed.value.mst,
                )
            )
        return results

    async def _exact_search(self, entry: CatalogEntry) -> SearchRecord:
        response = await self.client.search(entry.title, entry.source_kind)
        exact = [item for item in response.value if item.title == entry.title]
        if len(exact) != 1:
            raise ValueError(f"정확 명칭 검색 결과가 {len(exact)}건입니다")
        item = exact[0]
        if not item.mst or not item.source_id:
            raise ValueError("검색 결과에 source_id 또는 MST가 없습니다")
        return item


def _merge_current(history: list[HistoryVersion], current: SearchRecord) -> list[HistoryVersion]:
    by_version = {(item.mst, item.effective_from): item for item in history}
    current_date = _date(current.effective_date)
    current_key = (current.mst, current_date)
    existing = by_version.get(current_key)
    if existing:
        by_version[current_key] = HistoryVersion(
            source_id=existing.source_id or current.source_id,
            mst=existing.mst,
            effective_from=existing.effective_from or current_date,
            promulgated_on=existing.promulgated_on,
        )
    else:
        by_version[current_key] = HistoryVersion(current.source_id, current.mst, current_date)
    return list(by_version.values())


def _date(value: str) -> date | None:
    digits = "".join(character for character in value if character.isdigit())
    if len(digits) != 8:
        return None
    return date(int(digits[:4]), int(digits[4:6]), int(digits[6:]))


def _safe_detail(exc: Exception) -> str:
    message = str(exc).replace("\r", " ").replace("\n", " ").strip()
    return f"{type(exc).__name__}: {message}"[:300]
