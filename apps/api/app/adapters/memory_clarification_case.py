"""In-memory clarification case repository for deterministic tests."""

from __future__ import annotations

import asyncio
import hmac
from collections.abc import Callable
from datetime import UTC, date, datetime
from uuid import UUID, uuid4

from app.domain.clarification import ClarificationCase
from app.ports.clarification_case import (
    ClarificationCaseConflict,
    ClarificationCaseNotFound,
    ClarificationCaseRecord,
    ClarificationCaseStatus,
)

StoredClarificationCase = ClarificationCaseRecord


class MemoryClarificationCaseRepository:
    def __init__(self, *, now: Callable[[], datetime] | None = None) -> None:
        self._now = now or (lambda: datetime.now(UTC))
        self._records: dict[UUID, ClarificationCaseRecord] = {}
        self._lock = asyncio.Lock()

    async def create_or_get(
        self,
        *,
        owner_scope: str,
        capability_hash: str | None,
        original_question: str,
        as_of_date: date,
        project_stage: str,
        conversation_id: UUID | None,
        case: ClarificationCase,
        expires_at: datetime,
        case_id: UUID | None = None,
    ) -> ClarificationCaseRecord:
        async with self._lock:
            if case_id is not None and case_id in self._records:
                return self._require_owned(self._records[case_id], owner_scope, capability_hash)
            record = ClarificationCaseRecord(
                case_id=case_id or uuid4(),
                owner_scope=owner_scope,
                capability_hash=capability_hash,
                original_question=original_question,
                as_of_date=as_of_date,
                project_stage=project_stage,
                conversation_id=conversation_id,
                case=case,
                status=ClarificationCaseStatus.WAITING_FOR_USER,
                version=0,
                expires_at=expires_at,
            )
            self._records[record.case_id] = record
            return record

    async def create(
        self,
        *,
        owner_scope: str,
        case: ClarificationCase,
        expires_at: datetime,
        capability_hash: str | None = None,
    ) -> ClarificationCaseRecord:
        return await self.create_or_get(
            owner_scope=owner_scope,
            capability_hash=capability_hash,
            original_question="",
            as_of_date=self._now().date(),
            project_stage="planning",
            conversation_id=None,
            case=case,
            expires_at=expires_at,
        )

    async def get_owned(
        self, case_id: UUID, owner_scope: str, *, capability_hash: str | None = None
    ) -> ClarificationCaseRecord:
        async with self._lock:
            record = self._records.get(case_id)
            if record is None:
                raise ClarificationCaseNotFound
            return self._require_owned(record, owner_scope, capability_hash)

    async def merge(
        self,
        case_id: UUID,
        owner_scope: str,
        *,
        expected_version: int,
        case: ClarificationCase,
        capability_hash: str | None = None,
    ) -> ClarificationCaseRecord:
        return await self._update(
            case_id,
            owner_scope,
            expected_version=expected_version,
            case=case,
            status=None,
            capability_hash=capability_hash,
        )

    async def mark_waiting(
        self, case_id: UUID, owner_scope: str, **kwargs: object
    ) -> ClarificationCaseRecord:
        return await self._update(
            case_id, owner_scope, status=ClarificationCaseStatus.WAITING_FOR_USER, **kwargs
        )

    async def complete(
        self, case_id: UUID, owner_scope: str, **kwargs: object
    ) -> ClarificationCaseRecord:
        return await self._update(
            case_id, owner_scope, status=ClarificationCaseStatus.COMPLETED, **kwargs
        )

    async def cancel(
        self, case_id: UUID, owner_scope: str, **kwargs: object
    ) -> ClarificationCaseRecord:
        return await self._update(
            case_id, owner_scope, status=ClarificationCaseStatus.CANCELLED, **kwargs
        )

    async def _update(
        self,
        case_id: UUID,
        owner_scope: str,
        *,
        expected_version: int,
        case: ClarificationCase | None = None,
        status: ClarificationCaseStatus | None = None,
        capability_hash: str | None = None,
    ) -> ClarificationCaseRecord:
        async with self._lock:
            current = self._records.get(case_id)
            if current is None:
                raise ClarificationCaseNotFound
            current = self._require_owned(current, owner_scope, capability_hash)
            if current.version != expected_version:
                raise ClarificationCaseConflict("clarification case version is stale")
            updated = ClarificationCaseRecord(
                case_id=current.case_id,
                owner_scope=current.owner_scope,
                capability_hash=current.capability_hash,
                original_question=current.original_question,
                as_of_date=current.as_of_date,
                project_stage=current.project_stage,
                conversation_id=current.conversation_id,
                case=case or current.case,
                status=status or current.status,
                version=current.version + 1,
                expires_at=current.expires_at,
            )
            self._records[case_id] = updated
            return updated

    async def expire(self, now: datetime) -> tuple[UUID, ...]:
        async with self._lock:
            expired: list[UUID] = []
            for case_id, record in tuple(self._records.items()):
                if (
                    record.expires_at <= now
                    and record.status is not ClarificationCaseStatus.EXPIRED
                ):
                    self._records[case_id] = ClarificationCaseRecord(
                        case_id=record.case_id,
                        owner_scope=record.owner_scope,
                        capability_hash=None,
                        original_question="",
                        as_of_date=record.as_of_date,
                        project_stage=record.project_stage,
                        conversation_id=record.conversation_id,
                        case=ClarificationCase(()),
                        status=ClarificationCaseStatus.EXPIRED,
                        version=record.version + 1,
                        expires_at=record.expires_at,
                    )
                    expired.append(case_id)
            return tuple(expired)

    def _require_owned(
        self,
        record: ClarificationCaseRecord,
        owner_scope: str,
        capability_hash: str | None,
    ) -> ClarificationCaseRecord:
        if (
            record.owner_scope != owner_scope
            or record.status is ClarificationCaseStatus.EXPIRED
            or record.expires_at <= self._now()
            or (
                record.capability_hash is not None
                and (
                    capability_hash is None
                    or not hmac.compare_digest(record.capability_hash, capability_hash)
                )
            )
        ):
            raise ClarificationCaseNotFound
        return record
