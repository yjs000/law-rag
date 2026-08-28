from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from app.adapters.capacity_leases import (
    MemoryConcurrencyLimiter,
    PostgresCapacityLeaseStore,
    PostgresConcurrencyLimiter,
)
from app.domain.pipeline_issues import ExecutionPhase
from app.ports.question_execution import SystemBusy


async def test_competing_starts_admit_one_and_release_allows_the_next_execution() -> None:
    now = datetime(2026, 8, 28, tzinfo=UTC)
    limiter = MemoryConcurrencyLimiter(provider="ultra", slots=1, now=lambda: now)
    first = await limiter.acquire(uuid4(), ExecutionPhase.CORE, now + timedelta(seconds=10))

    with pytest.raises(SystemBusy):
        await limiter.acquire(uuid4(), ExecutionPhase.CORE, now + timedelta(seconds=10))

    await first.release()
    second = await limiter.acquire(uuid4(), ExecutionPhase.CORE, now + timedelta(seconds=10))

    assert second.slot == 0


async def test_stale_lease_is_reclaimed_and_cancellation_release_is_idempotent() -> None:
    instant = datetime(2026, 8, 28, tzinfo=UTC)
    clock = {"now": instant}
    limiter = MemoryConcurrencyLimiter(provider="ultra", slots=1, now=lambda: clock["now"])
    first = await limiter.acquire(uuid4(), ExecutionPhase.CORE, instant + timedelta(seconds=1))
    clock["now"] = instant + timedelta(seconds=2)

    replacement = await limiter.acquire(
        uuid4(), ExecutionPhase.FINALIZE, instant + timedelta(seconds=5)
    )
    await first.release()
    await replacement.release()
    assert await limiter.active_count() == 0


async def test_same_execution_phase_cannot_acquire_a_second_capacity_lease() -> None:
    now = datetime(2026, 8, 28, tzinfo=UTC)
    limiter = MemoryConcurrencyLimiter(provider="ultra", slots=2, now=lambda: now)
    execution_id = uuid4()
    await limiter.acquire(execution_id, ExecutionPhase.CORE, now + timedelta(seconds=10))

    with pytest.raises(SystemBusy):
        await limiter.acquire(execution_id, ExecutionPhase.CORE, now + timedelta(seconds=10))


async def test_database_error_fails_closed_as_system_busy() -> None:
    class BrokenLeaseStore:
        async def acquire_slot(self, **kwargs):
            raise RuntimeError("database connection failed")

    limiter = PostgresConcurrencyLimiter(
        provider="ultra", slots=1, lease_store=BrokenLeaseStore()
    )

    with pytest.raises(SystemBusy):
        await limiter.acquire(
            uuid4(), ExecutionPhase.CORE, datetime(2026, 8, 28, tzinfo=UTC) + timedelta(seconds=5)
        )


async def test_postgres_capacity_claim_serializes_provider_and_rejects_expired_deadlines() -> None:
    class Result:
        def mappings(self):
            return self

        def one_or_none(self):
            return None

    class Connection:
        def __init__(self):
            self.calls = []

        async def execute(self, statement, parameters=None):
            self.calls.append((str(statement), parameters or {}))
            return Result()

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
    store = PostgresCapacityLeaseStore(engine)  # type: ignore[arg-type]
    assert await store.acquire_slot(
        provider="ultra",
        slots=2,
        execution_id=uuid4(),
        phase=ExecutionPhase.CORE,
        deadline=datetime(2026, 8, 28, tzinfo=UTC),
    ) is None

    statements = "\n".join(statement for statement, _ in engine.connection.calls)
    assert "pg_advisory_xact_lock" in statements
    assert ":expires_at > now()" in statements
    assert "ON CONFLICT DO NOTHING" in statements
