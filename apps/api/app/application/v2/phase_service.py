"""Prepare, core, and finalize use cases for v2 question executions."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import timedelta
from typing import Any, Literal
from uuid import UUID

from app.application.answering import route_guidance_fallback, search_only_answer
from app.application.question_phase_coordinator import PhaseResult, QuestionPhaseCoordinator
from app.application.v2.dependencies import (
    PhaseRequest,
    PreparedExecution,
    PrepareQuestion,
    V2ExecutionDependencies,
)
from app.application.v2.evidence import (
    citations_for_hits,
    execution_generation_hits,
    execution_request_and_hits,
    freeze_citations,
)
from app.application.v2.grounding import (
    ClarificationGrounding,
    claims_are_grounded,
    clarification_grounding_from_payload,
    core_claim_targets,
    core_degraded_response,
    core_is_grounded,
    detail_claim_targets,
    grounding_fallback,
    response_is_grounded,
)
from app.domain.answer_events import AnswerEvent
from app.domain.grounding import CitationRegistry
from app.domain.question_execution import ExecutionSnapshot, ExecutionStatus, next_action_for
from app.domain.routing import RouteDecision
from app.domain.schemas import (
    ClarificationContinuation,
    ClarificationFactPrompt,
    MockUser,
    QuestionResponse,
)
from app.ports.clarification_case import ClarificationCaseStatus
from app.ports.question_execution import ExecutionNotFound, QuestionExecutionRecord

lease_release_logger = logging.getLogger("law_rag.phase_lease_release")


@dataclass(frozen=True)
class PhaseRun:
    """A phase admitted before HTTP starts streaming its persisted events."""

    task: asyncio.Task[tuple[AnswerEvent, ...]]
    owns_task: bool


class V2QuestionExecutionService:
    """Run the authoritative v2 prepare → core → finalize state machine.

    Dependencies are supplied by a provider instead of imported from framework
    modules.  The provider may be a production composition root or a narrow
    compatibility seam for legacy tests that patch ``app.main``.
    """

    def __init__(self, dependencies: Callable[[], V2ExecutionDependencies]) -> None:
        self._dependencies = dependencies
        self._phase_tasks: dict[object, asyncio.Task[tuple[AnswerEvent, ...]]] = {}

    async def prepare(self, request: PrepareQuestion) -> PreparedExecution:
        """Freeze the active generation and its evidence before provider work."""

        dependencies = self._dependencies()
        await dependencies.executions.expire(dependencies.now())
        existing = await dependencies.executions.find_by_prepare_key(
            request.owner_scope, request.idempotency_key
        )
        if existing is not None:
            return PreparedExecution(
                execution=existing,
                execution_capability=self._anonymous_capability(request, dependencies),
            )

        repository = await dependencies.resolve_repository()
        quota_kind = "ai" if request.payload.answer_mode == "terra" else "search"
        await dependencies.check_quota(quota_kind, request.user)
        await dependencies.require_supported_date(request.payload.as_of_date, repository)

        route, missing_fields = await self._route(
            dependencies,
            request.payload.question,
            request.payload.answer_mode,
            request.route_decision,
        )
        active = await dependencies.active_provider().active()
        hits, corpus_as_of = await self._retrieve_if_legal(
            dependencies, request.payload, active, repository, route
        )
        generation_hits = self._generation_hits(
            dependencies, request.payload.answer_mode, route, hits
        )
        execution_capability = self._anonymous_capability(request, dependencies)
        private_payload = {
            # The case capability authorizes transport access only; preserving it
            # with the long-lived execution snapshot would create a second secret store.
            "request": request.payload.model_dump(
                mode="json", exclude={"clarification_capability"}
            ),
            "hits": [hit.model_dump(mode="json") for hit in hits],
            "generation_hits": [hit.model_dump(mode="json") for hit in generation_hits],
            "corpus_as_of": corpus_as_of.isoformat() if corpus_as_of is not None else None,
            "route": route,
            "missing_fields": list(missing_fields),
        }
        if request.clarification is not None:
            private_payload["clarification_grounding"] = request.clarification.to_payload()
        if request.clarification_outcome is not None:
            private_payload["clarification_outcome"] = self._clarification_outcome_payload(
                request,
                dependencies,
            )
        execution = await dependencies.executions.prepare_or_get(
            owner_scope=request.owner_scope,
            prepare_idempotency_key=request.idempotency_key,
            generation_id=active.generation.id,
            capability_hash=dependencies.capability_hash(execution_capability),
            private_payload=private_payload,
            frozen_citations=freeze_citations(generation_hits),
            expires_at=dependencies.now() + timedelta(minutes=10),
        )
        return PreparedExecution(execution=execution, execution_capability=execution_capability)

    async def stream_core(self, request: PhaseRequest) -> tuple[AnswerEvent, ...]:
        """Run or replay the core phase without allowing duplicate provider work."""

        return await self.await_phase(await self.begin_core(request))

    async def stream_finalize(self, request: PhaseRequest) -> tuple[AnswerEvent, ...]:
        """Run or replay the finalize phase after a persisted core outcome."""

        return await self.await_phase(await self.begin_finalize(request))

    async def begin_core(self, request: PhaseRequest) -> PhaseRun:
        """Admit core provider work before the HTTP SSE response starts."""

        return await self._begin_phase(request, "core")

    async def begin_finalize(self, request: PhaseRequest) -> PhaseRun:
        """Admit finalize provider work before the HTTP SSE response starts."""

        return await self._begin_phase(request, "finalize")

    async def await_phase(self, run: PhaseRun) -> tuple[AnswerEvent, ...]:
        """Await a pre-admitted phase while preserving replay-safe cancellation semantics."""

        try:
            return await asyncio.shield(run.task)
        except asyncio.CancelledError:
            if not run.task.cancelled() and run.owns_task:
                raise
            if not run.task.cancelled():
                raise
            return (AnswerEvent.cancelled(),)

    async def cancel(self, request: PhaseRequest) -> None:
        """Cancel an owned execution and the local in-flight task, when present."""

        dependencies = self._dependencies()
        await dependencies.executions.cancel(
            request.execution_id,
            request.owner_scope,
            capability_hash=request.capability_hash,
        )
        task = self._phase_tasks.get(request.execution_id)
        if task is not None:
            task.cancel()

    async def response_from_frozen_evidence(
        self, execution: QuestionExecutionRecord
    ) -> QuestionResponse:
        """Generate detail only from persisted evidence; never retrieve again."""

        dependencies = self._dependencies()
        payload, hits, corpus_as_of = execution_request_and_hits(execution)
        fallback = search_only_answer(payload, hits, corpus_as_of)
        fallback.request_id = str(payload.client_request_id)
        route = execution.private_payload.get("route", "legal_search")
        if route != "legal_search":
            missing_fields = execution.private_payload.get("missing_fields", [])
            return route_guidance_fallback(
                payload,
                str(route),
                missing_fields=tuple(item for item in missing_fields if isinstance(item, str))
                if isinstance(missing_fields, list)
                else (),
            )
        if payload.answer_mode != "terra" or not dependencies.ai_available():
            return fallback

        generation_hits = self._stored_or_selected_generation_hits(dependencies, execution, hits)
        clarification = self._clarification_grounding(execution)
        if clarification is None:
            draft = await dependencies.answerer().answer(payload, generation_hits)
        else:
            draft = await dependencies.answerer().answer(
                payload, generation_hits, clarification=clarification
            )
        if not dependencies.validate_response(draft, generation_hits):
            raise ValueError("generated answer did not satisfy the citation contract")
        if clarification is not None and not claims_are_grounded(
            draft.grounded_claims,
            clarification,
            CitationRegistry(execution.frozen_citations),
            required_targets=detail_claim_targets(draft),
        ):
            raise ValueError(
                "generated clarification claims did not satisfy the grounding contract"
            )
        return QuestionResponse(
            request_id=str(payload.client_request_id),
            mode="ai",
            summary=draft.summary,
            scope=draft.scope,
            sections=draft.sections,
            checklist=draft.checklist,
            citations=citations_for_hits(generation_hits),
            limitations=[*draft.limitations, "이 서비스는 법률 자문을 대체하지 않습니다."],
            corpus_as_of=corpus_as_of,
            requested_answer_mode=payload.answer_mode,
            action=draft.action,
            route="legal_search",
        )

    async def core_from_frozen_evidence(
        self, execution: QuestionExecutionRecord
    ) -> tuple[Any, list[Any]]:
        """Generate the compact core result from the exact evidence frozen at prepare."""

        core, citations, _used_safe_fallback = await self._core_result_from_frozen_evidence(
            execution
        )
        return core, citations

    async def _core_result_from_frozen_evidence(
        self, execution: QuestionExecutionRecord
    ) -> tuple[Any, list[Any], bool]:
        """Return the core and whether it is the deterministic non-AI fallback."""

        dependencies = self._dependencies()
        payload, hits, corpus_as_of = execution_request_and_hits(execution)
        fallback = search_only_answer(payload, hits, corpus_as_of)
        route = execution.private_payload.get("route", "legal_search")
        if (
            route != "legal_search"
            or payload.answer_mode != "terra"
            or not dependencies.ai_available()
        ):
            return (
                dependencies.make_core_draft(
                    fallback.summary,
                    [citation.id for citation in fallback.citations],
                    fallback.action or "unanswerable",
                ),
                fallback.citations,
                True,
            )

        generation_hits = self._stored_or_selected_generation_hits(dependencies, execution, hits)
        clarification = self._clarification_grounding(execution)
        if clarification is None:
            draft = await dependencies.answerer().answer_core(payload, generation_hits)
        else:
            draft = await dependencies.answerer().answer_core(
                payload, generation_hits, clarification=clarification
            )
        if not dependencies.validate_core(draft, generation_hits):
            raise ValueError("generated core did not satisfy the citation contract")
        return draft, citations_for_hits(generation_hits), False

    async def run_core(self, execution: QuestionExecutionRecord) -> PhaseResult:
        """Validate a core draft before persisting the only publishable core event."""

        core, citations, used_safe_fallback = await self._core_result_from_frozen_evidence(
            execution
        )
        clarification = self._clarification_grounding(execution)
        if clarification is None:
            core_is_valid = core_is_grounded(core, CitationRegistry(execution.frozen_citations))
        elif used_safe_fallback:
            # This deterministic search-only output is not an LLM claim surface.
            # In particular, the legacy CoreDraft has no structured claims to read.
            core_is_valid = True
        else:
            core_is_valid = claims_are_grounded(
                core.grounded_claims,
                clarification,
                CitationRegistry(execution.frozen_citations),
                required_targets=core_claim_targets(core),
            )
        if not core_is_valid:
            return PhaseResult(
                target=ExecutionStatus.CORE_REPAIR_REQUIRED,
                events=(
                    AnswerEvent(
                        event_type="phase_complete",
                        payload={
                            "status": ExecutionStatus.CORE_REPAIR_REQUIRED.value,
                            "next_action": "repair_core",
                        },
                    ),
                ),
            )
        # Claims are validated before this point and must not alter the legacy
        # persisted-core contract or become a second public response surface.
        core_data = core.model_dump(mode="json", exclude={"grounded_claims"})
        return PhaseResult(
            target=ExecutionStatus.CORE_ANSWERED,
            events=(
                AnswerEvent(
                    event_type="summary",
                    payload={
                        "summary": core.summary,
                        "citations": [citation.model_dump(mode="json") for citation in citations],
                    },
                ),
                AnswerEvent(
                    event_type="phase_complete",
                    payload={
                        "status": ExecutionStatus.CORE_ANSWERED.value,
                        "next_action": "generate_detail",
                    },
                ),
            ),
            private_payload={
                "verified_core": core_data,
                "verified_core_citations": [
                    citation.model_dump(mode="json") for citation in citations
                ],
            },
        )

    async def run_finalize(
        self,
        execution: QuestionExecutionRecord,
        user: MockUser | None,
        *,
        response_from_frozen_evidence: Callable[[QuestionExecutionRecord], Any] | None = None,
    ) -> PhaseResult:
        """Finalize safely, preserving verified core content on detail failure."""

        dependencies = self._dependencies()
        payload, _hits, _corpus_as_of = execution_request_and_hits(execution)
        stored_core = execution.private_payload.get("verified_core")
        core = self._core_from_payload(dependencies, stored_core)
        degraded = execution.status is ExecutionStatus.CORE_REPAIR_REQUIRED
        produce_response = response_from_frozen_evidence or self.response_from_frozen_evidence
        try:
            response = await produce_response(execution)
        except Exception:
            response = core_degraded_response(payload, core, execution.private_payload)
            degraded = True
        clarification = self._clarification_grounding(execution)
        if clarification is None and not response_is_grounded(
            response, CitationRegistry(execution.frozen_citations)
        ):
            response = core_degraded_response(payload, core, execution.private_payload)
            degraded = True
        elif core is not None:
            response.summary = core.summary
            response.action = core.action
        if clarification is not None and not degraded:
            try:
                response = await self._persist_clarification_outcome(
                    dependencies,
                    execution,
                    response,
                )
            except Exception:
                response = core_degraded_response(payload, core, execution.private_payload)
                degraded = True
        response = await dependencies.save_authenticated(user, payload, response)
        response_data = response.model_dump(mode="json")
        return PhaseResult(
            target=ExecutionStatus.COMPLETED,
            response=response_data,
            events=(
                AnswerEvent.complete(
                    {"response": response_data, "outcome": "degraded" if degraded else "normal"}
                ),
            ),
        )

    def prepared_response(self, prepared: PreparedExecution) -> dict[str, object]:
        """Map the persisted state to the transport-neutral prepare response."""

        execution = prepared.execution
        next_action = next_action_for(
            ExecutionSnapshot(status=execution.status, version=execution.version)
        )
        response: dict[str, object] = {
            "execution_id": str(execution.execution_id),
            "status": execution.status.value,
            "next_action": next_action.value if next_action else "complete",
        }
        if prepared.execution_capability is not None:
            response["execution_capability"] = prepared.execution_capability
        return response

    async def _begin_phase(
        self, request: PhaseRequest, phase: Literal["core", "finalize"]
    ) -> PhaseRun:
        dependencies = self._dependencies()
        await dependencies.executions.expire(dependencies.now())
        execution = await dependencies.executions.get_owned(
            request.execution_id,
            request.owner_scope,
            capability_hash=request.capability_hash,
        )
        if execution.status is ExecutionStatus.EXPIRED:
            raise ExecutionNotFound()

        coordinator = QuestionPhaseCoordinator(
            dependencies.executions,
            core=dependencies.run_core,
            finalize=lambda current: dependencies.run_finalize(current, request.user),
            phase_timeout=dependencies.phase_timeout,
        )
        existing = self._phase_tasks.get(request.execution_id)
        owns_task = existing is None or existing.done()
        start_gate = asyncio.Event()

        async def run_after_admission() -> tuple[AnswerEvent, ...]:
            await start_gate.wait()
            return await coordinator.run(
                request.execution_id,
                request.owner_scope,
                phase=phase,
                capability_hash=request.capability_hash,
            )

        task = asyncio.create_task(run_after_admission()) if owns_task else existing
        assert task is not None
        if owns_task:
            self._phase_tasks[request.execution_id] = task
        try:
            lease = await dependencies.admit_phase(execution, phase) if owns_task else None
        except BaseException:
            self._discard_owned_task(request.execution_id, task, owns_task)
            task.cancel()
            raise

        if owns_task:
            task.add_done_callback(
                lambda completed: self._schedule_phase_release(
                    request.execution_id, completed, lease
                )
            )
            start_gate.set()
        return PhaseRun(task=task, owns_task=owns_task)

    def _schedule_phase_release(self, execution_id: object, task: Any, lease: Any) -> None:
        release_task = asyncio.create_task(self._release_phase_task(execution_id, task, lease))
        release_task.add_done_callback(self._observe_phase_release_failure)

    @staticmethod
    def _observe_phase_release_failure(release_task: asyncio.Task[None]) -> None:
        if release_task.cancelled():
            return
        try:
            release_task.result()
        except Exception as error:
            lease_release_logger.error(
                "phase lease release failed", extra={"error_type": type(error).__name__}
            )

    async def _release_phase_task(self, execution_id: object, task: Any, lease: Any) -> None:
        if self._phase_tasks.get(execution_id) is task:
            del self._phase_tasks[execution_id]
        if lease is not None:
            await lease.release()

    def _discard_owned_task(self, execution_id: object, task: Any, owns_task: bool) -> None:
        if owns_task and self._phase_tasks.get(execution_id) is task:
            del self._phase_tasks[execution_id]

    async def _route(
        self,
        dependencies: V2ExecutionDependencies,
        question: str,
        answer_mode: str,
        route_decision: RouteDecision | None,
    ) -> tuple[str, tuple[str, ...]]:
        if answer_mode != "terra":
            return "legal_search", ()
        if route_decision is not None:
            return route_decision.route, route_decision.missing_fields
        try:
            decision = await dependencies.route(question)
            return decision.route, decision.missing_fields
        except Exception:
            return "routing_unavailable", ()

    async def _retrieve_if_legal(
        self,
        dependencies: V2ExecutionDependencies,
        payload: Any,
        active: Any,
        repository: Any,
        route: str,
    ) -> tuple[list[Any], Any]:
        if route != "legal_search":
            return [], None
        return await dependencies.retrieve_evidence(payload, active, repository)

    def _generation_hits(
        self,
        dependencies: V2ExecutionDependencies,
        answer_mode: str,
        route: str,
        hits: list[Any],
    ) -> list[Any]:
        if route == "legal_search" and answer_mode == "terra":
            return dependencies.select_generation_hits(
                hits, dependencies.answer_evidence_max_characters
            )
        return hits

    def _stored_or_selected_generation_hits(
        self, dependencies: V2ExecutionDependencies, execution: Any, hits: list[Any]
    ) -> list[Any]:
        stored = execution_generation_hits(execution, hits)
        if stored is not None:
            return stored
        return dependencies.select_generation_hits(
            hits, dependencies.answer_evidence_max_characters
        )

    def _anonymous_capability(
        self, request: PrepareQuestion, dependencies: V2ExecutionDependencies
    ) -> str | None:
        if request.user is not None:
            return None
        return dependencies.execution_capability(request.owner_scope, request.idempotency_key)

    def _core_from_payload(
        self, dependencies: V2ExecutionDependencies, raw_core: Any
    ) -> Any | None:
        if not isinstance(raw_core, dict):
            return None
        return dependencies.make_core_draft(
            str(raw_core.get("summary", "")),
            [value for value in raw_core.get("citation_ids", []) if isinstance(value, str)],
            str(raw_core.get("action", "unanswerable")),
        )

    def _clarification_grounding(
        self, execution: QuestionExecutionRecord
    ) -> ClarificationGrounding | None:
        return clarification_grounding_from_payload(execution.private_payload)

    def _clarification_outcome_payload(
        self,
        request: PrepareQuestion,
        dependencies: V2ExecutionDependencies,
    ) -> dict[str, object]:
        """Persist only transition metadata needed after a grounded finalize."""

        outcome = request.clarification_outcome
        clarification = request.clarification
        if (
            outcome is None
            or clarification is None
            or outcome.case is None
            or outcome.next_status is None
        ):
            raise ValueError("clarification outcome is incomplete")
        if outcome.policy != clarification.policy or outcome.case.case != clarification.case:
            raise ValueError("clarification outcome does not match the frozen grounding state")
        if outcome.next_status not in {
            ClarificationCaseStatus.WAITING_FOR_USER,
            ClarificationCaseStatus.COMPLETED,
        }:
            raise ValueError("clarification outcome has an unsupported transition")
        return {
            "case_id": str(outcome.case.case_id),
            "expected_version": outcome.case.version,
            "next_status": outcome.next_status.value,
            "question_format": [
                {
                    "id": fact.id,
                    "label": fact.label,
                    "why_needed": fact.why_needed,
                    "group": fact.group,
                    "priority": fact.priority,
                }
                for fact in outcome.question_format.facts
            ],
            "remaining_count": len(outcome.case.case.remaining_facts()),
            "capability_hash": dependencies.capability_hash(
                request.payload.clarification_capability
            ),
        }

    async def _persist_clarification_outcome(
        self,
        dependencies: V2ExecutionDependencies,
        execution: QuestionExecutionRecord,
        response: QuestionResponse,
    ) -> QuestionResponse:
        """Make a case wait or complete only after creating a grounded response."""

        raw = execution.private_payload.get("clarification_outcome")
        if raw is None:
            return response
        if not isinstance(raw, dict) or dependencies.clarification_cases is None:
            raise ValueError("clarification transition is unavailable")
        raw_case_id = raw.get("case_id")
        expected_version = raw.get("expected_version")
        raw_status = raw.get("next_status")
        raw_capability_hash = raw.get("capability_hash")
        raw_questions = raw.get("question_format")
        remaining_count = raw.get("remaining_count")
        if (
            not isinstance(raw_case_id, str)
            or not isinstance(expected_version, int)
            or isinstance(expected_version, bool)
            or raw_status not in {"waiting_for_user", "completed"}
            or raw_capability_hash is not None
            and not isinstance(raw_capability_hash, str)
            or not isinstance(raw_questions, list)
            or not isinstance(remaining_count, int)
            or isinstance(remaining_count, bool)
            or remaining_count < 0
        ):
            raise ValueError("clarification transition payload is invalid")
        case_id = UUID(raw_case_id)
        status = ClarificationCaseStatus(raw_status)
        question_format = [
            ClarificationFactPrompt.model_validate(item) for item in raw_questions
        ]
        transition = (
            dependencies.clarification_cases.mark_waiting
            if status is ClarificationCaseStatus.WAITING_FOR_USER
            else dependencies.clarification_cases.complete
        )
        await transition(
            case_id,
            execution.owner_scope,
            expected_version=expected_version,
            capability_hash=raw_capability_hash,
        )
        if status is ClarificationCaseStatus.WAITING_FOR_USER:
            response.clarification = ClarificationContinuation(
                case_id=case_id,
                status="waiting_for_user",
                question_format=question_format,
                remaining_count=remaining_count,
            )
        return response


__all__ = ["V2QuestionExecutionService", "grounding_fallback"]
