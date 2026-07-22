import hashlib
from pathlib import Path

import pytest

from experiments.chunking.text_fixture_adapter import TextFixtureError, adapt_text_fixture
from law_rag_core.parsers.law_json import parse_legal_document


FIXTURE = (
    Path(__file__).parents[1] / "fixtures" / "electric-utility-act-chapter-2.txt"
)


def _parse(text: str, title: str = "전기사업법"):
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    adapted = adapt_text_fixture(text, document_title=title, input_sha256=digest)
    document = parse_legal_document(
        adapted.payload,
        expected_title=adapted.expected_title,
        source_kind=adapted.source_kind,
        source_url="local-experiment:test",
    )
    return adapted, document


def test_supplied_text_uses_current_parser_to_create_six_article_chunks() -> None:
    adapted, document = _parse(FIXTURE.read_text(encoding="utf-8"))

    assert adapted.mode == "articles"
    assert adapted.chapter == "제2장 전기사업"
    assert adapted.section == "제1절 허가 등"
    assert adapted.removed_ui_lines == 6
    assert [item.path for item in document.provisions] == [
        "제7조",
        "제8조",
        "제9조",
        "제10조",
        "제11조",
        "제12조",
    ]
    assert [item.heading for item in document.provisions] == [
        "사업의 허가",
        "결격사유",
        "전기설비의 설치 및 사업의 개시 의무",
        "사업의 양수 및 법인의 분할ㆍ합병 등",
        "사업의 승계 등",
        "사업허가의 취소 등",
    ]
    assert "제53조에 따른 전기위원회" in document.provisions[0].content
    assert "4의2. 발전소나 발전연료" in document.provisions[0].content
    assert all(_UI_TEXT not in item.content for item in document.provisions)


_UI_TEXT = "조문체계도버튼연혁"


def test_duplicate_article_path_fails_instead_of_silently_dropping_content() -> None:
    with pytest.raises(TextFixtureError, match="중복 조문 경로") as error:
        adapt_text_fixture(
            "제7조(첫째) 본문\n제7조(둘째) 다른 본문",
            document_title="전기사업법",
        )

    assert error.value.code == "duplicate_article_path"


def test_title_and_body_use_current_admin_rule_fallback() -> None:
    adapted, document = _parse("실험 제목\r\n첫 문장입니다.\r\n둘째 문장입니다.")

    assert adapted.mode == "title_body"
    assert document.title == "실험 제목"
    assert [item.path for item in document.provisions] == ["본문/단락1"]
    assert document.provisions[0].content == "첫 문장입니다. 둘째 문장입니다."


def test_branch_article_and_line_endings_are_normalized_by_current_parser() -> None:
    _, document = _parse("제12조의3(가지조문)\r\n① 가지조문 본문이다.\r\n")

    assert [item.path for item in document.provisions] == ["제12조의3"]
    assert document.provisions[0].content == "제12조의3(가지조문) ① 가지조문 본문이다."


@pytest.mark.parametrize("text", ["", " \r\n\t", "제목만 있음"])
def test_empty_or_title_only_input_fails(text: str) -> None:
    with pytest.raises(TextFixtureError):
        adapt_text_fixture(text, document_title="전기사업법")
