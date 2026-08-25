"""Single-stage question routing before evidence retrieval."""

from dataclasses import dataclass
from typing import Literal, Protocol, runtime_checkable

ProviderQuestionRoute = Literal[
    "legal_search",
    "clarification_required",
    "realtime_required",
    "external_document_required",
]
QuestionRoute = Literal[
    "legal_search",
    "clarification_required",
    "realtime_required",
    "external_document_required",
    "routing_unavailable",
]
RoutingReasonCode = Literal[
    "router_judgment",
    "routing_timeout",
    "routing_provider_error",
]


@dataclass(frozen=True)
class RouteDecision:
    route: QuestionRoute
    reason_code: RoutingReasonCode
    confidence: float
    missing_fields: tuple[str, ...] = ()
    explanation: str | None = None

    def __post_init__(self) -> None:
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be within [0, 1]")


@dataclass(frozen=True)
class RouteJudgment:
    """A provider judgment for one of the four provider-resolvable routes."""

    route: ProviderQuestionRoute
    confidence: float
    reason: str
    missing_fields: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be within [0, 1]")


@runtime_checkable
class QuestionRouter(Protocol):
    async def route(self, question: str) -> RouteJudgment: ...


async def route_question(question: str, router: QuestionRouter) -> RouteDecision:
    judgment = await router.route(question)
    return RouteDecision(
        route=judgment.route,
        reason_code="router_judgment",
        confidence=judgment.confidence,
        missing_fields=judgment.missing_fields,
        explanation=judgment.reason,
    )


ROUTE_DEFINITIONS = """\
- legal_search: 법령 조문으로 일반적인 설명이 가능한 질문.
- clarification_required: 설비용량 등 사용자 사실에 따라 답이 달라져 먼저 물어야 하는 질문.
- realtime_required: 시점/개인 계정 상태에 따라 바뀌는 정보(가격·예산·처리 상태 등)가 필요한 질문.
- external_document_required: 계약서·정산서 등 사용자가 보유한 문서 대조가 필요한 질문.
"""
