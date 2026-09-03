"""Persistence boundary for private clarification conversations."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from enum import StrEnum
from typing import Protocol
from uuid import UUID

from app.domain.clarification import ClarificationCase


class ClarificationCaseNotFound(Exception):
    """Do not distinguish absent, foreign, expired, or bad-capability cases."""


class ClarificationCaseConflict(Exception):
    """The caller attempted to write a stale clarification snapshot."""


class ClarificationCaseStatus(StrEnum):
    WAITING_FOR_USER = "waiting_for_user"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


@dataclass(frozen=True)
class ClarificationCaseRecord:
    case_id: UUID
    owner_scope: str
    capability_hash: str | None
    original_question: str
    as_of_date: date
    project_stage: str
    conversation_id: UUID | None
    case: ClarificationCase
    status: ClarificationCaseStatus
    version: int
    expires_at: datetime


class ClarificationCaseRepository(Protocol):
    async def create_or_get(self, **kwargs) -> ClarificationCaseRecord: ...

    async def get_owned(
        self, case_id: UUID, owner_scope: str, *, capability_hash: str | None = None
    ) -> ClarificationCaseRecord: ...

    async def merge(self, case_id: UUID, owner_scope: str, **kwargs) -> ClarificationCaseRecord: ...

    async def mark_waiting(
        self, case_id: UUID, owner_scope: str, **kwargs
    ) -> ClarificationCaseRecord: ...

    async def complete(
        self, case_id: UUID, owner_scope: str, **kwargs
    ) -> ClarificationCaseRecord: ...

    async def cancel(
        self, case_id: UUID, owner_scope: str, **kwargs
    ) -> ClarificationCaseRecord: ...

    async def expire(self, now: datetime) -> tuple[UUID, ...]: ...
