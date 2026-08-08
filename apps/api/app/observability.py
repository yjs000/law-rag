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


# TODO(2026-08-08, 사용자 요청): 지금 fallback_reason은 인증 사용자에게만 diagnostics로
# 저장된다(app/main.py의 _save_if_authenticated -> postgres_identity.save_question).
# 익명 사용자는 emit_question_outcome이 mode만 남기고 fallback_reason은 안 남아, 익명
# 요청이 왜 fallback됐는지 나중에 분석할 수 없다. 이 파일의 다른 이벤트(emit_route_outcome
# 등)도 마찬가지로 route/tier/reason_code 분포는 집계되지만 fallback_reason·generation
# 실패 사유·embedding 실패 사유는 익명 사용자 기준으로 집계되지 않는다. 개인정보 없이
# (질문 원문·사용자 식별자 없이) mode/route/tier/reason_code처럼 이미 안전한 필드들과
# 나란히 embedding/generation 단계의 실패 사유도 process-local counter로 남기는
# emit_question_stage_outcome류 이벤트를 추가해, 인증 여부와 무관하게 "왜 실패했는지"
# 분포를 분석 가능하게 만드는 걸 후속 작업으로 등록한다.


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
