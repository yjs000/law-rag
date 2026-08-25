import pytest
from pydantic import ValidationError

import app.domain.routing as routing
from app.adapters.nvidia_nim_route_classifier import _RouteJudgmentSchema
from app.domain.routing import RouteDecision, RouteJudgment


class FakeRouter:
    async def route(self, question: str) -> RouteJudgment:
        assert question == "용량에 따라 허가가 달라지나요?"
        return RouteJudgment(
            route="clarification_required",
            confidence=0.9,
            reason="발전설비용량에 따라 달라집니다.",
            missing_fields=("발전설비용량",),
        )


async def test_route_question_converts_single_router_judgment() -> None:
    decision = await routing.route_question("용량에 따라 허가가 달라지나요?", FakeRouter())

    assert decision.route == "clarification_required"
    assert decision.reason_code == "router_judgment"
    assert decision.confidence == 0.9
    assert decision.missing_fields == ("발전설비용량",)
    assert decision.explanation == "발전설비용량에 따라 달라집니다."


def test_route_decision_accepts_application_router_failure_route() -> None:
    decision = RouteDecision(
        route="routing_unavailable",
        reason_code="routing_provider_error",
        confidence=0.0,
    )

    assert decision.route == "routing_unavailable"
    assert decision.reason_code == "routing_provider_error"


def test_route_decision_rejects_out_of_range_confidence() -> None:
    with pytest.raises(ValueError, match="confidence"):
        RouteDecision(
            route="legal_search",
            reason_code="router_judgment",
            confidence=1.5,
        )


def test_route_judgment_rejects_out_of_range_confidence() -> None:
    with pytest.raises(ValueError, match="confidence"):
        RouteJudgment(route="legal_search", confidence=1.5, reason="x")


def test_provider_router_schema_rejects_application_failure_route() -> None:
    with pytest.raises(ValidationError):
        _RouteJudgmentSchema.model_validate(
            {
                "route": "routing_unavailable",
                "confidence": 0.0,
                "reason": "분류를 처리할 수 없습니다.",
                "missing_fields": [],
            }
        )
