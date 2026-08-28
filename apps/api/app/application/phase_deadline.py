from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta


@dataclass(frozen=True)
class PhaseDeadline:
    deadline_at: datetime

    @classmethod
    def started(cls, started_at: datetime, *, provider_budget_seconds: float) -> PhaseDeadline:
        if provider_budget_seconds <= 0:
            raise ValueError("provider budget must be positive")
        return cls(deadline_at=started_at + timedelta(seconds=provider_budget_seconds))

    def remaining_seconds(self, now: datetime) -> float:
        return max(0, (self.deadline_at - now).total_seconds())
