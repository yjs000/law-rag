import pytest

from app.domain.routing import (
    NearestExampleMatch,
    RouteDecision,
    RouteExample,
    RouteJudgment,
    build_tier2_prompt,
    cosine_similarity,
    match_conditional_variance_phrase,
    match_external_document_keywords,
    match_realtime_keywords,
    match_realtime_personal_state_phrase,
    nearest_example,
    route_tier1,
    route_tier2,
)


def test_realtime_keyword_is_detected() -> None:
    assert match_realtime_keywords("올해 설치비 지원 예산이 얼마나 남았나요?") == ("올해",)


def test_external_document_keyword_is_detected() -> None:
    assert match_external_document_keywords("계약서 내용대로 정산됐는지 확인하고 싶어요") == (
        "계약서",
    )


def test_realtime_personal_state_phrase_is_detected() -> None:
    # 2026-08-08: bare "현재"/"지금"/"최근" alone over-triggered (see
    # test_realtime_personal_state_phrase_excludes_law_currency_question below), so this
    # requires a nearby personal/account-state noun instead of a bare keyword match.
    assert match_realtime_personal_state_phrase(
        "전력망 연결 신청 후 현재 대기 순서를 어디서 확인하나요?"
    )


def test_realtime_personal_state_phrase_excludes_law_currency_question() -> None:
    # route-fixture-v1.json boundary case: "현재" here means "currently in effect law"
    # (already handled by as_of_date), not "my current status" - must not trigger.
    assert not match_realtime_personal_state_phrase(
        "현재 시행 중인 신재생에너지법의 허가 절차를 알려주세요."
    )


def test_document_keyword_from_corpus_analysis_is_detected() -> None:
    assert match_external_document_keywords(
        "인버터가 고장 났지만 설치업체가 폐업한 상황인데, 계약서와 보증서에서 수리 책임을 "
        "어떻게 확인하나요?"
    ) == ("계약서", "보증서")


def test_document_keyword_excludes_general_legal_requirement_question() -> None:
    # route-fixture-v1.json boundary case: this asks whether the law requires a
    # contract, not to check the user's own contract - must not trigger.
    assert match_external_document_keywords(
        "태양광 발전사업을 하려면 계약서를 반드시 작성해야 하는 법적 의무가 있나요?"
    ) == ()


def test_question_with_neither_keyword_type_has_no_matches() -> None:
    assert match_realtime_keywords("태양광 발전사업 허가는 어떻게 받나요?") == ()
    assert match_external_document_keywords("태양광 발전사업 허가는 어떻게 받나요?") == ()


def test_tier1_routes_external_document_confidently() -> None:
    decision = route_tier1("정산서를 보니 금액이 안 맞는데 어떻게 확인하나요?")

    assert decision == RouteDecision(
        route="external_document_required",
        reason_code="tier1_document_keyword",
        tier=1,
        confidence=1.0,
    )


def test_tier1_routes_realtime_confidently() -> None:
    decision = route_tier1("지금 시세로 전기를 팔면 얼마나 받을 수 있나요?")

    assert decision is not None
    assert decision.route == "realtime_required"
    assert decision.tier == 1
    assert decision.confidence == 1.0


def test_tier1_prefers_document_over_realtime_when_both_match() -> None:
    decision = route_tier1("계약서에 올해 단가가 어떻게 적혀 있나요?")

    assert decision is not None
    assert decision.route == "external_document_required"


def test_tier1_returns_none_when_inconclusive() -> None:
    assert route_tier1("태양광 발전사업 허가는 어떻게 받나요?") is None


def test_conditional_variance_phrase_is_detected() -> None:
    # D-10 case 0251's exact construction: the answer branches on a fact not given.
    assert match_conditional_variance_phrase(
        "소규모 설비는 용량이나 전기 사용 방식에 따라 허가와 신고가 어떻게 달라지나요?"
    )


def test_conditional_variance_phrase_absent_in_general_question() -> None:
    # D-10 case 0201: same topic, but asks for a general explanation, not "how it varies".
    assert not match_conditional_variance_phrase(
        "태양광 발전소 허가를 준비하고 있는데, 어떤 허가나 신고가 필요한지 어떻게 구분하나요?"
    )


def test_tier1_routes_conditional_variance_phrase_as_clarification() -> None:
    decision = route_tier1("전기 사용 방식에 따라 신고 절차가 다릅니다 어떻게 다른가요?")

    assert decision is not None
    assert decision.route == "clarification_required"
    assert decision.reason_code == "tier1_conditional_variance_phrase"
    assert decision.tier == 1


def test_route_decision_rejects_out_of_range_confidence() -> None:
    with pytest.raises(ValueError, match="confidence"):
        RouteDecision(
            route="legal_search",
            reason_code="x",
            tier=1,
            confidence=1.5,
        )


_LEGAL_SEARCH_EXAMPLE = RouteExample(
    example_id="lay-energy-0201", route="legal_search", embedding=(1.0, 0.0)
)
_CLARIFICATION_EXAMPLE = RouteExample(
    example_id="lay-energy-0251",
    route="clarification_required",
    embedding=(0.0, 1.0),
    missing_fields=("발전설비용량", "전압"),
)


def test_cosine_similarity_of_identical_vectors_is_one() -> None:
    assert cosine_similarity((1.0, 2.0, 3.0), (1.0, 2.0, 3.0)) == pytest.approx(1.0)


def test_cosine_similarity_of_orthogonal_vectors_is_zero() -> None:
    assert cosine_similarity((1.0, 0.0), (0.0, 1.0)) == pytest.approx(0.0)


def test_cosine_similarity_rejects_mismatched_dimensions() -> None:
    with pytest.raises(ValueError, match="dimensionality"):
        cosine_similarity((1.0, 0.0), (1.0, 0.0, 0.0))


def test_nearest_example_picks_the_closest_vector() -> None:
    match = nearest_example((0.9, 0.1), (_LEGAL_SEARCH_EXAMPLE, _CLARIFICATION_EXAMPLE))

    assert match.example_id == "lay-energy-0201"
    assert match.route == "legal_search"
    assert match.similarity > 0.5


def test_route_tier2_requires_at_least_one_example() -> None:
    with pytest.raises(ValueError, match="at least one"):
        nearest_example((1.0, 0.0), ())


class _FakeClassifier:
    """Test double for RouteClassifier - records the hint it was called with."""

    def __init__(self, judgment: RouteJudgment) -> None:
        self.judgment = judgment
        self.received_hint: NearestExampleMatch | None | str = "not called"

    async def classify(
        self, question: str, hint: NearestExampleMatch | None
    ) -> RouteJudgment:
        self.received_hint = hint
        return self.judgment


async def test_route_tier2_llm_judgment_becomes_route_decision() -> None:
    classifier = _FakeClassifier(
        RouteJudgment(
            route="clarification_required",
            confidence=0.9,
            reason="설비용량에 따라 답이 갈린다",
            missing_fields=("발전설비용량",),
        )
    )

    decision = await route_tier2("용량에 따라 허가와 신고가 어떻게 달라지나요?", classifier)

    assert decision.route == "clarification_required"
    assert decision.tier == 2
    assert decision.reason_code == "tier2_llm_judgment"
    assert decision.confidence == 0.9
    assert decision.missing_fields == ("발전설비용량",)


async def test_route_tier2_passes_nearest_example_hint_to_classifier() -> None:
    classifier = _FakeClassifier(
        RouteJudgment(route="legal_search", confidence=0.6, reason="일반 설명 가능")
    )
    hint = nearest_example((0.9, 0.1), (_LEGAL_SEARCH_EXAMPLE, _CLARIFICATION_EXAMPLE))

    await route_tier2("허가나 신고가 필요한지 어떻게 구분하나요?", classifier, hint=hint)

    assert classifier.received_hint == hint


async def test_route_tier2_works_without_a_hint() -> None:
    classifier = _FakeClassifier(
        RouteJudgment(route="legal_search", confidence=0.6, reason="일반 설명 가능")
    )

    await route_tier2("허가나 신고가 필요한지 어떻게 구분하나요?", classifier)

    assert classifier.received_hint is None


def test_route_judgment_rejects_out_of_range_confidence() -> None:
    with pytest.raises(ValueError, match="confidence"):
        RouteJudgment(route="legal_search", confidence=1.5, reason="x")


def test_tier2_prompt_marks_hint_as_advisory_not_authoritative() -> None:
    hint = nearest_example((0.9, 0.1), (_LEGAL_SEARCH_EXAMPLE, _CLARIFICATION_EXAMPLE))

    prompt = build_tier2_prompt("허가나 신고가 필요한지 어떻게 구분하나요?", hint)

    assert "근거로 쓰지 말" in prompt
    assert hint.route in prompt


def test_tier2_prompt_without_hint_says_no_example() -> None:
    prompt = build_tier2_prompt("허가나 신고가 필요한지 어떻게 구분하나요?", None)

    assert "참고할 유사 예시 없음" in prompt
