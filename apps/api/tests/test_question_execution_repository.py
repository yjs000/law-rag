from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from app.adapters.memory_question_execution import MemoryQuestionExecutionRepository
from app.adapters.postgres_question_execution import PostgresQuestionExecutionRepository
from app.domain.grounding import FrozenCitation
from app.domain.question_execution import ExecutionStatus
from app.ports.question_execution import ExecutionConflict, ExecutionNotFound


@pytest.fixture
def repository() -> MemoryQuestionExecutionRepository:
    return MemoryQuestionExecutionRepository(now=lambda: datetime(2026, 8, 28, tzinfo=UTC))


async def test_prepare_deduplicates_owner_and_idempotency_key(
    repository: MemoryQuestionExecutionRepository,
) -> None:
    expires_at = datetime(2026, 8, 28, tzinfo=UTC) + timedelta(minutes=5)
    generation_id = uuid4()

    first = await repository.prepare_or_get(
        owner_scope="user:1",
        prepare_idempotency_key="request-key",
        generation_id=generation_id,
        private_payload={"question": "비공개 질문"},
        expires_at=expires_at,
    )
    replay = await repository.prepare_or_get(
        owner_scope="user:1",
        prepare_idempotency_key="request-key",
        generation_id=uuid4(),
        private_payload={"question": "바꾸려는 질문"},
        expires_at=expires_at,
    )

    assert replay.execution_id == first.execution_id
    assert replay.generation_id == generation_id
    assert replay.private_payload == {"question": "비공개 질문"}


async def test_foreign_owner_or_wrong_capability_is_not_found(
    repository: MemoryQuestionExecutionRepository,
) -> None:
    execution = await repository.prepare_or_get(
        owner_scope="anonymous",
        prepare_idempotency_key="request-key",
        generation_id=uuid4(),
        capability_hash="expected-capability",
        expires_at=datetime(2026, 8, 28, tzinfo=UTC) + timedelta(minutes=5),
    )

    with pytest.raises(ExecutionNotFound):
        await repository.get_owned(execution.execution_id, "user:other")
    with pytest.raises(ExecutionNotFound):
        await repository.get_owned(
            execution.execution_id, "anonymous", capability_hash="wrong-capability"
        )


async def test_running_and_completed_phase_replays_return_the_authoritative_snapshot(
    repository: MemoryQuestionExecutionRepository,
) -> None:
    execution = await repository.prepare_or_get(
        owner_scope="user:1",
        prepare_idempotency_key="request-key",
        generation_id=uuid4(),
        expires_at=datetime(2026, 8, 28, tzinfo=UTC) + timedelta(minutes=5),
    )
    running = await repository.transition_phase(
        execution.execution_id,
        "user:1",
        expected_version=0,
        target=ExecutionStatus.CORE_RUNNING,
    )
    replay = await repository.transition_phase(
        execution.execution_id,
        "user:1",
        expected_version=0,
        target=ExecutionStatus.CORE_RUNNING,
    )
    core = await repository.transition_phase(
        execution.execution_id,
        "user:1",
        expected_version=1,
        target=ExecutionStatus.CORE_ANSWERED,
    )
    completed = await repository.complete(
        execution.execution_id,
        "user:1",
        expected_version=2,
        response={"outcome": "normal"},
    )
    complete_replay = await repository.complete(
        execution.execution_id,
        "user:1",
        expected_version=2,
        response={"outcome": "normal"},
    )

    assert replay == running
    assert core.status is ExecutionStatus.CORE_ANSWERED
    assert completed.status is ExecutionStatus.COMPLETED
    assert complete_replay == completed


async def test_phase_claim_distinguishes_the_single_starter_from_a_replay(
    repository: MemoryQuestionExecutionRepository,
) -> None:
    execution = await repository.prepare_or_get(
        owner_scope="user:1",
        prepare_idempotency_key="request-key",
        generation_id=uuid4(),
        expires_at=datetime(2026, 8, 28, tzinfo=UTC) + timedelta(minutes=5),
    )

    starter = await repository.claim_phase(
        execution.execution_id,
        "user:1",
        expected_version=0,
        target=ExecutionStatus.CORE_RUNNING,
    )
    replay = await repository.claim_phase(
        execution.execution_id,
        "user:1",
        expected_version=0,
        target=ExecutionStatus.CORE_RUNNING,
    )

    assert starter.started is True
    assert replay.started is False
    assert replay.execution == starter.execution


async def test_stale_transition_cannot_overwrite_a_newer_snapshot(
    repository: MemoryQuestionExecutionRepository,
) -> None:
    execution = await repository.prepare_or_get(
        owner_scope="user:1",
        prepare_idempotency_key="request-key",
        generation_id=uuid4(),
        expires_at=datetime(2026, 8, 28, tzinfo=UTC) + timedelta(minutes=5),
    )
    await repository.transition_phase(
        execution.execution_id,
        "user:1",
        expected_version=0,
        target=ExecutionStatus.CORE_RUNNING,
    )

    with pytest.raises(ExecutionConflict):
        await repository.transition_phase(
            execution.execution_id,
            "user:1",
            expected_version=0,
            target=ExecutionStatus.CORE_REPAIR_REQUIRED,
        )


async def test_expiry_transitions_an_inflight_execution_and_keeps_its_idempotency_record(
    repository: MemoryQuestionExecutionRepository,
) -> None:
    expires_at = datetime(2026, 8, 28, tzinfo=UTC) + timedelta(seconds=1)
    execution = await repository.prepare_or_get(
        owner_scope="user:1",
        prepare_idempotency_key="request-key",
        generation_id=uuid4(),
        expires_at=expires_at,
    )
    await repository.transition_phase(
        execution.execution_id,
        "user:1",
        expected_version=0,
        target=ExecutionStatus.CORE_RUNNING,
    )

    expired = await repository.expire(expires_at)
    replay = await repository.prepare_or_get(
        owner_scope="user:1",
        prepare_idempotency_key="request-key",
        generation_id=uuid4(),
        expires_at=expires_at + timedelta(minutes=5),
    )

    assert expired == (execution.execution_id,)
    assert replay.status is ExecutionStatus.EXPIRED
    assert replay.private_payload == {}


async def test_expiry_scrubs_private_payload_capability_and_terminal_response(
    repository: MemoryQuestionExecutionRepository,
) -> None:
    expires_at = datetime(2026, 8, 28, tzinfo=UTC) + timedelta(seconds=1)
    execution = await repository.prepare_or_get(
        owner_scope="anonymous",
        prepare_idempotency_key="request-key",
        generation_id=uuid4(),
        capability_hash="capability",
        private_payload={"question": "비공개 질문"},
        frozen_citations=(FrozenCitation(id="C1", quote="법령 원문"),),
        expires_at=expires_at,
    )
    running = await repository.transition_phase(
        execution.execution_id,
        "anonymous",
        expected_version=0,
        target=ExecutionStatus.CORE_RUNNING,
        capability_hash="capability",
    )
    answered = await repository.transition_phase(
        execution.execution_id,
        "anonymous",
        expected_version=running.version,
        target=ExecutionStatus.CORE_ANSWERED,
        capability_hash="capability",
    )
    await repository.complete(
        execution.execution_id,
        "anonymous",
        expected_version=answered.version,
        response={"answer": "short-lived response"},
        capability_hash="capability",
    )

    await repository.expire(expires_at)
    scrubbed = await repository.get_owned(execution.execution_id, "anonymous")

    assert scrubbed.status is ExecutionStatus.COMPLETED
    assert scrubbed.capability_hash is None
    assert scrubbed.private_payload == {}
    assert scrubbed.frozen_citations == ()
    assert scrubbed.verified_response is None


async def test_anonymous_owner_can_cancel_with_its_execution_capability(
    repository: MemoryQuestionExecutionRepository,
) -> None:
    execution = await repository.prepare_or_get(
        owner_scope="anonymous",
        prepare_idempotency_key="request-key",
        generation_id=uuid4(),
        capability_hash="capability",
        expires_at=datetime(2026, 8, 28, tzinfo=UTC) + timedelta(minutes=5),
    )

    cancelled = await repository.cancel(
        execution.execution_id, "anonymous", capability_hash="capability"
    )

    assert cancelled.status is ExecutionStatus.CANCELLED


async def test_event_sequence_is_persisted_once_before_any_replay_is_visible(
    repository: MemoryQuestionExecutionRepository,
) -> None:
    execution = await repository.prepare_or_get(
        owner_scope="user:1",
        prepare_idempotency_key="request-key",
        generation_id=uuid4(),
        expires_at=datetime(2026, 8, 28, tzinfo=UTC) + timedelta(minutes=5),
    )
    from app.domain.answer_events import AnswerEvent

    event = AnswerEvent(event_type="summary", payload={"sentence": "검증됨"})
    assert await repository.append_event(
        execution.execution_id, "user:1", phase="core", sequence=0, event=event
    ) == event
    assert await repository.append_event(
        execution.execution_id, "user:1", phase="core", sequence=0, event=event
    ) == event

    with pytest.raises(ExecutionConflict):
        await repository.append_event(
            execution.execution_id,
            "user:1",
            phase="core",
            sequence=0,
            event=AnswerEvent(event_type="summary", payload={"sentence": "다름"}),
        )


async def test_finish_phase_makes_status_and_replayable_events_visible_together(
    repository: MemoryQuestionExecutionRepository,
) -> None:
    execution = await repository.prepare_or_get(
        owner_scope="user:1",
        prepare_idempotency_key="atomic-phase",
        generation_id=uuid4(),
        expires_at=datetime(2026, 8, 28, tzinfo=UTC) + timedelta(minutes=5),
    )
    running = await repository.claim_phase(
        execution.execution_id,
        "user:1",
        expected_version=execution.version,
        target=ExecutionStatus.CORE_RUNNING,
    )
    from app.domain.answer_events import AnswerEvent

    answered = await repository.finish_phase(
        execution.execution_id,
        "user:1",
        expected_version=running.execution.version,
        target=ExecutionStatus.CORE_ANSWERED,
        phase="core",
        events=(
            AnswerEvent(event_type="summary", payload={"summary": "검증됨"}),
            AnswerEvent(
                event_type="phase_complete",
                payload={"status": "core_answered", "next_action": "generate_detail"},
            ),
        ),
    )

    assert answered.status is ExecutionStatus.CORE_ANSWERED
    assert [event.event_type for event in await repository.events_for(
        execution.execution_id, "user:1", phase="core"
    )] == ["summary", "phase_complete"]


async def test_postgres_transition_uses_owner_and_optimistic_version_conditions() -> None:
    execution_id = uuid4()
    generation_id = uuid4()
    now = datetime(2026, 8, 28, tzinfo=UTC)

    def row(status: str, version: int):
        return {
            "execution_id": execution_id,
            "owner_scope": "user:1",
            "prepare_idempotency_key": "request-key",
            "capability_hash": None,
            "generation_id": generation_id,
            "status": status,
            "version": version,
            "private_payload": {},
            "frozen_citations": [],
            "verified_response": None,
            "expires_at": now + timedelta(minutes=5),
            "created_at": now,
            "updated_at": now,
        }

    class Result:
        def __init__(self, value):
            self.value = value

        def mappings(self):
            return self

        def one_or_none(self):
            return self.value

    class Connection:
        def __init__(self):
            self.calls = []
            self.rows = iter((row("prepared", 0), row("core_running", 1)))

        async def execute(self, statement, parameters):
            self.calls.append((str(statement), parameters))
            return Result(next(self.rows))

    class Begin:
        def __init__(self, connection):
            self.connection = connection

        async def __aenter__(self):
            return self.connection

        async def __aexit__(self, *args):
            return False

    class Engine:
        def __init__(self):
            self.connection = Connection()

        def begin(self):
            return Begin(self.connection)

    engine = Engine()
    repository = PostgresQuestionExecutionRepository(engine)  # type: ignore[arg-type]

    updated = await repository.transition_phase(
        execution_id,
        "user:1",
        expected_version=0,
        target=ExecutionStatus.CORE_RUNNING,
    )

    update_sql, parameters = engine.connection.calls[-1]
    assert updated.status is ExecutionStatus.CORE_RUNNING
    assert "owner_scope=:owner_scope" in update_sql
    assert "version=:expected_version" in update_sql
    assert parameters["expected_version"] == 0
