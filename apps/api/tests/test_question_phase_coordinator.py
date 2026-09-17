from datetime import UTC, datetime, timedelta
from uuid import uuid4

from app.adapters.memory_question_execution import MemoryQuestionExecutionRepository
from app.application.question_phase_coordinator import PhaseResult, QuestionPhaseCoordinator
from app.domain.answer_events import AnswerEvent
from app.domain.provider_attempts import ProviderAttemptsExhausted
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


async def test_finalize_claim_preserves_core_repair_source_for_the_producer() -> None:
    """The finalize producer must distinguish repair from ordinary missing-core states."""

    started_at = datetime(2026, 9, 3, tzinfo=UTC)
    repository = MemoryQuestionExecutionRepository(now=lambda: started_at)
    execution = await repository.prepare_or_get(
        owner_scope="user:1",
        prepare_idempotency_key="core-repair-source",
        generation_id=uuid4(),
        expires_at=started_at + timedelta(minutes=10),
    )
    core_claim = await repository.claim_phase(
        execution.execution_id,
        "user:1",
        expected_version=execution.version,
        target=ExecutionStatus.CORE_RUNNING,
    )
    await repository.finish_phase(
        execution.execution_id,
        "user:1",
        expected_version=core_claim.execution.version,
        target=ExecutionStatus.CORE_REPAIR_REQUIRED,
        phase="core",
        events=(),
    )
    observed: dict[str, object] = {}

    async def core(record):
        raise AssertionError(f"core must not run again: {record.status}")

    async def finalize(record):
        observed["status"] = record.status
        observed["source_status"] = record.private_payload["finalize_source_status"]
        return PhaseResult(target=ExecutionStatus.COMPLETED, events=())

    coordinator = QuestionPhaseCoordinator(repository, core=core, finalize=finalize)
    events = await coordinator.run(
        execution.execution_id, "user:1", phase="finalize", capability_hash=None
    )
    current = await repository.get_owned(execution.execution_id, "user:1")

    assert events == ()
    assert observed == {
        "status": ExecutionStatus.FINALIZE_RUNNING,
        "source_status": ExecutionStatus.CORE_REPAIR_REQUIRED.value,
    }
    assert current.status is ExecutionStatus.COMPLETED
    assert (
        current.private_payload["finalize_source_status"]
        == ExecutionStatus.CORE_REPAIR_REQUIRED.value
    )


async def test_core_provider_exhaustion_persists_a_safe_terminal_replay() -> None:
    started_at = datetime(2026, 9, 15, tzinfo=UTC)
    repository = MemoryQuestionExecutionRepository(now=lambda: started_at)
    execution = await repository.prepare_or_get(
        owner_scope="user:1",
        prepare_idempotency_key="core-provider-exhausted",
        generation_id=uuid4(),
        expires_at=started_at + timedelta(minutes=10),
    )
    core_calls = 0
    finalize_calls = 0

    async def core(record):
        nonlocal core_calls
        core_calls += 1
        raise ProviderAttemptsExhausted(failure_kind="provider_http", upstream_status=503)

    async def finalize(record):
        nonlocal finalize_calls
        finalize_calls += 1
        return PhaseResult(target=ExecutionStatus.COMPLETED, events=())

    coordinator = QuestionPhaseCoordinator(repository, core=core, finalize=finalize)

    events = await coordinator.run(
        execution.execution_id, "user:1", phase="core", capability_hash=None
    )
    replay = await coordinator.run(
        execution.execution_id, "user:1", phase="core", capability_hash=None
    )
    current = await repository.get_owned(execution.execution_id, "user:1")

    assert current.status is ExecutionStatus.FAILED
    assert events == replay == (AnswerEvent.error("provider_unavailable"),)
    assert core_calls == 1
    assert finalize_calls == 0


async def test_finalize_provider_exhaustion_persists_a_safe_terminal_replay() -> None:
    started_at = datetime(2026, 9, 15, tzinfo=UTC)
    repository = MemoryQuestionExecutionRepository(now=lambda: started_at)
    execution = await repository.prepare_or_get(
        owner_scope="user:1",
        prepare_idempotency_key="finalize-provider-exhausted",
        generation_id=uuid4(),
        expires_at=started_at + timedelta(minutes=10),
    )
    core_calls = 0
    finalize_calls = 0

    async def core(record):
        nonlocal core_calls
        core_calls += 1
        return PhaseResult(target=ExecutionStatus.CORE_ANSWERED, events=())

    async def finalize(record):
        nonlocal finalize_calls
        finalize_calls += 1
        raise ProviderAttemptsExhausted(failure_kind="provider_http", upstream_status=503)

    coordinator = QuestionPhaseCoordinator(repository, core=core, finalize=finalize)
    await coordinator.run(execution.execution_id, "user:1", phase="core", capability_hash=None)

    events = await coordinator.run(
        execution.execution_id, "user:1", phase="finalize", capability_hash=None
    )
    replay = await coordinator.run(
        execution.execution_id, "user:1", phase="finalize", capability_hash=None
    )
    cross_phase_replay = await coordinator.run(
        execution.execution_id, "user:1", phase="core", capability_hash=None
    )
    current = await repository.get_owned(execution.execution_id, "user:1")

    assert current.status is ExecutionStatus.FAILED
    assert events == replay == cross_phase_replay == (AnswerEvent.error("provider_unavailable"),)
    assert core_calls == 1
    assert finalize_calls == 1


async def test_finalize_provider_exhaustion_replays_terminal_failure_over_nonempty_core_events(
) -> None:
    """A terminal finalize failure must win over an earlier successful core replay."""

    started_at = datetime(2026, 9, 15, tzinfo=UTC)
    repository = MemoryQuestionExecutionRepository(now=lambda: started_at)
    execution = await repository.prepare_or_get(
        owner_scope="user:1",
        prepare_idempotency_key="finalize-provider-exhausted-with-core-events",
        generation_id=uuid4(),
        expires_at=started_at + timedelta(minutes=10),
    )
    core_event = AnswerEvent(event_type="summary", payload={"summary": "확인된 요약"})
    core_calls = 0
    finalize_calls = 0

    async def core(record):
        nonlocal core_calls
        core_calls += 1
        return PhaseResult(
            target=ExecutionStatus.CORE_ANSWERED,
            events=(
                core_event,
                AnswerEvent(
                    event_type="phase_complete",
                    payload={
                        "status": ExecutionStatus.CORE_ANSWERED.value,
                        "next_action": "generate_detail",
                    },
                ),
            ),
        )

    async def finalize(record):
        nonlocal finalize_calls
        finalize_calls += 1
        raise ProviderAttemptsExhausted(failure_kind="provider_http", upstream_status=503)

    coordinator = QuestionPhaseCoordinator(repository, core=core, finalize=finalize)
    core_events = await coordinator.run(
        execution.execution_id, "user:1", phase="core", capability_hash=None
    )
    terminal_events = await coordinator.run(
        execution.execution_id, "user:1", phase="finalize", capability_hash=None
    )
    core_replay = await coordinator.run(
        execution.execution_id, "user:1", phase="core", capability_hash=None
    )
    current = await repository.get_owned(execution.execution_id, "user:1")

    assert core_events[0] == core_event
    assert current.status is ExecutionStatus.FAILED
    assert terminal_events == core_replay == (AnswerEvent.error("provider_unavailable"),)
    assert core_calls == 1
    assert finalize_calls == 1


async def test_core_value_error_still_requires_grounding_repair() -> None:
    started_at = datetime(2026, 9, 15, tzinfo=UTC)
    repository = MemoryQuestionExecutionRepository(now=lambda: started_at)
    execution = await repository.prepare_or_get(
        owner_scope="user:1",
        prepare_idempotency_key="core-grounding-repair",
        generation_id=uuid4(),
        expires_at=started_at + timedelta(minutes=10),
    )

    async def core(record):
        raise ValueError("grounding validation failed")

    async def finalize(record):
        raise AssertionError("finalize must not run")

    coordinator = QuestionPhaseCoordinator(repository, core=core, finalize=finalize)

    events = await coordinator.run(
        execution.execution_id, "user:1", phase="core", capability_hash=None
    )
    current = await repository.get_owned(execution.execution_id, "user:1")

    assert current.status is ExecutionStatus.CORE_REPAIR_REQUIRED
    assert events == (
        AnswerEvent(
            event_type="phase_complete",
            payload={
                "status": ExecutionStatus.CORE_REPAIR_REQUIRED.value,
                "next_action": "repair_core",
            },
        ),
    )
