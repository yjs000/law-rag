import pytest

from app.domain.search_queries import prepare_search_query


def test_natural_question_removes_question_language_but_keeps_legal_terms() -> None:
    prepared = prepare_search_query("전기저장시설 설치 시 확인할 기준은?")

    assert prepared.terms == ("전기저장시설", "설치", "기준")
    assert prepared.strict_query == "전기저장시설 설치 기준"


def test_ai_is_not_required_to_relax_a_natural_keyword_query() -> None:
    prepared = prepare_search_query("에너지 사업 허가 절차를 알려주세요")

    assert prepared.terms == ("에너지", "사업", "허가")
    assert prepared.relaxed_query == "에너지 OR 사업 OR 허가"


def test_alias_expansion_and_query_syntax_are_controlled_by_the_server() -> None:
    prepared = prepare_search_query("ESS 설치'); DROP TABLE provisions; --")

    assert prepared.strict_query == "ess 설치 drop table provisions"
    assert "전기저장시설" in prepared.expanded_terms
    assert "'" not in prepared.relaxed_query
    assert ";" not in prepared.relaxed_query


@pytest.mark.parametrize(
    ("question", "terms"),
    [
        (
            "전기저장시설을 설치할 때 적용되는 화재안전 기준은 무엇인가요?",
            ("전기저장시설", "설치", "적용", "화재안전", "기준"),
        ),
        (
            "전기사업 허가를 신청할 때 제출해야 하는 서류는 무엇인가요?",
            ("전기사업", "허가", "신청", "제출", "서류"),
        ),
    ],
)
def test_first_page_questions_keep_only_searchable_terms(question, terms) -> None:
    assert prepare_search_query(question).terms == terms
