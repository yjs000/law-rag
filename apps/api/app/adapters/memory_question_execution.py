from __future__ import annotations

import asyncio
import hmac
from collections.abc import Callable, Mapping  # noqa: I001
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from uuid import UUID, uuid4

from app.domain.answer_events import AnswerEvent
from app.domain.grounding import FrozenCitation
from app.domain.pipeline_issues import PipelineIssue
from app.domain.question_execution import (
    TERMINAL_EXECUTION_STATUSES,
    ExecutionSnapshot,
    ExecutionStatus,
    transition_execution,
)
from app.ports.question_execution import ExecutionConflict, ExecutionNotFound


@dataclass(frozen=True)
class StoredQuestionExecution:
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
    created_at: datetime
    updated_at: datetime


class MemoryQuestionExecutionRepository:
    """In-memory reference implementation of the authoritative execution contract."""

    def __init__(self, *, now: Callable[[], datetime] | None = None) -> None:
        self._now = now or (lambda: datetime.now(UTC))
        self._records: dict[UUID, StoredQuestionExecution] = {}
        self._by_prepare_key: dict[tuple[str, str], UUID] = {}
        self._events: dict[tuple[UUID, str, int], AnswerEvent] = {}
        self._issues: dict[UUID, list[PipelineIssue]] = {}
        self._lock = asyncio.Lock()

    async def prepare_or_get(
        self,
        *,
        owner_scope: str,
        prepare_idempotency_key: str,
        generation_id: UUID,
        expires_at: datetime,
        capability_hash: str | None = None,
        private_payload: Mapping[str, object] | None = None,
        frozen_citations: tuple[FrozenCitation, ...] = (),
    ) -> StoredQuestionExecution:
        async with self._lock:
            key = (owner_scope, prepare_idempotency_key)
            existing_id = self._by_prepare_key.get(key)
            if existing_id is not None:
                return self._records[existing_id]
            now = self._now()
            record = StoredQuestionExecution(
                execution_id=uuid4(),
                owner_scope=owner_scope,
                prepare_idempotency_key=prepare_idempotency_key,
                capability_hash=capability_hash,
                generation_id=generation_id,
                status=ExecutionStatus.PREPARED,
                version=0,
                private_payload=dict(private_payload or {}),
                frozen_citations=tuple(frozen_citations),
                verified_response=None,
                expires_at=expires_at,
                created_at=now,
                updated_at=now,
            )
            self._records[record.execution_id] = record
            self._by_prepare_key[key] = record.execution_id
            return record

    async def get_owned(
        self, execution_id: UUID, owner_scope: str, *, capability_hash: str | None = None
    ) -> StoredQuestionExecution:
        async with self._lock:
            return self._get_owned(execution_id, owner_scope, capability_hash=capability_hash)

    async def transition_phase(
        self,
        execution_id: UUID,
        owner_scope: str,
        *,
        expected_version: int,
        target: ExecutionStatus,
        capability_hash: str | None = None,
    ) -> StoredQuestionExecution:
        async with self._lock:
            current = self._get_owned(execution_id, owner_scope, capability_hash=capability_hash)
            if current.status is target:
                return current
            self._require_expected_version(current, expected_version)
            updated = transition_execution(
                ExecutionSnapshot(status=current.status, version=current.version), target
            )
            return self._replace(current, status=updated.status, version=updated.version)

    async def append_event(
        self,
        execution_id: UUID,
        owner_scope: str,
        *,
        phase: str,
        sequence: int,
        event: AnswerEvent,
        capability_hash: str | None = None,
    ) -> AnswerEvent:
        async with self._lock:
            self._get_owned(execution_id, owner_scope, capability_hash=capability_hash)
            key = (execution_id, phase, sequence)
            existing = self._events.get(key)
            if existing is not None:
                if existing != event:
                    raise ExecutionConflict("event sequence is already occupied")
                return existing
            self._events[key] = event
            return event

    async def append_issue(
        self,
        execution_id: UUID,
        owner_scope: str,
        issue: PipelineIssue,
        *,
        capability_hash: str | None = None,
    ) -> PipelineIssue:
        async with self._lock:
            self._get_owned(execution_id, owner_scope, capability_hash=capability_hash)
            self._issues.setdefault(execution_id, []).append(issue)
            return issue

    async def complete(
        self,
        execution_id: UUID,
        owner_scope: str,
        *,
        expected_version: int,
        response: Mapping[str, object],
        capability_hash: str | None = None,
    ) -> StoredQuestionExecution:
        async with self._lock:
            current = self._get_owned(execution_id, owner_scope, capability_hash=capability_hash)
            if current.status is ExecutionStatus.COMPLETED:
                return current
            self._require_expected_version(current, expected_version)
            updated = transition_execution(
                ExecutionSnapshot(status=current.status, version=current.version),
                ExecutionStatus.COMPLETED,
            )
            return self._replace(
                current,
                status=updated.status,
                version=updated.version,
                verified_response=dict(response),
            )

    async def cancel(self, execution_id: UUID, owner_scope: str) -> StoredQuestionExecution:
        async with self._lock:
            current = self._get_owned(execution_id, owner_scope)
            if current.status in TERMINAL_EXECUTION_STATUSES:
                return current
            updated = transition_execution(
                ExecutionSnapshot(status=current.status, version=current.version),
                ExecutionStatus.CANCELLED,
            )
            return self._replace(current, status=updated.status, version=updated.version)

    async def expire(self, now: datetime) -> tuple[UUID, ...]:
        async with self._lock:
            expired: list[UUID] = []
            for record in tuple(self._records.values()):
                if record.expires_at > now or record.status in TERMINAL_EXECUTION_STATUSES:
                    continue
                updated = transition_execution(
                    ExecutionSnapshot(status=record.status, version=record.version),
                    ExecutionStatus.EXPIRED,
                )
                self._replace(record, status=updated.status, version=updated.version)
                expired.append(record.execution_id)
            return tuple(expired)

    def _get_owned(
        self, execution_id: UUID, owner_scope: str, *, capability_hash: str | None = None
    ) -> StoredQuestionExecution:
        record = self._records.get(execution_id)
        if record is None or record.owner_scope != owner_scope:
            raise ExecutionNotFound
        if record.capability_hash is not None and (
            capability_hash is None
            or not hmac.compare_digest(record.capability_hash, capability_hash)
        ):
            raise ExecutionNotFound
        return record

    @staticmethod
    def _require_expected_version(record: StoredQuestionExecution, expected_version: int) -> None:
        if record.version != expected_version:
            raise ExecutionConflict("execution version is stale")

    def _replace(
        self, record: StoredQuestionExecution, **changes: object
    ) -> StoredQuestionExecution:
        updated = replace(record, updated_at=self._now(), **changes)
        self._records[record.execution_id] = updated
        return updated
