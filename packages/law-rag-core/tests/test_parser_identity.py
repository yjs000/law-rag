import json
from datetime import date
from uuid import UUID

import pytest

from law_rag_core.domain.catalog import SourceKind
from law_rag_core.domain.entities import LegalDocumentRecord
from law_rag_core.domain.identifiers import canonical_provision_id
from law_rag_core.parsers.law_json import parse_legal_document as parse_json
from law_rag_core.parsers.law_xml import parse_legal_document as parse_xml


def _json_body(*, effective_from: str = "20260201") -> str:
    return json.dumps(
        {
            "법령": {
                "기본정보": {
                    "법령ID": "001",
                    "법령일련번호": "1001",
                    "법령명_한글": "전기사업법",
                    "시행일자": effective_from,
                },
                "조문": {
                    "조문단위": {
                        "조문번호": "1",
                        "조문제목": "목적",
                        "조문내용": "제1조(목적) 전기사업의 기본제도를 정한다.",
                        "항": {
                            "항번호": "①",
                            "항내용": "전기사업자는 이 법을 준수하여야 한다.",
                            "호": {
                                "호번호": "1.",
                                "호내용": "1. 전기사업의 허가",
                                "목": {"목번호": "가.", "목내용": "가. 발전사업"},
                            },
                        },
                    }
                },
            }
        },
        ensure_ascii=False,
    )


def _xml_body(*, effective_from: str = "20260201") -> str:
    return f"""\
<법령><기본정보><법령ID>001</법령ID><법령일련번호>1001</법령일련번호>
<법령명_한글>전기사업법</법령명_한글><시행일자>{effective_from}</시행일자></기본정보>
<조문><조문단위><조문번호>1</조문번호><조문제목>목적</조문제목>
<조문내용>제1조(목적) 전기사업의 기본제도를 정한다.</조문내용>
<항><항번호>①</항번호><항내용>전기사업자는 이 법을 준수하여야 한다.</항내용>
<호><호번호>1.</호번호><호내용>1. 전기사업의 허가</호내용>
<목><목번호>가.</목번호><목내용>가. 발전사업</목내용></목></호></항>
</조문단위></조문></법령>"""


def _normalized_provisions(document: LegalDocumentRecord) -> list[tuple[object, ...]]:
    return [
        (
            item.id,
            item.path,
            item.heading,
            item.content,
            item.parent_path,
            item.ordinal,
        )
        for item in document.provisions
    ]


def test_json_and_xml_share_schema_v3_provision_identity_and_structure() -> None:
    json_document = parse_json(
        _json_body(),
        expected_title="전기사업법",
        source_kind=SourceKind.LAW,
        source_url="https://example.test/json",
    )
    xml_document = parse_xml(
        _xml_body(),
        expected_title="전기사업법",
        source_kind=SourceKind.LAW,
        source_url="https://example.test/xml",
    )

    assert json_document.parser_schema_version == "3"
    assert xml_document.parser_schema_version == "3"
    assert _normalized_provisions(json_document) == _normalized_provisions(xml_document)
    assert [item.path for item in json_document.provisions] == [
        "제1조",
        "제1조/항①",
        "제1조/항①/호1.",
        "제1조/항①/호1./목가.",
    ]
    assert [item.parent_path for item in json_document.provisions] == [
        None,
        "제1조",
        "제1조/항①",
        "제1조/항①/호1.",
    ]
    assert str(json_document.provisions[0].id) == "10c50843-75b4-55df-b538-6821ed095e78"


@pytest.mark.parametrize(
    "alternate",
    [
        pytest.param(
            canonical_provision_id(
                source_kind=SourceKind.ADMIN_RULE,
                source_id="001",
                mst="1001",
                effective_from=date(2026, 2, 1),
                path="제1조",
            ),
            id="source-kind",
        ),
        pytest.param(
            canonical_provision_id(
                source_kind=SourceKind.LAW,
                source_id="002",
                mst="1001",
                effective_from=date(2026, 2, 1),
                path="제1조",
            ),
            id="source-id",
        ),
        pytest.param(
            canonical_provision_id(
                source_kind=SourceKind.LAW,
                source_id="001",
                mst="1002",
                effective_from=date(2026, 2, 1),
                path="제1조",
            ),
            id="mst",
        ),
        pytest.param(
            canonical_provision_id(
                source_kind=SourceKind.LAW,
                source_id="001",
                mst="1001",
                effective_from=date(2026, 2, 2),
                path="제1조",
            ),
            id="effective-from",
        ),
        pytest.param(
            canonical_provision_id(
                source_kind=SourceKind.LAW,
                source_id="001",
                mst="1001",
                effective_from=date(2026, 2, 1),
                path="제2조",
            ),
            id="path",
        ),
    ],
)
def test_every_schema_v3_identity_component_changes_the_uuid(alternate: UUID) -> None:
    expected = canonical_provision_id(
        source_kind=SourceKind.LAW,
        source_id="001",
        mst="1001",
        effective_from=date(2026, 2, 1),
        path="제1조",
    )

    assert alternate != expected


def test_same_mst_and_path_on_different_effective_dates_get_distinct_ids() -> None:
    first = parse_json(
        _json_body(effective_from="20260201"),
        expected_title="전기사업법",
        source_kind=SourceKind.LAW,
        source_url="https://example.test/first",
    )
    second = parse_json(
        _json_body(effective_from="20260301"),
        expected_title="전기사업법",
        source_kind=SourceKind.LAW,
        source_url="https://example.test/second",
    )

    assert first.mst == second.mst
    assert first.provisions[0].path == second.provisions[0].path
    assert first.provisions[0].id != second.provisions[0].id


@pytest.mark.parametrize(
    ("parser", "body"),
    [(parse_json, _json_body()), (parse_xml, _xml_body())],
)
def test_effective_date_override_controls_record_and_provision_identity(parser, body) -> None:
    authoritative_date = date(2026, 3, 1)

    document = parser(
        body,
        expected_title="전기사업법",
        source_kind=SourceKind.LAW,
        source_url="https://example.test/history",
        effective_from_override=authoritative_date,
    )

    assert document.effective_from == authoritative_date
    assert document.provisions[0].id == canonical_provision_id(
        source_kind=SourceKind.LAW,
        source_id=document.source_id,
        mst=document.mst,
        effective_from=authoritative_date,
        path=document.provisions[0].path,
    )


def test_flat_subitem_groups_ignore_items_that_only_reference_other_subitems() -> None:
    body = json.dumps(
        {
            "법령": {
                "기본정보": {
                    "법령ID": "001",
                    "법령일련번호": "1001",
                    "법령명_한글": "전기사업법 시행령",
                    "시행일자": "20260102",
                },
                "조문": {
                    "조문단위": {
                        "조문번호": "5",
                        "조문제목": "평탄화 목 복원",
                        "조문내용": "제5조(평탄화 목 복원) 상위 호를 복원한다.",
                        "항": {
                            "항번호": "①",
                            "항내용": "① 다음 각 호를 따른다.",
                            "호": [
                                {
                                    "호번호": "1.",
                                    "호내용": "1. 다음 각 목의 어느 하나에 해당하는 자",
                                },
                                {"호번호": "2.", "호내용": "2. 다른 요건"},
                                {
                                    "호번호": "3.",
                                    "호내용": "3. 다음 각 목의 어느 하나에 해당하는 방법",
                                },
                                {
                                    "호번호": "4.",
                                    "호내용": "4. 제3호 각 목의 방법을 통한 지배",
                                },
                            ],
                            "목": [
                                {"목번호": "가.", "목내용": "가. 첫 그룹 가목"},
                                {"목번호": "나.", "목내용": "나. 첫 그룹 나목"},
                                {"목번호": "가.", "목내용": "가. 둘째 그룹 가목"},
                                {"목번호": "나.", "목내용": "나. 둘째 그룹 나목"},
                                {"목번호": "다.", "목내용": "다. 둘째 그룹 다목"},
                            ],
                        },
                    }
                },
            }
        },
        ensure_ascii=False,
    )

    document = parse_json(
        body,
        expected_title="전기사업법 시행령",
        source_kind=SourceKind.LAW,
        source_url="https://example.test/flattened",
    )

    subitems = [item for item in document.provisions if "/목" in item.path]
    assert [(item.path, item.parent_path) for item in subitems] == [
        ("제5조/항①/호1./목가.", "제5조/항①/호1."),
        ("제5조/항①/호1./목나.", "제5조/항①/호1."),
        ("제5조/항①/호3./목가.", "제5조/항①/호3."),
        ("제5조/항①/호3./목나.", "제5조/항①/호3."),
        ("제5조/항①/호3./목다.", "제5조/항①/호3."),
    ]


def _json_body_with_law_type(*, law_type: str, law_type_code: str) -> str:
    return json.dumps(
        {
            "법령": {
                "기본정보": {
                    "법령ID": "001",
                    "법령일련번호": "1001",
                    "법령명_한글": "전기사업법",
                    "시행일자": "20260201",
                    "법종구분": {"content": law_type},
                    "법종구분코드": law_type_code,
                },
                "조문": {
                    "조문단위": {
                        "조문번호": "1",
                        "조문내용": "제1조(목적) 전기사업의 기본제도를 정한다.",
                    }
                },
            }
        },
        ensure_ascii=False,
    )


def _xml_body_with_law_type(*, law_type: str, law_type_code: str) -> str:
    return f"""\
<법령><기본정보><법령ID>001</법령ID><법령일련번호>1001</법령일련번호>
<법령명_한글>전기사업법</법령명_한글><시행일자>20260201</시행일자>
<법종구분>{law_type}</법종구분><법종구분코드>{law_type_code}</법종구분코드></기본정보>
<조문><조문단위><조문번호>1</조문번호>
<조문내용>제1조(목적) 전기사업의 기본제도를 정한다.</조문내용>
</조문단위></조문></법령>"""


def test_json_and_xml_parsers_extract_law_type_classification() -> None:
    json_document = parse_json(
        _json_body_with_law_type(law_type="법률", law_type_code="01"),
        expected_title="전기사업법",
        source_kind=SourceKind.LAW,
        source_url="https://example.test/law-type-json",
    )
    xml_document = parse_xml(
        _xml_body_with_law_type(law_type="법률", law_type_code="01"),
        expected_title="전기사업법",
        source_kind=SourceKind.LAW,
        source_url="https://example.test/law-type-xml",
    )

    assert json_document.law_type_name == "법률"
    assert json_document.law_type_code == "01"
    assert xml_document.law_type_name == "법률"
    assert xml_document.law_type_code == "01"


def _admrul_json_body(*, kind_name: str, kind_code: str) -> str:
    return json.dumps(
        {
            "AdmRulService": {
                "행정규칙ID": "900",
                "행정규칙일련번호": "9001",
                "행정규칙명": "전기설비 기술기준",
                "시행일자": "20260201",
                "행정규칙종류": kind_name,
                "행정규칙종류코드": kind_code,
                "조문내용": ["제1조(목적) 이 규칙은 안전을 위해 제정한다."],
            }
        },
        ensure_ascii=False,
    )


def test_json_parser_extracts_administrative_rule_type_classification() -> None:
    document = parse_json(
        _admrul_json_body(kind_name="예규", kind_code="03"),
        expected_title="전기설비 기술기준",
        source_kind=SourceKind.ADMIN_RULE,
        source_url="https://example.test/admrul-json",
    )

    assert document.law_type_name == "예규"
    assert document.law_type_code == "03"


def test_law_type_fields_are_none_when_absent() -> None:
    document = parse_json(
        _json_body(),
        expected_title="전기사업법",
        source_kind=SourceKind.LAW,
        source_url="https://example.test/no-law-type",
    )

    assert document.law_type_name is None
    assert document.law_type_code is None
