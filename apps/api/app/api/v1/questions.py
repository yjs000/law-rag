"""Version 1 question and cancellation HTTP transport."""

from __future__ import annotations

import asyncio
import time
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request
from law_rag_core.ports.repository import LegalRepository

from app.api.dependencies import _optional_user, main_module
from app.application.request_budget import RequestBudget
from app.application.v1.dependencies import V1AnsweringError
from app.application.v1.retrieval import elapsed_ms, remaining_ms
from app.domain.schemas import QuestionRequest, QuestionResponse
from app.observability import QuestionStageTimingOutcome, emit_question_stage_timing

router = APIRouter()


async def _handle_question(
    payload: QuestionRequest, request: Request, repository: LegalRepository
) -> QuestionResponse:
    """Coordinate v1 request ownership, cancellation, timing and answer execution."""

    main = main_module()
    budget = RequestBudget.start(
        main.settings.question_request_timeout_seconds,
        main.settings.response_reserve_seconds,
    )
    request_id = str(payload.client_request_id)
    request_started = time.monotonic()
    outcome: QuestionStageTimingOutcome = "failed"
    try:
        user = await _optional_user(request.headers.get("authorization"))
        owner = main._question_owner(request, user)
        task = asyncio.current_task()
        if task is None:
            raise HTTPException(status_code=503, detail="질문 처리를 시작할 수 없습니다.")
        if not await main.question_tasks.register(owner, payload.client_request_id, task):
            raise HTTPException(status_code=409, detail="같은 요청이 이미 처리 중입니다.")
        try:
            await asyncio.sleep(0)
            async with asyncio.timeout(budget.remaining_seconds()):
                response = await main._answer_question(payload, request, user, budget, repository)
        except V1AnsweringError as exc:
            raise _answering_http_error(main, exc) from exc
        except asyncio.CancelledError as exc:
            raise HTTPException(status_code=499, detail="질문 처리가 취소되었습니다.") from exc
        except TimeoutError as exc:
            outcome = "timed_out"
            raise HTTPException(
                status_code=503,
                detail="질문 처리 시간이 초과되었습니다. 잠시 후 다시 시도해 주세요.",
            ) from exc
        finally:
            await main.question_tasks.unregister(owner, payload.client_request_id, task)
        outcome = _request_outcome_for_response(response)
        return response
    finally:
        emit_question_stage_timing(
            request_id,
            "request",
            outcome,
            elapsed_ms(request_started),
            remaining_ms(budget),
        )


@router.post("/v1/questions", response_model=QuestionResponse)
async def question(payload: QuestionRequest, request: Request) -> QuestionResponse:
    """Answer a legal question through the v1 repository contract."""

    return await _handle_question(payload, request, main_module().repository)


@router.post("/v1/questions/{client_request_id}/cancel", status_code=202)
async def cancel_question(client_request_id: UUID, request: Request) -> dict[str, bool]:
    """Cancel an in-flight question owned by the current caller."""

    main = main_module()
    user = await _optional_user(request.headers.get("authorization"))
    if not await main.question_tasks.cancel(main._question_owner(request, user), client_request_id):
        raise HTTPException(status_code=404, detail="처리 중인 질문을 찾을 수 없습니다.")
    return {"cancelled": True}


def _request_outcome_for_response(response: QuestionResponse) -> QuestionStageTimingOutcome:
    """Classify a validated fallback as degraded rather than failed."""

    return "degraded" if response.fallback_reason is not None else "succeeded"


def _answering_http_error(main: object, error: V1AnsweringError) -> HTTPException:
    """Render application failures through the unchanged v1 HTTP contract."""

    details = {
        "search_only_disabled": "검색 전용 기능이 비활성화되어 있습니다.",
        "ai_unavailable": "AI 답변을 현재 사용할 수 없습니다.",
        "generation_failed": "AI 답변을 생성하지 못했습니다. 잠시 후 다시 시도해 주세요.",
        "retrieval_timeout": "법령 검색 시간이 초과되었습니다. 잠시 후 다시 시도해 주세요.",
        "retrieval_unavailable": "법령 검색을 일시적으로 사용할 수 없습니다.",
    }
    if error.code == "corpus_unready":
        return main._corpus_unready_http_error()  # type: ignore[attr-defined]
    return HTTPException(status_code=503, detail=details[error.code])
