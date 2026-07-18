import pytest

from app.domain.search_queries import prepare_search_query


def test_natural_question_removes_question_language_but_keeps_legal_terms() -> None:
    prepared = prepare_search_query("전기저장시설 설치 시 확인할 기준은?")

    assert prepared.terms == ("전기저장시설", "설치", "기준")
    assert prepared.strict_query == "전기저장시설 설치 기준"


def test_ai_is_not_required_to_relax_a_natural_keyword_query() -> None:
    prepared = prepare_search_query("에너지 사업 허가 절차를 알려주세요")

    assert prepared.terms == ("에너지", "사업", "허가")
    assert prepared.strict_query == "에너지 사업 허가"
    assert prepared.minimum_match_query == (
        "(에너지 사업) OR (에너지 허가) OR (사업 허가)"
    )
    assert prepared.anchored_query == "에너지 (사업 OR 허가)"


def test_alias_expansion_and_query_syntax_are_controlled_by_the_server() -> None:
    prepared = prepare_search_query("ESS 설치'); DROP TABLE provisions; --")

    assert prepared.strict_query == (
        "(ess OR 전기저장시설 OR 에너지저장장치) 설치 drop table provisions"
    )
    assert "전기저장시설" in prepared.expanded_terms
    assert "'" not in prepared.minimum_match_query
    assert ";" not in prepared.minimum_match_query


def test_four_stage_query_plan_preserves_all_minimum_two_and_anchor_contracts() -> None:
    prepared = prepare_search_query("전기저장시설 설치 기준")

    assert prepared.anchor_term == "전기저장시설"
    assert prepared.strict_query == "전기저장시설 설치 기준"
    assert prepared.minimum_match_query == (
        "(전기저장시설 설치) OR (전기저장시설 기준) OR (설치 기준)"
    )
    assert prepared.anchored_query == "전기저장시설 (설치 OR 기준)"


def test_minimum_match_contains_every_two_term_combination() -> None:
    prepared = prepare_search_query("전기사업 허가 신청 제출 서류")

    assert prepared.minimum_match_query.count(" OR ") == 9
    assert "(전기사업 허가)" in prepared.minimum_match_query
    assert "(신청 서류)" in prepared.minimum_match_query
    assert "(제출 서류)" in prepared.minimum_match_query


def test_aliases_are_grouped_without_weakening_the_term_requirement() -> None:
    prepared = prepare_search_query("ESS 화재안전 기술기준")

    ess = "(ess OR 전기저장시설 OR 에너지저장장치)"
    assert prepared.strict_query == f"{ess} 화재안전 기술기준"
    assert prepared.minimum_match_query.startswith(f"({ess} 화재안전)")
    assert prepared.anchor_term == "기술기준"
    assert prepared.anchored_query == f"기술기준 ({ess} OR 화재안전)"


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
