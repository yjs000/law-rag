import pytest
from pydantic import ValidationError

from law_rag_agent.schemas import GenerationResult, RouteDecision


def test_route_decision_accepts_known_routes():
    decision = RouteDecision(route="legal_search", reason="에너지 법령 질문")
    assert decision.route == "legal_search"


def test_route_decision_rejects_unknown_route():
    with pytest.raises(ValidationError):
        RouteDecision(route="not_a_real_route", reason="x")


def test_generation_result_holds_citation_ids_and_action():
    result = GenerationResult(
        answer="태양광은 신에너지법 제2조에서 정의합니다.",
        citation_ids=["C1", "C2"],
        action="fully_answerable",
    )
    assert result.citation_ids == ["C1", "C2"]
    assert result.action == "fully_answerable"
