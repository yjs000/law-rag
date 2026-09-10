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

판정 우선순위:
- 특정 부지·설비·사업을 실제로 설치할 수 있는지, 허용되는지, 자신에게 적용되는지처럼
  최종적인 개별 결론을 요구하면 토지 지목·용도지역·농지·산지·설비용량·판매용·자가소비
  등 결론을 바꾸는 사실을 확인한다. 필수 사실이 빠진 경우 clarification_required를
  선택하고 missing_fields에 빠진 사실을 구체적으로 쓴다.
- 어떤 허가가 필요한지, 적용될 수 있는 신고·허가·의무·절차가 무엇인지 묻는 질문은
  허가·신고·절차의 조건부 목록과 분기 기준을 법령으로 설명할 수 있으므로 legal_search다.
  개별 결론에 필요한 사실이 누락됐다는 이유만으로 clarification_required를 선택하지 않는다.
- legal_search 답변은 확인되지 않은 사실을 가정해 최종 결론을 내리지 않고, 사실에 따라
  달라지는 부분을 조건과 한계로 명시한다.
"""
