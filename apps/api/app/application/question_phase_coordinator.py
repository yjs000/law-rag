"""Authoritative, replay-safe v2 phase coordination.

Provider work is supplied as a small application callback and deliberately runs
outside repository transactions.  The result and every event clients may replay
are committed together afterwards.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from app.domain.answer_events import AnswerEvent
from app.domain.question_execution import ExecutionStatus
from app.ports.question_execution import QuestionExecutionRecord, QuestionExecutionRepository


@dataclass(frozen=True)
class PhaseResult:
    target: ExecutionStatus
    events: tuple[AnswerEvent, ...]
    response: Mapping[str, object] | None = None
    private_payload: Mapping[str, object] | None = None


PhaseProducer = Callable[[QuestionExecutionRecord], Awaitable[PhaseResult]]


class QuestionPhaseCoordinator:
    """Start exactly one phase or return its persisted authoritative replay."""

    def __init__(
        self,
        repository: QuestionExecutionRepository,
        *,
        core: PhaseProducer,
        finalize: PhaseProducer,
        now: Callable[[], datetime] | None = None,
        phase_timeout: timedelta = timedelta(seconds=57),
    ) -> None:
        self._repository = repository
        self._core = core
        self._finalize = finalize
        self._now = now or (lambda: datetime.now(UTC))
        self._phase_timeout = phase_timeout

    async def run(
        self,
        execution_id,
        owner_scope: str,
        *,
        phase: str,
        capability_hash: str | None,
    ) -> tuple[AnswerEvent, ...]:
        current = await self._repository.get_owned(
            execution_id, owner_scope, capability_hash=capability_hash
        )
        if current.status is ExecutionStatus.PHASE_RECOVERY_REQUIRED:
            return await self._repository.events_for(
                execution_id, owner_scope, phase=phase, capability_hash=capability_hash
            )
        if current.status is ExecutionStatus.CANCELLED:
            return (AnswerEvent.cancelled(),)
        if self._is_timed_out_running(current):
            recovered = await self._repository.finish_phase(
                execution_id,
                owner_scope,
                expected_version=current.version,
                target=ExecutionStatus.PHASE_RECOVERY_REQUIRED,
                phase=phase,
                events=(AnswerEvent.error("phase_recovery_required"),),
                capability_hash=capability_hash,
            )
            del recovered
            return await self._repository.events_for(
                execution_id, owner_scope, phase=phase, capability_hash=capability_hash
            )

        running, replay_status, producer = self._phase_contract(phase)
        if current.status is replay_status or (
            phase == "core" and current.status is ExecutionStatus.CORE_REPAIR_REQUIRED
        ) or (
            phase == "finalize" and current.status is ExecutionStatus.COMPLETED
        ):
            return await self._repository.events_for(
                execution_id, owner_scope, phase=phase, capability_hash=capability_hash
            )
        if current.status is running:
            # A live invocation might still own the provider call.  Never start
            # another one; the browser reconnects with bounded backoff.
            return (AnswerEvent(event_type="status", payload={"status": current.status.value}),)

        claim = await self._repository.claim_phase(
            execution_id,
            owner_scope,
            expected_version=current.version,
            target=running,
            private_payload=(
                {"finalize_source_status": current.status.value}
                if phase == "finalize"
                else None
            ),
            capability_hash=capability_hash,
        )
        if not claim.started:
            return await self.run(
                execution_id, owner_scope, phase=phase, capability_hash=capability_hash
            )
        try:
            result = await producer(claim.execution)
        except Exception:  # never expose provider text or traceback through SSE
            result = (
                PhaseResult(
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
                if phase == "core"
                else PhaseResult(
                    target=ExecutionStatus.FAILED,
                    events=(AnswerEvent.error("phase_processing_failed"),),
                )
            )
        await self._repository.finish_phase(
            execution_id,
            owner_scope,
            expected_version=claim.execution.version,
            target=result.target,
            phase=phase,
            events=result.events,
            response=result.response,
            private_payload=result.private_payload,
            capability_hash=capability_hash,
        )
        return await self._repository.events_for(
            execution_id, owner_scope, phase=phase, capability_hash=capability_hash
        )

    def _phase_contract(self, phase: str):
        if phase == "core":
            return (
                ExecutionStatus.CORE_RUNNING,
                ExecutionStatus.CORE_ANSWERED,
                self._core,
            )
        if phase == "finalize":
            return (
                ExecutionStatus.FINALIZE_RUNNING,
                ExecutionStatus.COMPLETED,
                self._finalize,
            )
        raise ValueError("unknown execution phase")

    def _is_timed_out_running(self, record: QuestionExecutionRecord) -> bool:
        return record.status in {
            ExecutionStatus.CORE_RUNNING,
            ExecutionStatus.FINALIZE_RUNNING,
        } and record.updated_at + self._phase_timeout <= self._now()
