"""SSE presentation and provider-phase admission for v2 executions."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Header, HTTPException, Request
from fastapi.responses import StreamingResponse

from app.api.dependencies import _optional_user, main_module
from app.application.v2.dependencies import PhaseRequest
from app.domain.answer_events import AnswerEvent
from app.domain.pipeline_issues import ExecutionPhase
from app.domain.question_execution import ExecutionStatus
from app.domain.schemas import QuestionRequest
from app.observability import emit_execution_phase
from app.ports.question_execution import ExecutionConflict, ExecutionNotFound, SystemBusy

router = APIRouter()


def _sse(event_type: str, payload: dict[str, object]) -> bytes:
    """Serialize one already-persisted answer event in the public SSE format."""

    return f"event: {event_type}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n".encode()


async def _stream_execution_phase(
    execution_id: UUID,
    request: Request,
    phase: Literal["core", "finalize"],
    execution_capability: str | None,
) -> StreamingResponse:
    """Present pre-stream errors as HTTP and post-start outcomes as typed SSE events."""

    main = main_module()
    user = await _optional_user(request.headers.get("authorization"))
    capability_hash = main._capability_hash(execution_capability) if user is None else None
    try:
        phase_request = PhaseRequest(
            execution_id=execution_id,
            owner_scope=main._question_owner(request, user),
            capability_hash=capability_hash,
            user=user,
        )
        run = (
            await main.v2_question_execution_service.begin_core(phase_request)
            if phase == "core"
            else await main.v2_question_execution_service.begin_finalize(phase_request)
        )
    except ExecutionNotFound as exc:
        raise HTTPException(status_code=404, detail="질문 실행을 찾을 수 없습니다.") from exc

    try:
        persisted = await main.v2_question_execution_service.await_phase(run)
    except (ExecutionConflict, ValueError):
        persisted = (AnswerEvent.error("phase_not_ready"),)
    except ExecutionNotFound:
        persisted = (AnswerEvent.error("execution_not_found"),)

    async def events():
        for event in persisted:
            yield _sse(event.event_type, dict(event.payload))

    return StreamingResponse(events(), media_type="text/event-stream")


async def _admit_v2_provider_phase(
    execution: object, phase: Literal["core", "finalize"]
) -> object | None:
    """Acquire provider capacity before sending an SSE response when work will start."""

    main = main_module()
    request_data = execution.private_payload.get("request")
    if not isinstance(request_data, dict):
        return None
    request_payload = QuestionRequest.model_validate(request_data)
    will_start = (phase == "core" and execution.status is ExecutionStatus.PREPARED) or (
        phase == "finalize"
        and execution.status
        in {ExecutionStatus.CORE_ANSWERED, ExecutionStatus.CORE_REPAIR_REQUIRED}
    )
    if not will_start or request_payload.answer_mode != "terra":
        return None
    if phase == "finalize" and isinstance(
        execution.private_payload.get("verified_core_response"), dict
    ):
        return None
    if execution.private_payload.get("route", "legal_search") != "legal_search":
        return None
    try:
        return await main.question_phase_limiter.acquire(
            execution.execution_id,
            ExecutionPhase.CORE if phase == "core" else ExecutionPhase.FINALIZE,
            datetime.now(UTC) + timedelta(seconds=main.settings.v2_provider_budget_seconds),
        )
    except SystemBusy as exc:
        emit_execution_phase(str(execution.execution_id), phase, "busy")
        raise HTTPException(status_code=503, detail="system_busy") from exc


@router.post("/v2/question-executions/{execution_id}/core")
async def core_question_execution(
    execution_id: UUID,
    request: Request,
    execution_capability: Annotated[str | None, Header(alias="X-Execution-Capability")] = None,
) -> StreamingResponse:
    return await _stream_execution_phase(execution_id, request, "core", execution_capability)


@router.post("/v2/question-executions/{execution_id}/finalize")
async def finalize_question_execution(
    execution_id: UUID,
    request: Request,
    execution_capability: Annotated[str | None, Header(alias="X-Execution-Capability")] = None,
) -> StreamingResponse:
    return await _stream_execution_phase(execution_id, request, "finalize", execution_capability)
