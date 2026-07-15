from datetime import date
from pathlib import Path

import pytest
from law_rag_core.domain.catalog import SourceKind

from law_rag_collector.deletions import parse_deletions_json, parse_deletions_xml

FIXTURES = Path(__file__).parent / "fixtures"


def test_json_and_xml_deletion_contracts_match() -> None:
    json_page = parse_deletions_json((FIXTURES / "deletions.json").read_text(encoding="utf-8"), 1)
    xml_page = parse_deletions_xml((FIXTURES / "deletions.xml").read_text(encoding="utf-8"), 1)

    assert json_page == xml_page
    assert json_page.total_count == 2
    assert json_page.records[0].mst == "1001"
    assert json_page.records[0].source_kind is SourceKind.LAW
    assert json_page.records[0].deleted_on == date(2026, 7, 10)


def test_empty_deletion_page_is_valid() -> None:
    page = parse_deletions_json((FIXTURES / "deletions-empty.json").read_text(encoding="utf-8"), 1)
    assert page.total_count == 0
    assert page.records == []


def test_administrative_rule_kind_is_mapped() -> None:
    page = parse_deletions_json(
        """{
          "DataService": {
            "target": "delHst", "totalCnt": 1, "page": 1,
            "law": [{"일련번호": "2001", "구분명": "행정규칙", "삭제일자": "20260712"}]
          }
        }""",
        2,
    )
    assert page.records[0].source_kind is SourceKind.ADMIN_RULE


def test_wrong_kind_or_missing_page_fields_are_rejected() -> None:
    body = (FIXTURES / "deletions.json").read_text(encoding="utf-8")
    with pytest.raises(ValueError, match="구분명"):
        parse_deletions_json(body, 2)
    with pytest.raises(ValueError, match="페이지"):
        parse_deletions_json('{"target": "delHst", "law": []}', 1)
    with pytest.raises(ValueError, match="페이지 번호"):
        parse_deletions_json(body, 1, expected_page=2)
