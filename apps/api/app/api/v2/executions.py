"""Version 2 prepare and cancellation transport plus service compatibility seams."""

from __future__ import annotations

import hashlib
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Header, HTTPException, Request
from law_rag_core.ports.repository import LegalRepository

from app.adapters.openai_answerer import CoreDraft
from app.api.dependencies import _optional_user, main_module
from app.application.clarification_workflow import ClarificationOwner, ClarificationTurnRequest
from app.application.question_phase_coordinator import PhaseResult
from app.application.v2.dependencies import PhaseRequest, PreparedExecution, PrepareQuestion
from app.application.v2.grounding import ClarificationGrounding
from app.domain.routing import RouteDecision
from app.domain.schemas import Citation, MockUser, QuestionRequest, QuestionResponse
from app.observability import emit_execution_phase
from app.ports.clarification_case import ClarificationCaseNotFound
from app.ports.question_execution import ExecutionNotFound

router = APIRouter()


def _not_ready_error() -> HTTPException:
    return HTTPException(
        status_code=503,
        detail={"code": "v2_search_not_ready", "message": "v2 검색을 아직 사용할 수 없습니다."},
    )


async def _v2_repository() -> LegalRepository:
    """Resolve the active-generation repository through the patchable main seam."""

    main = main_module()
    resources = main._llamaindex_resources()
    if resources is None:
        raise _not_ready_error()
    _, _, repository = resources
    if repository is None or not await main._v2_ready():
        raise _not_ready_error()
    return repository


def _v2_active_provider() -> Any:
    """Return the active generation provider only when resources are configured."""

    resources = main_module()._llamaindex_resources()
    if resources is None or resources[0] is None:
        raise _not_ready_error()
    return resources[0]


def _capability_hash(value: str | None) -> str | None:
    return hashlib.sha256(value.encode("utf-8")).hexdigest() if value else None


def _execution_capability(owner_scope: str, idempotency_key: str) -> str:
    """Derive a replay-safe opaque anonymous capability without storing plaintext."""

    material = f"{owner_scope}\x00{idempotency_key}".encode()
    return hashlib.sha256(main_module().settings.rate_limit_secret.encode() + material).hexdigest()


async def _retrieve_pinned_v2_evidence(
    payload: QuestionRequest, active: Any, repository: LegalRepository
) -> tuple[list[Any], Any]:
    """Retrieve from the same frozen active index persisted by prepare."""

    main = main_module()
    hits = await main.llamaindex_search_index(
        active.index, payload.question, payload.as_of_date, 10
    )
    return hits, await repository.last_sync()


@router.post("/v2/question-executions")
async def prepare_question_execution(
    payload: QuestionRequest,
    request: Request,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=1)],
) -> dict[str, object]:
    """Freeze active evidence before the core or finalize provider phases start."""

    main = main_module()
    user = await _optional_user(request.headers.get("authorization"))
    owner_scope = main._question_owner(request, user)
    clarification, clarification_outcome, route_decision = await _prepare_clarification_turn(
        main, payload, owner_scope, user
    )
    prepared = await main.v2_question_execution_service.prepare(
        PrepareQuestion(
            payload=payload,
            owner_scope=owner_scope,
            idempotency_key=idempotency_key,
            user=user,
            clarification=clarification,
            clarification_outcome=clarification_outcome,
            route_decision=route_decision,
        )
    )
    emit_execution_phase(str(prepared.execution.execution_id), "prepare", "prepared")
    return main.v2_question_execution_service.prepared_response(prepared)


async def _prepare_clarification_turn(
    main: Any,
    payload: QuestionRequest,
    owner_scope: str,
    user: MockUser | None,
) -> tuple[ClarificationGrounding | None, Any | None, RouteDecision | None]:
    """Resolve one optional clarification turn without persisting its capability."""

    workflow = getattr(main, "clarification_workflow", None)
    if workflow is None:
        return None, None, None

    is_continuation = payload.clarification_case_id is not None
    route_decision: RouteDecision | None = None
    if not is_continuation:
        try:
            route_decision = await main.route_question(payload.question, main._question_router())
        except TimeoutError:
            route_decision = RouteDecision(
                route="routing_unavailable", reason_code="routing_timeout", confidence=0.0
            )
        except Exception:  # noqa: BLE001 - optional provider routing must not block prepare
            route_decision = RouteDecision(
                route="routing_unavailable", reason_code="routing_provider_error", confidence=0.0
            )
        if route_decision.route != "clarification_required":
            return None, None, route_decision

    try:
        outcome = await workflow.run_turn(
            ClarificationTurnRequest(
                question=payload.question,
                as_of_date=payload.as_of_date,
                project_stage=payload.project_stage,
                case_id=payload.clarification_case_id,
                user_text=payload.question if is_continuation else None,
                conversation_id=payload.conversation_id,
            ),
            ClarificationOwner(
                owner_scope=owner_scope,
                capability_hash=_capability_hash(payload.clarification_capability)
                if user is None
                else None,
            ),
        )
    except ClarificationCaseNotFound as exc:
        raise HTTPException(status_code=404, detail="보완 질문을 찾을 수 없습니다.") from exc

    if outcome.case is None or outcome.next_status is None:
        return None, None, route_decision
    return (
        ClarificationGrounding(policy=outcome.policy, case=outcome.case.case),
        outcome,
        route_decision,
    )


@router.delete("/v2/question-executions/{execution_id}", status_code=202)
async def cancel_question_execution(
    execution_id: UUID,
    request: Request,
    execution_capability: Annotated[str | None, Header(alias="X-Execution-Capability")] = None,
) -> dict[str, bool]:
    """Cancel an owned execution before or during a provider phase."""

    main = main_module()
    user = await _optional_user(request.headers.get("authorization"))
    try:
        await main.v2_question_execution_service.cancel(
            PhaseRequest(
                execution_id=execution_id,
                owner_scope=main._question_owner(request, user),
                capability_hash=_capability_hash(execution_capability) if user is None else None,
                user=user,
            )
        )
    except ExecutionNotFound as exc:
        raise HTTPException(status_code=404, detail="질문 실행을 찾을 수 없습니다.") from exc
    return {"cancelled": True}


def _prepared_execution_response(
    execution: Any, *, execution_capability: str | None = None
) -> dict[str, object]:
    return main_module().v2_question_execution_service.prepared_response(
        PreparedExecution(execution=execution, execution_capability=execution_capability)
    )


async def _v2_response_from_frozen_evidence(execution: Any) -> QuestionResponse:
    return await main_module().v2_question_execution_service.response_from_frozen_evidence(
        execution
    )


async def _v2_core_from_frozen_evidence(execution: Any) -> tuple[CoreDraft, list[Citation]]:
    return await main_module().v2_question_execution_service.core_from_frozen_evidence(execution)


async def _run_v2_core(execution: Any) -> PhaseResult:
    return await main_module().v2_question_execution_service.run_core(execution)


async def _run_v2_finalize(execution: Any, user: MockUser | None) -> PhaseResult:
    main = main_module()
    return await main.v2_question_execution_service.run_finalize(
        execution,
        user,
        response_from_frozen_evidence=main._v2_response_from_frozen_evidence,
    )
