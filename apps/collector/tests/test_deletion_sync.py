import json
from datetime import date
from pathlib import Path

import pytest
from law_rag_core.domain.catalog import SourceKind
from law_rag_core.parsers import law_json

from law_rag_collector.client import ParsedResponse, RawResponse
from law_rag_collector.deletions import DeletionRecord
from law_rag_collector.repository import MockCorpusRepository
from law_rag_collector.service import CollectorService

FIXTURES = Path(__file__).parent / "fixtures"


def _seed(repository: MockCorpusRepository) -> None:
    body = (FIXTURES / "law.json").read_text(encoding="utf-8")
    raw = RawResponse(body, "JSON", "https://example.test?OC=%5Bredacted%5D")
    document = law_json.parse_legal_document(
        body,
        expected_title="전기사업법",
        source_kind=SourceKind.LAW,
        source_url=raw.source_url,
    )
    repository.upsert(document, raw, effective_to=None)


class DeletionClient:
    def __init__(self, *, fail_admin: bool = False) -> None:
        self.fail_admin = fail_admin
        self.windows: list[tuple[int, date, date]] = []

    async def deleted_records(self, *, kind, from_date, to_date):
        self.windows.append((kind, from_date, to_date))
        if kind == 2 and self.fail_admin:
            raise RuntimeError("simulated deletion lookup failure")
        records = (
            [DeletionRecord("1001", SourceKind.LAW, "법령", date(2026, 7, 10))]
            if kind == 1
            else []
        )
        return ParsedResponse(
            records,
            RawResponse("{}", "JSON", "https://example.test?OC=%5Bredacted%5D"),
        )


@pytest.mark.asyncio
async def test_weekly_deletion_sync_quarantines_source_record_without_legal_end_date(
    tmp_path,
) -> None:
    repository = MockCorpusRepository(tmp_path, today=lambda: date(2026, 7, 14))
    _seed(repository)
    client = DeletionClient()
    service = CollectorService(client, repository, today=lambda: date(2026, 7, 14))

    first = await service.sync_history(entries=[])
    manifest = json.loads(repository.manifest_path.read_text(encoding="utf-8"))
    document = next(iter(manifest["documents"].values()))
    assert document["lifecycle_state"] == "active"
    assert document["source_record_state"] == "deleted"
    assert document["source_deleted_on"] == "2026-07-10"
    assert document["effective_to"] is None
    assert manifest["deletion_sync"]["completed_on"] == "2026-07-14"
    assert client.windows[:2] == [
        (1, date(2026, 7, 7), date(2026, 7, 14)),
        (2, date(2026, 7, 7), date(2026, 7, 14)),
    ]
    assert first[0].state == "ready"

    second = await service.sync_history(entries=[])
    assert all(item.state == "unchanged" for item in second)
    assert client.windows[2:] == [
        (1, date(2026, 7, 13), date(2026, 7, 14)),
        (2, date(2026, 7, 13), date(2026, 7, 14)),
    ]


@pytest.mark.asyncio
async def test_any_deletion_lookup_failure_preserves_active_document_and_checkpoint(
    tmp_path,
) -> None:
    repository = MockCorpusRepository(tmp_path, today=lambda: date(2026, 7, 14))
    _seed(repository)
    client = DeletionClient(fail_admin=True)
    service = CollectorService(client, repository, today=lambda: date(2026, 7, 14))

    results = await service.sync_history(entries=[])
    manifest = json.loads(repository.manifest_path.read_text(encoding="utf-8"))
    document = next(iter(manifest["documents"].values()))

    assert all(item.state == "failed" for item in results)
    assert document["lifecycle_state"] == "active"
    assert document["source_record_state"] == "available"
    assert document["effective_to"] is None
    assert "deletion_sync" not in manifest
    assert manifest["runs"][-1]["failed"] == 2
