from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from app.adapters.capacity_leases import MemoryConcurrencyLimiter, PostgresConcurrencyLimiter
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
