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
- route 판단과 별개로 missing_fields를 먼저 추출한다. 질문자가 결과를 가르는 결정축을 직접
  언급했지만 구체적인 값을 주지 않은 축은 모두 missing_fields에 넣는다. 일반적인 허가·신고
  종류나 구분 기준만 묻고 결정축을 직접 지목하지 않았다면 missing_fields는 비운다.
- 반드시 다음 순서로 판정한다. 1. missing_fields를 먼저 추출한다. 2. legal_search 후보인데
  missing_fields가 하나라도 있으면 clarification_required로 정한다. 3. 비어 있을 때만
  legal_search를 확정한다. realtime·외부 문서 필요성은 각각의 전용 route로 판정한다.
- 추출 예시: "용량에 따라"라고 했지만 숫자·단위가 없으면 '설비용량'을 넣는다. "사용 방식에
  따라"라고 했지만 판매용·자가소비용 선택이 없으면 '전기 사용 방식'을 넣는다. "전압에 따라"라고
  했지만 실제 전압이 없으면 '전압'을 넣는다. 이는 단어 존재만 보는 것이 아니라 실제 값의
  제공 여부를 본다.
- 특정 부지·설비·사업을 실제로 설치할 수 있는지, 허용되는지, 자신에게 적용되는지처럼
  최종적인 개별 결론을 요구하면 토지 지목·용도지역·농지·산지·설비용량·판매용·자가소비
  등 결론을 바꾸는 사실을 확인한다. 필수 사실이 빠진 경우 clarification_required를
  선택하고 missing_fields에 빠진 사실을 구체적으로 쓴다.
- 어떤 허가가 필요한지, 적용될 수 있는 신고·허가·의무·절차가 무엇인지 묻는 질문은
  허가·신고·절차의 조건부 목록과 분기 기준을 법령으로 설명할 수 있으므로 legal_search다.
  개별 결론에 필요한 사실이 누락됐다는 이유만으로 clarification_required를 선택하지 않는다.
- 다만 질문이 설비규모 같은 결정 사실에 따라 여러 경로 중 어느 경로가 적용되는지를
  골라 달라고 요구하면서 결정 사실의 실제 값을 주지 않았다면 clarification_required다.
  가능한 경로 전체와 각 조건을 일반적으로 설명해 달라는 질문과 구분한다.
- 질문자가 특정 설비에 적용될 경로를 요구하면서 용량·전압·사용 방식·공사 종류처럼 결과를
  가르는 결정축을 질문에서 직접 지목했지만 그 실제 값이 하나라도 빠졌다면
  clarification_required를 우선한다. 이때는 조건부 일반 설명을 일부 제공할 수 있더라도 먼저
  누락 사실을 묻는다. 상충하면 이 규칙이 legal_search 일반 설명 규칙보다 우선한다.
- 대조 예시: "허가·신고의 종류와 일반 구분 기준은 무엇인가"는 legal_search다. 반면
  "용량과 사용 방식에 따라 달라지는 자기 설비의 절차는 무엇인가"처럼 결정축의 실제 값을
  주지 않은 질문은 clarification_required다. 문장에 "어떻게 달라지는가"가 있어도 같다.
- legal_search 답변은 확인되지 않은 사실을 가정해 최종 결론을 내리지 않고, 사실에 따라
  달라지는 부분을 조건과 한계로 명시한다.
"""
