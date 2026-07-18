from __future__ import annotations

import asyncio
from uuid import UUID


class QuestionTaskRegistry:
    """Process-local active question tasks, scoped by a non-secret owner key."""

    def __init__(self) -> None:
        self._tasks: dict[tuple[str, UUID], asyncio.Task[object]] = {}
        self._lock = asyncio.Lock()

    async def register(
        self, owner: str, request_id: UUID, task: asyncio.Task[object]
    ) -> bool:
        key = (owner, request_id)
        async with self._lock:
            if key in self._tasks:
                return False
            self._tasks[key] = task
            return True

    async def cancel(self, owner: str, request_id: UUID) -> bool:
        async with self._lock:
            task = self._tasks.get((owner, request_id))
            if task is None or task.done():
                return False
            task.cancel()
            return True

    async def unregister(
        self, owner: str, request_id: UUID, task: asyncio.Task[object]
    ) -> None:
        key = (owner, request_id)
        async with self._lock:
            if self._tasks.get(key) is task:
                self._tasks.pop(key, None)

    async def active_count(self) -> int:
        async with self._lock:
            return len(self._tasks)
