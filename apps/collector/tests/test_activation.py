import json
from datetime import date
from pathlib import Path
from uuid import uuid4

import pytest
from law_rag_core.domain.catalog import SourceKind
from law_rag_core.domain.entities import ProvisionRecord
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


def test_noncanonical_provision_id_blocks_activation() -> None:
    document, raw = _json_document("law-deleted.json")
    document.provisions[0].id = uuid4()

    with pytest.raises(ValueError, match="정규 UUID"):
        validate_for_activation(document, raw, today=date(2026, 7, 14))


def test_old_parser_schema_blocks_activation() -> None:
    document, raw = _json_document("law-deleted.json")
    document.parser_schema_version = "2"

    with pytest.raises(ValueError, match="파서 스키마"):
        validate_for_activation(document, raw, today=date(2026, 7, 14))


def test_structure_marker_cannot_replace_article_body() -> None:
    document, raw = _json_document("law-deleted.json")
    document.provisions[0].content = "제1장 총칙"

    with pytest.raises(ValueError, match="구조 표지"):
        validate_for_activation(document, raw, today=date(2026, 7, 14))


def test_missing_parent_path_blocks_activation() -> None:
    document, raw = _json_document("law-deleted.json")
    document.provisions.append(
        ProvisionRecord(
            id=uuid4(),
            path=f"{document.provisions[0].path}/항①",
            heading=None,
            content="① 하위 조문",
            parent_path="제999조",
            ordinal=1,
        )
    )

    with pytest.raises(ValueError, match="상위 조문 경로"):
        validate_for_activation(document, raw, today=date(2026, 7, 14))


def test_parent_path_cannot_cross_article_boundary() -> None:
    document, raw = _json_document("law-deleted.json")
    first_path = document.provisions[0].path
    document.provisions.extend(
        [
            ProvisionRecord(
                id=uuid4(),
                path="제2조",
                heading=None,
                content="제2조 실제 본문",
                parent_path=None,
                ordinal=1,
            ),
            ProvisionRecord(
                id=uuid4(),
                path=f"{first_path}/항①",
                heading=None,
                content="① 하위 조문",
                parent_path="제2조",
                ordinal=2,
            ),
        ]
    )

    with pytest.raises(ValueError, match="다른 조문"):
        validate_for_activation(document, raw, today=date(2026, 7, 14))
