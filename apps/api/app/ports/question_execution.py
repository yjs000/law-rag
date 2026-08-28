from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID

from app.domain.answer_events import AnswerEvent
from app.domain.grounding import FrozenCitation
from app.domain.pipeline_issues import PipelineIssue
from app.domain.question_execution import ExecutionStatus


class ExecutionNotFound(Exception):
    """Use one public error for absent, foreign, and capability-mismatched executions."""


class ExecutionConflict(Exception):
    pass


class SystemBusy(Exception):
    pass


class QuestionExecutionRecord(Protocol):
    execution_id: UUID
    owner_scope: str
    prepare_idempotency_key: str
    capability_hash: str | None
    generation_id: UUID
    status: ExecutionStatus
    version: int
    private_payload: Mapping[str, object]
    frozen_citations: tuple[FrozenCitation, ...]
    verified_response: Mapping[str, object] | None
    expires_at: datetime


@dataclass(frozen=True)
class PhaseClaim:
    execution: QuestionExecutionRecord
    started: bool


class QuestionExecutionRepository(Protocol):
    async def prepare_or_get(self, **kwargs) -> QuestionExecutionRecord: ...

    async def get_owned(
        self, execution_id: UUID, owner_scope: str, *, capability_hash: str | None = None
    ) -> QuestionExecutionRecord: ...

    async def transition_phase(
        self, execution_id: UUID, owner_scope: str, **kwargs
    ) -> QuestionExecutionRecord: ...

    async def claim_phase(
        self, execution_id: UUID, owner_scope: str, **kwargs
    ) -> PhaseClaim: ...

    async def append_event(
        self, execution_id: UUID, owner_scope: str, event: AnswerEvent
    ) -> AnswerEvent: ...

    async def events_for(
        self, execution_id: UUID, owner_scope: str, *, phase: str
    ) -> tuple[AnswerEvent, ...]: ...

    async def append_issue(
        self, execution_id: UUID, owner_scope: str, issue: PipelineIssue
    ) -> PipelineIssue: ...

    async def complete(
        self, execution_id: UUID, owner_scope: str, **kwargs
    ) -> QuestionExecutionRecord: ...

    async def cancel(
        self, execution_id: UUID, owner_scope: str, *, capability_hash: str | None = None
    ) -> QuestionExecutionRecord: ...

    async def expire(self, now: datetime) -> tuple[UUID, ...]: ...
