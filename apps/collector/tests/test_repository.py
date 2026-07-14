import hashlib
import json
from datetime import date
from uuid import NAMESPACE_URL, uuid5

import pytest
from law_rag_core.domain.catalog import SourceKind
from law_rag_core.domain.entities import LegalDocumentRecord, ProvisionRecord

from law_rag_collector.client import RawResponse
from law_rag_collector.repository import MockCorpusRepository


def _document(raw_body: str = "{}") -> LegalDocumentRecord:
    return LegalDocumentRecord(
        source_id="001",
        mst="1000",
        title="전기사업법",
        source_kind=SourceKind.LAW,
        promulgation_number="제1호",
        promulgated_on=date(2020, 1, 1),
        effective_from=date(2020, 2, 1),
        ministry="산업통상자원부",
        source_url="https://example.test/lawService.do?OC=%5Bredacted%5D",
        raw_format="JSON",
        raw_sha256=hashlib.sha256(raw_body.encode("utf-8")).hexdigest(),
        provisions=[
            ProvisionRecord(
                id=uuid5(NAMESPACE_URL, "test#1"),
                path="제1조",
                heading="목적",
                content="목적 조문",
            )
        ],
    )


def test_mock_repository_is_idempotent_and_reports_status(tmp_path) -> None:
    repository = MockCorpusRepository(tmp_path, today=lambda: date(2026, 7, 14))
    raw = RawResponse("{}", "JSON", "https://example.test?OC=%5Bredacted%5D")

    assert repository.upsert(_document(), raw, effective_to=date(2025, 12, 31)) is True
    assert repository.upsert(_document(), raw, effective_to=date(2025, 12, 31)) is False

    status = repository.status()
    item = next(item for item in status["items"] if item["title"] == "전기사업법")
    assert status["documents"] == 1
    assert item["state"] == "ready"
    assert item["versions"] == 1
    assert "secret" not in (tmp_path / "manifest.json").read_text(encoding="utf-8")


def test_mock_repository_preserves_staged_effective_dates_for_same_mst(tmp_path) -> None:
    repository = MockCorpusRepository(tmp_path, today=lambda: date(2026, 7, 14))
    first_body = json.dumps({"version": "first"})
    second_body = json.dumps({"version": "second"})
    first_raw = RawResponse(
        first_body, "JSON", "https://example.test?OC=%5Bredacted%5D"
    )
    second_raw = RawResponse(
        second_body, "JSON", "https://example.test?OC=%5Bredacted%5D"
    )
    first = _document(first_body)
    second = _document(second_body)
    second.effective_from = date(2020, 3, 1)

    repository.upsert(first, first_raw, effective_to=date(2020, 2, 29))
    repository.upsert(second, second_raw, effective_to=None)

    assert repository.status()["documents"] == 2


def test_failed_validation_keeps_previous_active_manifest(tmp_path) -> None:
    repository = MockCorpusRepository(tmp_path, today=lambda: date(2026, 7, 14))
    raw = RawResponse("{}", "JSON", "https://example.test?OC=%5Bredacted%5D")
    repository.upsert(_document(), raw, effective_to=None)
    previous = repository.manifest_path.read_bytes()
    invalid = _document()
    invalid.effective_from = None

    with pytest.raises(ValueError, match="시행일"):
        repository.upsert(invalid, raw, effective_to=None)

    assert repository.manifest_path.read_bytes() == previous


def test_atomic_manifest_failure_preserves_previous_state(tmp_path, monkeypatch) -> None:
    import law_rag_collector.repository as repository_module

    repository = MockCorpusRepository(tmp_path, today=lambda: date(2026, 7, 14))
    old_raw = RawResponse("{}", "JSON", "https://example.test?OC=%5Bredacted%5D")
    repository.upsert(_document(), old_raw, effective_to=None)
    previous = repository.manifest_path.read_bytes()
    old_manifest = json.loads(previous)
    old_raw_path = tmp_path / next(iter(old_manifest["documents"].values()))["raw_path"]
    actual_replace = repository_module.os.replace

    def fail_manifest_replace(source, destination) -> None:
        if destination == repository.manifest_path:
            raise OSError("simulated interruption")
        actual_replace(source, destination)

    monkeypatch.setattr(repository_module.os, "replace", fail_manifest_replace)
    new_body = '{"changed": true}'
    with pytest.raises(OSError, match="simulated interruption"):
        repository.upsert(
            _document(new_body),
            RawResponse(new_body, "JSON", "https://example.test?OC=%5Bredacted%5D"),
            effective_to=None,
        )

    assert repository.manifest_path.read_bytes() == previous
    assert old_raw_path.read_text(encoding="utf-8") == "{}"
    assert not list(tmp_path.glob(".manifest.json.*.tmp"))
