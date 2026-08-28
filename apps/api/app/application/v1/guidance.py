"""Safe no-search guidance for v1 routes rejected before retrieval."""

from __future__ import annotations

import time
from typing import Any, Literal

from app.application.answering import clarification_resubmission_summary
from app.application.request_budget import RequestBudget, StageTimeoutError
from app.application.v1.dependencies import V1AnswerDependencies
from app.application.v1.retrieval import elapsed_ms, remaining_ms
from app.domain.routing import RouteDecision
from app.domain.schemas import QuestionRequest, QuestionResponse
from app.observability import emit_question_stage_timing


async def generate_blocked_answer(
    payload: QuestionRequest,
    route_decision: RouteDecision,
    explanation: str | None,
    blocked_fallback: QuestionResponse,
    diagnostics: dict[str, object],
    budget: RequestBudget,
    dependencies: V1AnswerDependencies,
    *,
    stage_name: Literal[
        "clarification_generation",
        "required_source_guidance_generation",
        "blocked_answer_generation",
    ],
) -> QuestionResponse:
    """Generate validation-safe guidance when the router intentionally skipped search."""

    if route_decision.route == "routing_unavailable" and stage_name != "blocked_answer_generation":
        raise ValueError("routing_unavailable requires blocked_answer_generation")
    if route_decision.route != "routing_unavailable" and stage_name == "blocked_answer_generation":
        raise ValueError("blocked_answer_generation is reserved for routing_unavailable")
    stage = diagnostics[stage_name]
    assert isinstance(stage, dict)
    stage.update({"attempted": True, "status": "started"})
    started = time.monotonic()
    outcome: Literal["succeeded", "failed", "timed_out"] = "failed"
    try:
        draft = await budget.run(
            stage_name,
            lambda: dependencies.answer_blocked_route(payload, route_decision.route, explanation),
            cap_seconds=dependencies.answer_timeout_seconds,
        )
        outcome = "succeeded"
    except StageTimeoutError:
        outcome = "timed_out"
        stage["status"] = "timed_out"
        return blocked_fallback
    except Exception as exc:
        status_code = getattr(exc, "status_code", None)
        if status_code in {402, 429}:
            dependencies.mark_ai_quota_exhausted()
        stage["status"] = "billing_or_quota_error" if status_code in {402, 429} else "failed"
        return blocked_fallback
    finally:
        emit_question_stage_timing(
            str(payload.client_request_id),
            stage_name,
            outcome,
            elapsed_ms(started),
            remaining_ms(budget),
        )
    if route_decision.route == "routing_unavailable":
        validation_stage = diagnostics["blocked_response_validation"]
        assert isinstance(validation_stage, dict)
        validation_stage.update({"attempted": True, "status": "started"})
        valid = validate_blocked_response(draft)
        validation_stage["status"] = "succeeded" if valid else "failed"
        if not valid:
            stage["status"] = "blocked_response_validation_failed"
            return blocked_fallback
        stage["status"] = "succeeded"
        return QuestionResponse(
            request_id=str(payload.client_request_id),
            mode="ai",
            summary=draft.summary,
            scope="라우팅 분류 일시 중단 (검색 미실행)",
            sections=[],
            checklist=[],
            citations=[],
            limitations=["질문 분류를 완료하지 못해 법령 검색을 시작하지 않았습니다."],
            requested_answer_mode=payload.answer_mode,
            action="unanswerable",
            route="routing_unavailable",
        )
    if not dependencies.validate_draft(draft, []):
        stage["status"] = "validation_failed"
        return blocked_fallback
    stage["status"] = "succeeded"
    summary = (
        clarification_resubmission_summary(payload.question, draft.missing_information)
        if draft.action == "clarification_required"
        else draft.summary
    )
    return QuestionResponse(
        request_id=str(payload.client_request_id),
        mode="ai",
        summary=summary,
        scope=f"라우팅: {route_decision.route} (검색 미실행)",
        sections=[],
        checklist=[],
        citations=[],
        limitations=[*draft.limitations, "이 서비스는 법률 자문을 대체하지 않습니다."],
        requested_answer_mode=payload.answer_mode,
        action=draft.action,
        route=route_decision.route,
    )


def validate_blocked_response(draft: Any) -> bool:
    """Only an empty explicit no-answer draft may describe routing failure."""

    return draft.action == "unanswerable" and not draft.sections and not draft.checklist
