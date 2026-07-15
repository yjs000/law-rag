import json
from datetime import date
from pathlib import Path

import pytest
from law_rag_core.domain.catalog import SourceKind
from law_rag_core.parsers import law_json, law_xml

from law_rag_collector.activation import validate_for_activation
from law_rag_collector.client import RawResponse
from law_rag_collector.repository import MockCorpusRepository

FIXTURES = Path(__file__).parent / "fixtures"


def _json_document(name: str):
    body = (FIXTURES / name).read_text(encoding="utf-8")
    raw = RawResponse(body, "JSON", "https://example.test?OC=%5Bredacted%5D")
    document = law_json.parse_legal_document(
        body,
        expected_title="전기사업법",
        source_kind=SourceKind.LAW,
        source_url=raw.source_url,
    )
    return document, raw


def test_branch_supplement_future_and_missing_optional_fields_are_preserved(tmp_path) -> None:
    document, raw = _json_document("law-boundaries.json")

    metadata = validate_for_activation(document, raw, today=date(2026, 7, 14))

    assert [item.path for item in document.provisions] == ["제2조의2"]
    assert document.ministry is None  # 소관부처는 선택 필드다.
    assert metadata.has_supplementary_provisions is True
    assert metadata.lifecycle_state == "scheduled"
    assert metadata.source_record_state == "available"

    repository = MockCorpusRepository(tmp_path, today=lambda: date(2026, 7, 14))
    assert repository.upsert(document, raw, effective_to=None) is True
    manifest = json.loads(repository.manifest_path.read_text(encoding="utf-8"))
    active = next(iter(manifest["documents"].values()))
    assert active["lifecycle_state"] == "scheduled"
    assert active["source_record_state"] == "available"
    assert active["has_supplementary_provisions"] is True
    assert document.raw_sha256 in active["raw_path"]


def test_source_deleted_and_legally_abolished_markers_are_separate() -> None:
    deleted, deleted_raw = _json_document("law-deleted.json")
    deleted_metadata = validate_for_activation(deleted, deleted_raw, today=date(2026, 7, 14))
    assert deleted_metadata.lifecycle_state == "active"
    assert deleted_metadata.source_record_state == "deleted"

    body = (FIXTURES / "law-abolished.xml").read_text(encoding="utf-8")
    raw = RawResponse(body, "XML", "https://example.test?OC=%5Bredacted%5D")
    abolished = law_xml.parse_legal_document(
        body,
        expected_title="전기사업법",
        source_kind=SourceKind.LAW,
        source_url=raw.source_url,
    )
    abolished_metadata = validate_for_activation(abolished, raw, today=date(2026, 7, 14))
    assert abolished_metadata.lifecycle_state == "abolished"
    assert abolished_metadata.source_record_state == "available"


def test_missing_critical_effective_date_blocks_activation() -> None:
    document, raw = _json_document("law-missing-critical.json")
    with pytest.raises(ValueError, match="시행일"):
        validate_for_activation(document, raw, today=date(2026, 7, 14))


def test_raw_hash_mismatch_blocks_activation() -> None:
    document, raw = _json_document("law-deleted.json")
    document.raw_sha256 = "0" * 64
    with pytest.raises(ValueError, match="SHA-256"):
        validate_for_activation(document, raw, today=date(2026, 7, 14))
