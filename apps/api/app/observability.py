import json
import logging
from collections import Counter
from threading import Lock
from typing import Literal

from pydantic import BaseModel, ConfigDict

from app.domain.routing import QuestionRoute, RouteDecision, RouterTier
from app.domain.schemas import AiFallbackReason, AnswerMode

logger = logging.getLogger("law_rag.question_outcome")
route_logger = logging.getLogger("law_rag.route_outcome")
stage_timing_logger = logging.getLogger("law_rag.question_stage_timing")

QuestionStageTimingStage = Literal[
    "routing", "embedding", "retrieval", "generation", "blocked_route_generation", "request"
]
QuestionStageTimingOutcome = Literal["succeeded", "failed", "timed_out", "degraded"]
_served_by_mode: Counter[str] = Counter()
_route_by_route_tier: Counter[tuple[str, int]] = Counter()
_route_by_reason: Counter[str] = Counter()
_clarification_missing_fields: Counter[str] = Counter()
_fallback_by_reason: Counter[str] = Counter()
_metrics_lock = Lock()


class QuestionOutcomeEvent(BaseModel):
    request_id: str
    mode: AnswerMode
    result: Literal["served"] = "served"
    fallback_reason: AiFallbackReason | None = None


def emit_question_outcome(
    request_id: str, mode: AnswerMode, *, fallback_reason: AiFallbackReason | None = None
) -> None:
    """질문·원문·사용자·비밀을 받을 수 없는 최소 관측 경계.

    2026-08-08: `fallback_reason`을 optional로 추가했다 - 새 이벤트나 새 호출부를 만들지
    않고, 이미 모든 요청(인증·익명 모두)에서 한 번씩 불리는 이 함수 하나에 실어 보낸다.
    인증 사용자는 원래 `_save_if_authenticated`의 diagnostics 저장으로도 fallback_reason을
    보존하지만, 익명 사용자는 이 카운터가 유일한 기록이었다 - 이제 인증 여부와 무관하게
    분포를 집계한다. 질문 원문·사용자 식별자는 여전히 받지 않는다(기존 불변조건 유지).
    """
    event = QuestionOutcomeEvent(request_id=request_id, mode=mode, fallback_reason=fallback_reason)
    with _metrics_lock:
        _served_by_mode[mode.value] += 1
        if fallback_reason is not None:
            _fallback_by_reason[fallback_reason.value] += 1
    logger.info(json.dumps(event.model_dump(mode="json"), ensure_ascii=True))


def question_metrics_snapshot() -> dict[str, int]:
    """외부 메트릭 백엔드 연결 전 사용하는 프로세스 로컬 누계 (mode -> count)."""
    with _metrics_lock:
        return dict(_served_by_mode)


def fallback_reason_metrics_snapshot() -> dict[str, int]:
    """2026-08-08: fallback_reason -> count, 인증 여부와 무관하게 누계.

    route_metrics_snapshot()과 같은 패턴 - 질문 원문은 절대 포함하지 않는다.
    """
    with _metrics_lock:
        return dict(_fallback_by_reason)


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
    텍스트를 받지 않는다. 이 누계로 라우터의 route·reason_code·누락 필드 분포를 검토하고,
    정상 판정과 라우터 불가(timeout/provider error) 경로를 구분한다.
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


class QuestionStageTimingEvent(BaseModel):
    """0045: routing/embedding/retrieval/generation/request 각 stage의 예산 소비를
    구조화 이벤트로 남긴다. 필드는 닫힌 enum과 정수 밀리초뿐이다 - 질문 원문, 근거 내용,
    문서 제목, 예외 메시지, 사용자 식별자는 이 이벤트로 절대 전달할 수 없다(모델
    검증기가 임의 문자열을 거부한다).
    """

    model_config = ConfigDict(extra="forbid")

    request_id: str
    stage: QuestionStageTimingStage
    outcome: QuestionStageTimingOutcome
    elapsed_ms: int
    remaining_ms: int


def emit_question_stage_timing(
    request_id: str,
    stage: QuestionStageTimingStage,
    outcome: QuestionStageTimingOutcome,
    elapsed_ms: int,
    remaining_ms: int,
) -> None:
    """0045: 조정된 요청 예산(52s < 55s < 60s) 아래 각 stage가 얼마나 썼고 얼마나
    남았는지 안전하게 관측한다. 호출부는 절대 잡은 예외를 이 함수에 넘기면 안 된다 -
    이 함수는 그럴 수 있는 매개변수 자체를 받지 않는다.
    """
    event = QuestionStageTimingEvent(
        request_id=request_id,
        stage=stage,
        outcome=outcome,
        elapsed_ms=elapsed_ms,
        remaining_ms=remaining_ms,
    )
    stage_timing_logger.info(json.dumps(event.model_dump(mode="json"), ensure_ascii=True))
