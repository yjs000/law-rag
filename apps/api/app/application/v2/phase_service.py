"""Prepare, core, and finalize use cases for v2 question executions."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from datetime import timedelta
from typing import Any, Literal

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
    core_degraded_response,
    core_is_grounded,
    grounding_fallback,
    response_is_grounded,
)
from app.domain.answer_events import AnswerEvent
from app.domain.grounding import CitationRegistry
from app.domain.question_execution import ExecutionSnapshot, ExecutionStatus, next_action_for
from app.domain.schemas import MockUser, QuestionResponse
from app.ports.question_execution import ExecutionNotFound, QuestionExecutionRecord


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
            request.payload.question, request.payload.answer_mode
        )
        active = await dependencies.active_provider().active()
        hits, corpus_as_of = await self._retrieve_if_legal(
            dependencies, request.payload, active, repository, route
        )
        generation_hits = self._generation_hits(
            dependencies, request.payload.answer_mode, route, hits
        )
        execution_capability = self._anonymous_capability(request, dependencies)
        execution = await dependencies.executions.prepare_or_get(
            owner_scope=request.owner_scope,
            prepare_idempotency_key=request.idempotency_key,
            generation_id=active.generation.id,
            capability_hash=dependencies.capability_hash(execution_capability),
            private_payload={
                "request": request.payload.model_dump(mode="json"),
                "hits": [hit.model_dump(mode="json") for hit in hits],
                "generation_hits": [hit.model_dump(mode="json") for hit in generation_hits],
                "corpus_as_of": corpus_as_of.isoformat() if corpus_as_of is not None else None,
                "route": route,
                "missing_fields": list(missing_fields),
            },
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
        draft = await dependencies.answerer().answer(payload, generation_hits)
        if not dependencies.validate_response(draft, generation_hits):
            raise ValueError("generated answer did not satisfy the citation contract")
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
            )

        generation_hits = self._stored_or_selected_generation_hits(dependencies, execution, hits)
        draft = await dependencies.answerer().answer_core(payload, generation_hits)
        if not dependencies.validate_core(draft, generation_hits):
            raise ValueError("generated core did not satisfy the citation contract")
        return draft, citations_for_hits(generation_hits)

    async def run_core(self, execution: QuestionExecutionRecord) -> PhaseResult:
        """Validate a core draft before persisting the only publishable core event."""

        core, citations = await self.core_from_frozen_evidence(execution)
        if not core_is_grounded(core, CitationRegistry(execution.frozen_citations)):
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
        core_data = core.model_dump(mode="json")
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
        if not response_is_grounded(response, CitationRegistry(execution.frozen_citations)):
            response = core_degraded_response(payload, core, execution.private_payload)
            degraded = True
        elif core is not None:
            response.summary = core.summary
            response.action = core.action
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
            core=self.run_core,
            finalize=lambda current: self.run_finalize(current, request.user),
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
                lambda completed: asyncio.create_task(
                    self._release_phase_task(request.execution_id, completed, lease)
                )
            )
            start_gate.set()
        return PhaseRun(task=task, owns_task=owns_task)

    async def _release_phase_task(self, execution_id: object, task: Any, lease: Any) -> None:
        if self._phase_tasks.get(execution_id) is task:
            del self._phase_tasks[execution_id]
        if lease is not None:
            await lease.release()

    def _discard_owned_task(self, execution_id: object, task: Any, owns_task: bool) -> None:
        if owns_task and self._phase_tasks.get(execution_id) is task:
            del self._phase_tasks[execution_id]

    async def _route(self, question: str, answer_mode: str) -> tuple[str, tuple[str, ...]]:
        if answer_mode != "terra":
            return "legal_search", ()
        try:
            decision = await self._dependencies().route(question)
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


__all__ = ["V2QuestionExecutionService", "grounding_fallback"]
