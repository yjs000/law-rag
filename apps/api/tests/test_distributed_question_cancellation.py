import asyncio
from uuid import uuid4

import pytest

from app.application.distributed_question_cancellation import (
    CancelSignalResult,
    ExecutionNotOwnedError,
    ExecutionStatus,
    MemoryQuestionCancellationCoordinator,
    watch_for_distributed_cancel,
)


@pytest.mark.asyncio
async def test_cancel_before_registration_creates_tombstone_and_prevents_start() -> None:
    coordinator = MemoryQuestionCancellationCoordinator()
    request_id = uuid4()

    result = await coordinator.request_cancel("user:a", request_id)
    registered = await coordinator.register("user:a", request_id)
    running = await coordinator.mark_running("user:a", request_id)

    assert result is CancelSignalResult.PENDING_REGISTRATION
    assert registered.status is ExecutionStatus.CANCEL_REQUESTED
    assert running.status is ExecutionStatus.CANCEL_REQUESTED


@pytest.mark.asyncio
async def test_cancel_from_another_handler_reaches_the_active_task() -> None:
    coordinator = MemoryQuestionCancellationCoordinator()
    request_id = uuid4()
    started = asyncio.Event()
    cancelled = asyncio.Event()

    async def work() -> None:
        try:
            started.set()
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            cancelled.set()
            raise

    await coordinator.register("user:a", request_id)
    await coordinator.mark_running("user:a", request_id)
    active_task = asyncio.create_task(work())
    watcher = asyncio.create_task(
        watch_for_distributed_cancel(
            coordinator,
            "user:a",
            request_id,
            active_task,
        )
    )
    await started.wait()

    # This call represents a cancel endpoint with a different process-local registry.
    result = await coordinator.request_cancel("user:a", request_id)
    await watcher
    with pytest.raises(asyncio.CancelledError):
        await active_task

    assert result is CancelSignalResult.CANCEL_REQUESTED
    assert cancelled.is_set()


@pytest.mark.asyncio
async def test_completed_work_stops_watcher_without_cancel_signal() -> None:
    coordinator = MemoryQuestionCancellationCoordinator()
    request_id = uuid4()
    await coordinator.register("user:a", request_id)
    await coordinator.mark_running("user:a", request_id)

    active_task = asyncio.create_task(asyncio.sleep(0))
    await watch_for_distributed_cancel(
        coordinator, "user:a", request_id, active_task
    )

    assert active_task.done()
    assert not active_task.cancelled()


@pytest.mark.asyncio
async def test_owner_cannot_cancel_or_observe_another_owners_execution() -> None:
    coordinator = MemoryQuestionCancellationCoordinator()
    request_id = uuid4()
    await coordinator.register("user:a", request_id)

    assert (
        await coordinator.request_cancel("user:b", request_id)
        is CancelSignalResult.NOT_OWNED
    )
    with pytest.raises(ExecutionNotOwnedError):
        await coordinator.is_cancel_requested("user:b", request_id)
    with pytest.raises(ExecutionNotOwnedError):
        await coordinator.register("user:b", request_id)


@pytest.mark.asyncio
async def test_terminal_states_return_idempotent_cancel_results() -> None:
    coordinator = MemoryQuestionCancellationCoordinator()
    completed_id = uuid4()
    cancelled_id = uuid4()

    for request_id, status in (
        (completed_id, ExecutionStatus.COMPLETED),
        (cancelled_id, ExecutionStatus.CANCELLED),
    ):
        await coordinator.register("user:a", request_id)
        await coordinator.mark_running("user:a", request_id)
        await coordinator.finish("user:a", request_id, status)

    assert (
        await coordinator.request_cancel("user:a", completed_id)
        is CancelSignalResult.ALREADY_FINISHED
    )
    assert (
        await coordinator.request_cancel("user:a", cancelled_id)
        is CancelSignalResult.CANCELLED
    )
