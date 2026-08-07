import pytest

from app.domain.routing import (
    RouteDecision,
    match_external_document_keywords,
    match_realtime_keywords,
    route_tier1,
)


def test_realtime_keyword_is_detected() -> None:
    assert match_realtime_keywords("올해 설치비 지원 예산이 얼마나 남았나요?") == ("올해",)


def test_external_document_keyword_is_detected() -> None:
    assert match_external_document_keywords("계약서 내용대로 정산됐는지 확인하고 싶어요") == (
        "계약서",
    )


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


def test_route_decision_rejects_out_of_range_confidence() -> None:
    with pytest.raises(ValueError, match="confidence"):
        RouteDecision(
            route="legal_search",
            reason_code="x",
            tier=1,
            confidence=1.5,
        )
