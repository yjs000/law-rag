import json
import logging
from collections import Counter
from threading import Lock
from typing import Literal

from pydantic import BaseModel

from app.domain.routing import QuestionRoute, RouteDecision, RouterTier
from app.domain.schemas import AnswerMode

logger = logging.getLogger("law_rag.question_outcome")
route_logger = logging.getLogger("law_rag.route_outcome")
_served_by_mode: Counter[str] = Counter()
_route_by_route_tier: Counter[tuple[str, int]] = Counter()
_route_by_reason: Counter[str] = Counter()
_clarification_missing_fields: Counter[str] = Counter()
_metrics_lock = Lock()


class QuestionOutcomeEvent(BaseModel):
    request_id: str
    mode: AnswerMode
    result: Literal["served"] = "served"


def emit_question_outcome(request_id: str, mode: AnswerMode) -> None:
    """질문·원문·사용자·비밀을 받을 수 없는 최소 관측 경계."""
    event = QuestionOutcomeEvent(request_id=request_id, mode=mode)
    with _metrics_lock:
        _served_by_mode[mode.value] += 1
    logger.info(json.dumps(event.model_dump(mode="json"), ensure_ascii=True))


def question_metrics_snapshot() -> dict[str, int]:
    """외부 메트릭 백엔드 연결 전 사용하는 프로세스 로컬 누계."""
    with _metrics_lock:
        return dict(_served_by_mode)


class RouteOutcomeEvent(BaseModel):
    request_id: str
    route: QuestionRoute
    tier: RouterTier
    reason_code: str
    confidence: float
    missing_field_categories: tuple[str, ...] = ()


def emit_route_outcome(request_id: str, decision: RouteDecision) -> None:
    """0028 라우터 관측 경계. 질문 원문, 사용자가 채운 설비 정보, 문서 내용은 받지 않는다 —

    ``missing_field_categories``는 ``설비용량``처럼 미리 정의된 슬롯 이름만 허용하고 자유
    텍스트를 받지 않는다. tier 1이 clarification을 거의 못 잡는 동안 이 누계로 어느 route가
    tier 2/3에서 얼마나 자주 잡히는지 보고, 나중에 tier 1 사전에 넣을 후보를 찾는다.
    """
    event = RouteOutcomeEvent(
        request_id=request_id,
        route=decision.route,
        tier=decision.tier,
        reason_code=decision.reason_code,
        confidence=decision.confidence,
        missing_field_categories=decision.missing_fields,
    )
    with _metrics_lock:
        _route_by_route_tier[(decision.route, decision.tier)] += 1
        _route_by_reason[decision.reason_code] += 1
        for field in decision.missing_fields:
            _clarification_missing_fields[field] += 1
    route_logger.info(json.dumps(event.model_dump(mode="json"), ensure_ascii=True))


def route_metrics_snapshot() -> dict[str, object]:
    """route/tier/reason_code/missing-field 누계. 질문 원문은 절대 포함하지 않는다."""
    with _metrics_lock:
        return {
            "by_route_and_tier": {
                f"{route}:tier{tier}": count
                for (route, tier), count in _route_by_route_tier.items()
            },
            "by_reason_code": dict(_route_by_reason),
            "clarification_missing_field_categories": dict(_clarification_missing_fields),
        }
