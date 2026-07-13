from pathlib import Path

import pytest

from app.domain.catalog import SourceKind
from app.parsers.law_json import LawJsonParseError
from app.parsers.law_json import parse_legal_document as parse_json
from app.parsers.law_xml import LawXmlParseError
from app.parsers.law_xml import parse_legal_document as parse_xml

FIXTURES = Path(__file__).parent / "fixtures"


def test_json_and_xml_normalize_to_equivalent_core_document() -> None:
    json_doc = parse_json(
        (FIXTURES / "law.json").read_text(encoding="utf-8"),
        expected_title="전기사업법",
        source_kind=SourceKind.LAW,
        source_url="https://example.test/json",
    )
    xml_doc = parse_xml(
        (FIXTURES / "law.xml").read_text(encoding="utf-8"),
        expected_title="전기사업법",
        source_kind=SourceKind.LAW,
        source_url="https://example.test/xml",
    )
    assert (json_doc.source_id, json_doc.mst, json_doc.title) == (
        xml_doc.source_id,
        xml_doc.mst,
        xml_doc.title,
    )
    assert [(p.path, p.content) for p in json_doc.provisions] == [
        (p.path, p.content) for p in xml_doc.provisions
    ]
    assert json_doc.raw_format == "JSON"
    assert xml_doc.raw_format == "XML"


@pytest.mark.parametrize(
    "parser,error", [(parse_json, LawJsonParseError), (parse_xml, LawXmlParseError)]
)
def test_exact_allowlist_title_is_enforced(parser, error) -> None:
    suffix = "json" if parser is parse_json else "xml"
    with pytest.raises(error, match="허용 목록 제목 불일치"):
        parser(
            (FIXTURES / f"law.{suffix}").read_text(encoding="utf-8"),
            expected_title="다른 법령",
            source_kind=SourceKind.LAW,
            source_url="https://example.test",
        )


def test_admin_rule_json_sections_get_stable_article_paths() -> None:
    document = parse_json(
        (FIXTURES / "admin_rule.json").read_text(encoding="utf-8"),
        expected_title="전기저장시설의 화재안전성능기준(NFPC 607)",
        source_kind=SourceKind.ADMIN_RULE,
        source_url="https://example.test",
    )
    assert [provision.path for provision in document.provisions] == ["제1조", "제2조"]
