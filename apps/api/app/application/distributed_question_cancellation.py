from __future__ import annotations

import asyncio
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from enum import StrEnum
from typing import Protocol
from uuid import UUID


class ExecutionStatus(StrEnum):
    ACCEPTED = "accepted"
    RUNNING = "running"
    CANCEL_REQUESTED = "cancel_requested"
    CANCELLED = "cancelled"
    COMPLETED = "completed"
    FAILED = "failed"


class CancelSignalResult(StrEnum):
    CANCEL_REQUESTED = "cancel_requested"
    PENDING_REGISTRATION = "pending_registration"
    CANCELLED = "cancelled"
    ALREADY_FINISHED = "already_finished"
    NOT_OWNED = "not_owned"


TERMINAL_STATUSES = {
    ExecutionStatus.CANCELLED,
    ExecutionStatus.COMPLETED,
    ExecutionStatus.FAILED,
}


@dataclass(frozen=True)
class QuestionExecution:
    owner: str
    request_id: UUID
    status: ExecutionStatus
    created_at: datetime
    updated_at: datetime


class QuestionCancellationCoordinator(Protocol):
    async def register(self, owner: str, request_id: UUID) -> QuestionExecution: ...

    async def mark_running(self, owner: str, request_id: UUID) -> QuestionExecution: ...

    async def request_cancel(self, owner: str, request_id: UUID) -> CancelSignalResult: ...

    async def is_cancel_requested(self, owner: str, request_id: UUID) -> bool: ...

    async def wait_for_cancel(self, owner: str, request_id: UUID) -> None: ...

    async def finish(
        self, owner: str, request_id: UUID, status: ExecutionStatus
    ) -> QuestionExecution: ...


class ExecutionNotOwnedError(Exception):
    pass


class InvalidExecutionTransitionError(Exception):
    pass


class MemoryQuestionCancellationCoordinator:
    """In-memory test double for the future shared PostgreSQL coordinator.

    Separate request handlers can share this object while retaining independent local
    task registries. Its transition contract is intentionally suitable for a database
    adapter; it does not claim to provide cross-process coordination by itself.
    """

    def __init__(self) -> None:
        self._executions: dict[UUID, QuestionExecution] = {}
        self._cancel_events: dict[UUID, asyncio.Event] = {}
        self._lock = asyncio.Lock()

    async def register(self, owner: str, request_id: UUID) -> QuestionExecution:
        async with self._lock:
            current = self._executions.get(request_id)
            if current is not None:
                self._ensure_owner(current, owner)
                return current
            now = _now()
            execution = QuestionExecution(
                owner=owner,
                request_id=request_id,
                status=ExecutionStatus.ACCEPTED,
                created_at=now,
                updated_at=now,
            )
            self._executions[request_id] = execution
            return execution

    async def mark_running(self, owner: str, request_id: UUID) -> QuestionExecution:
        async with self._lock:
            current = self._owned_execution(owner, request_id)
            if current.status is ExecutionStatus.CANCEL_REQUESTED:
                return current
            if current.status is not ExecutionStatus.ACCEPTED:
                raise InvalidExecutionTransitionError(
                    f"cannot mark {current.status} execution as running"
                )
            return self._replace(current, ExecutionStatus.RUNNING)

    async def request_cancel(self, owner: str, request_id: UUID) -> CancelSignalResult:
        async with self._lock:
            current = self._executions.get(request_id)
            if current is None:
                now = _now()
                self._executions[request_id] = QuestionExecution(
                    owner=owner,
                    request_id=request_id,
                    status=ExecutionStatus.CANCEL_REQUESTED,
                    created_at=now,
                    updated_at=now,
                )
                self._cancel_event(request_id).set()
                return CancelSignalResult.PENDING_REGISTRATION
            if current.owner != owner:
                return CancelSignalResult.NOT_OWNED
            if current.status is ExecutionStatus.CANCELLED:
                return CancelSignalResult.CANCELLED
            if current.status in {ExecutionStatus.COMPLETED, ExecutionStatus.FAILED}:
                return CancelSignalResult.ALREADY_FINISHED
            if current.status is not ExecutionStatus.CANCEL_REQUESTED:
                self._replace(current, ExecutionStatus.CANCEL_REQUESTED)
            self._cancel_event(request_id).set()
            return CancelSignalResult.CANCEL_REQUESTED

    async def is_cancel_requested(self, owner: str, request_id: UUID) -> bool:
        async with self._lock:
            current = self._owned_execution(owner, request_id)
            return current.status is ExecutionStatus.CANCEL_REQUESTED

    async def wait_for_cancel(self, owner: str, request_id: UUID) -> None:
        """Wait for a durable-state-equivalent notification without polling.

        The production adapter must combine an initial authoritative row check with
        a Supabase Realtime notification and a post-subscribe row check so a signal
        cannot be lost between checking and subscribing.
        """

        async with self._lock:
            current = self._owned_execution(owner, request_id)
            event = self._cancel_event(request_id)
            if current.status is ExecutionStatus.CANCEL_REQUESTED:
                event.set()
        await event.wait()

    async def finish(
        self, owner: str, request_id: UUID, status: ExecutionStatus
    ) -> QuestionExecution:
        if status not in TERMINAL_STATUSES:
            raise InvalidExecutionTransitionError("finish requires a terminal status")
        async with self._lock:
            current = self._owned_execution(owner, request_id)
            if current.status in TERMINAL_STATUSES:
                if current.status is not status:
                    raise InvalidExecutionTransitionError(
                        f"cannot change terminal status {current.status} to {status}"
                    )
                return current
            return self._replace(current, status)

    def _owned_execution(self, owner: str, request_id: UUID) -> QuestionExecution:
        current = self._executions.get(request_id)
        if current is None or current.owner != owner:
            raise ExecutionNotOwnedError
        return current

    @staticmethod
    def _ensure_owner(current: QuestionExecution, owner: str) -> None:
        if current.owner != owner:
            raise ExecutionNotOwnedError

    def _replace(
        self, current: QuestionExecution, status: ExecutionStatus
    ) -> QuestionExecution:
        updated = replace(current, status=status, updated_at=_now())
        self._executions[current.request_id] = updated
        return updated

    def _cancel_event(self, request_id: UUID) -> asyncio.Event:
        return self._cancel_events.setdefault(request_id, asyncio.Event())


async def watch_for_distributed_cancel(
    coordinator: QuestionCancellationCoordinator,
    owner: str,
    request_id: UUID,
    task: asyncio.Task[object],
) -> None:
    """Await a shared event and cancel the task owned by this process."""

    cancel_wait = asyncio.create_task(coordinator.wait_for_cancel(owner, request_id))
    task_done = asyncio.create_task(_wait_until_done(task))
    try:
        done, _ = await asyncio.wait(
            {cancel_wait, task_done}, return_when=asyncio.FIRST_COMPLETED
        )
        if cancel_wait in done and not task.done():
            task.cancel()
    finally:
        cancel_wait.cancel()
        task_done.cancel()


async def _wait_until_done(task: asyncio.Task[object]) -> None:
    try:
        await asyncio.shield(task)
    except (asyncio.CancelledError, Exception):
        return


def _now() -> datetime:
    return datetime.now(UTC)
