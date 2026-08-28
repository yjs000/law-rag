from datetime import UTC, datetime, timedelta
from uuid import uuid4

from app.adapters.memory_question_execution import MemoryQuestionExecutionRepository
from app.application.question_phase_coordinator import PhaseResult, QuestionPhaseCoordinator
from app.domain.answer_events import AnswerEvent
from app.domain.question_execution import ExecutionStatus


async def test_timed_out_running_phase_is_recovery_required_without_provider_retry() -> None:
    started_at = datetime(2026, 8, 28, tzinfo=UTC)
    repository = MemoryQuestionExecutionRepository(now=lambda: started_at)
    execution = await repository.prepare_or_get(
        owner_scope="user:1",
        prepare_idempotency_key="crash-uncertain",
        generation_id=uuid4(),
        expires_at=started_at + timedelta(minutes=10),
    )
    await repository.claim_phase(
        execution.execution_id,
        "user:1",
        expected_version=execution.version,
        target=ExecutionStatus.CORE_RUNNING,
    )
    provider_calls = 0

    async def core(record):
        nonlocal provider_calls
        provider_calls += 1
        return PhaseResult(target=ExecutionStatus.CORE_ANSWERED, events=())

    async def finalize(record):
        raise AssertionError("finalize must not run")

    coordinator = QuestionPhaseCoordinator(
        repository,
        core=core,
        finalize=finalize,
        now=lambda: started_at + timedelta(seconds=58),
    )

    events = await coordinator.run(
        execution.execution_id, "user:1", phase="core", capability_hash=None
    )
    current = await repository.get_owned(execution.execution_id, "user:1")

    assert provider_calls == 0
    assert current.status is ExecutionStatus.PHASE_RECOVERY_REQUIRED
    assert events == (AnswerEvent.error("phase_recovery_required"),)
