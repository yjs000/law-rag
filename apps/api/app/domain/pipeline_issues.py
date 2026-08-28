from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class ExecutionPhase(StrEnum):
    PREPARE = "prepare"
    CORE = "core"
    FINALIZE = "finalize"


@dataclass(frozen=True)
class PipelineIssue:
    phase: ExecutionPhase | str
    stage: str
    public_reason_code: str
    recoverable: bool

    def __post_init__(self) -> None:
        if not self.stage or not self.public_reason_code:
            raise ValueError("pipeline issues require a public stage and reason code")
