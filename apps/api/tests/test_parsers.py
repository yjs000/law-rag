import json
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


def test_technical_standard_is_split_by_decimal_sections_not_referenced_articles() -> None:
    body = json.dumps(
        {
            "AdmRulService": {
                "행정규칙명": "전기저장시설의 화재안전성능기준(NFTC 607)",
                "행정규칙ID": "nftc607",
                "행정규칙일련번호": "1",
                "조문내용": (
                    "화재안전기술기준 1.1 적용범위 이 기준은 제11조에 따른다. "
                    "1.2 용어의 정의 저장용량은 12.2 L 이상이다. "
                    "2.1 설치기준 전기저장시설은 방화구획한다."
                ),
            }
        },
        ensure_ascii=False,
    )

    document = parse_json(
        body,
        expected_title="전기저장시설의 화재안전성능기준(NFTC 607)",
        source_kind=SourceKind.ADMIN_RULE,
        source_url="https://example.test",
    )

    assert [provision.path for provision in document.provisions] == [
        "기준1.1",
        "기준1.2",
        "기준2.1",
    ]
    assert "제11조" in document.provisions[0].content
    assert "12.2 L" in document.provisions[1].content
    assert all(len(provision.content) < 100 for provision in document.provisions)


def test_technical_standard_ignores_decimal_section_references() -> None:
    body = json.dumps(
        {
            "AdmRulService": {
                "행정규칙명": "전기저장시설의 화재안전기술기준(NFTC 607)",
                "행정규칙ID": "nftc607",
                "행정규칙일련번호": "2",
                "조문내용": (
                    "1.1 적용범위 세부사항이다.1.2 기준의 효력 세부사항이다."
                    "2.1 소화기 기준이다.2.2 스프링클러설비 기준이다."
                    "2.3 배터리용 소화장치 기준이며 2.2에도 불구하고 적용한다."
                    "2.4 자동화재탐지설비에는 2.2 및 2.3을 적용하지 않을 수 있다."
                ),
            }
        },
        ensure_ascii=False,
    )

    document = parse_json(
        body,
        expected_title="전기저장시설의 화재안전기술기준(NFTC 607)",
        source_kind=SourceKind.ADMIN_RULE,
        source_url="https://example.test",
    )

    assert [provision.path for provision in document.provisions] == [
        "기준1.1",
        "기준1.2",
        "기준2.1",
        "기준2.2",
        "기준2.3",
        "기준2.4",
    ]
