from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Literal, TypeVar

TimeoutStage = Literal["routing", "embedding", "retrieval", "generation"]
T = TypeVar("T")


class StageTimeoutError(TimeoutError):
    def __init__(self, stage: TimeoutStage) -> None:
        super().__init__(f"{stage} exceeded its request budget")
        self.stage = stage


@dataclass(frozen=True)
class RequestBudget:
    deadline: float
    reserve_seconds: float
    clock: Callable[[], float]

    @classmethod
    def start(
        cls,
        total_seconds: float,
        reserve_seconds: float,
        *,
        clock: Callable[[], float] = time.monotonic,
    ) -> RequestBudget:
        return cls(clock() + total_seconds, reserve_seconds, clock)

    def remaining_seconds(self) -> float:
        return max(0.0, self.deadline - self.clock())

    def stage_timeout_seconds(
        self, cap_seconds: float, *, stage: TimeoutStage = "generation"
    ) -> float:
        timeout = min(cap_seconds, self.remaining_seconds() - self.reserve_seconds)
        if timeout <= 0:
            raise StageTimeoutError(stage)
        return timeout

    async def run(
        self,
        stage: TimeoutStage,
        operation: Callable[[], Awaitable[T]],
        *,
        cap_seconds: float,
    ) -> T:
        timeout = self.stage_timeout_seconds(cap_seconds, stage=stage)
        try:
            async with asyncio.timeout(timeout):
                return await operation()
        except TimeoutError as exc:
            raise StageTimeoutError(stage) from exc
