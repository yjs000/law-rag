"""Short-transaction PostgreSQL clarification-case repository."""

from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import date, datetime
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.domain.clarification import ClarificationCase, FactStatus, RequiredFact
from app.ports.clarification_case import (
    ClarificationCaseConflict,
    ClarificationCaseNotFound,
    ClarificationCaseRecord,
    ClarificationCaseStatus,
)

_COLUMNS = """
case_id,owner_scope,capability_hash,original_question,as_of_date,project_stage,
conversation_id,facts,status,version,expires_at
"""


class PostgresClarificationCaseRepository:
    """Store private case state; provider work must happen outside this adapter."""

    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine

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
        identifier = case_id or uuid4()
        async with self._engine.begin() as connection:
            row = (
                (
                    await connection.execute(
                        text(
                            f"""INSERT INTO clarification_cases(
                        case_id,owner_scope,capability_hash,original_question,as_of_date,project_stage,
                        conversation_id,facts,status,expires_at)
                        VALUES(:case_id,:owner_scope,:capability_hash,:original_question,:as_of_date,
                        :project_stage,:conversation_id,CAST(:facts AS jsonb),
                        'waiting_for_user',:expires_at)
                        ON CONFLICT(case_id) DO UPDATE SET case_id=EXCLUDED.case_id
                        RETURNING {_COLUMNS}"""
                        ),
                        {
                            "case_id": identifier,
                            "owner_scope": owner_scope,
                            "capability_hash": capability_hash,
                            "original_question": original_question,
                            "as_of_date": as_of_date,
                            "project_stage": project_stage,
                            "conversation_id": conversation_id,
                            "facts": _facts_json(case),
                            "expires_at": expires_at,
                        },
                    )
                )
                .mappings()
                .one()
            )
        record = _record_from_row(row)
        if record.owner_scope != owner_scope or record.capability_hash != capability_hash:
            raise ClarificationCaseNotFound
        return record

    async def get_owned(
        self, case_id: UUID, owner_scope: str, *, capability_hash: str | None = None
    ) -> ClarificationCaseRecord:
        async with self._engine.connect() as connection:
            row = (
                (
                    await connection.execute(
                        text(
                            f"""SELECT {_COLUMNS} FROM clarification_cases
                        WHERE case_id=:case_id AND owner_scope=:owner_scope
                          AND status <> 'expired' AND expires_at > now()"""
                        ),
                        {"case_id": case_id, "owner_scope": owner_scope},
                    )
                )
                .mappings()
                .one_or_none()
            )
        return _require_owned(row, capability_hash)

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
        async with self._engine.begin() as connection:
            row = (
                (
                    await connection.execute(
                        text(
                            f"""UPDATE clarification_cases SET
                        facts=COALESCE(CAST(:facts AS jsonb), facts),
                        status=COALESCE(:status, status), version=version+1, updated_at=now()
                        WHERE case_id=:case_id AND owner_scope=:owner_scope
                          AND version=:expected_version AND status <> 'expired'
                          AND (capability_hash IS NULL OR capability_hash=:capability_hash)
                          AND expires_at > now()
                        RETURNING {_COLUMNS}"""
                        ),
                        {
                            "case_id": case_id,
                            "owner_scope": owner_scope,
                            "expected_version": expected_version,
                            "capability_hash": capability_hash,
                            "facts": _facts_json(case) if case is not None else None,
                            "status": status.value if status is not None else None,
                        },
                    )
                )
                .mappings()
                .one_or_none()
            )
        record = _require_owned(row, capability_hash)
        if record.version != expected_version + 1:
            raise ClarificationCaseConflict("clarification case version is stale")
        return record

    async def expire(self, now: datetime) -> tuple[UUID, ...]:
        async with self._engine.begin() as connection:
            rows = (
                (
                    await connection.execute(
                        text(
                            """UPDATE clarification_cases SET status='expired',version=version+1,
                        capability_hash=NULL,original_question='',facts='[]'::jsonb,updated_at=now()
                        WHERE expires_at<=:now AND status <> 'expired' RETURNING case_id"""
                        ),
                        {"now": now},
                    )
                )
                .scalars()
                .all()
            )
        return tuple(UUID(str(value)) for value in rows)


def _require_owned(
    row: Mapping[str, object] | None, capability_hash: str | None
) -> ClarificationCaseRecord:
    if row is None:
        raise ClarificationCaseConflict("clarification case version is stale")
    record = _record_from_row(row)
    if record.capability_hash is not None and record.capability_hash != capability_hash:
        raise ClarificationCaseNotFound
    return record


def _facts_json(case: ClarificationCase) -> str:
    return json.dumps(
        [
            {
                "id": fact.id,
                "label": fact.label,
                "why_needed": fact.why_needed,
                "blocking": fact.blocking,
                "group": fact.group,
                "priority": fact.priority,
                "status": fact.status.value,
                "value": fact.value,
                "source_turn_id": str(fact.source_turn_id) if fact.source_turn_id else None,
            }
            for fact in case.required_facts
        ]
    )


def _record_from_row(row: Mapping[str, object]) -> ClarificationCaseRecord:
    facts_value = row["facts"]
    facts_data = json.loads(facts_value) if isinstance(facts_value, str) else facts_value
    facts = (
        tuple(
            RequiredFact(
                id=str(item["id"]),
                label=str(item["label"]),
                why_needed=str(item["why_needed"]),
                blocking=bool(item["blocking"]),
                group=str(item["group"]),
                priority=int(item["priority"]),
                status=FactStatus(str(item.get("status", "unanswered"))),
                value=item.get("value"),
                source_turn_id=UUID(str(item["source_turn_id"]))
                if item.get("source_turn_id")
                else None,
            )
            for item in facts_data
            if isinstance(item, Mapping)
        )
        if isinstance(facts_data, list)
        else ()
    )
    return ClarificationCaseRecord(
        case_id=UUID(str(row["case_id"])),
        owner_scope=str(row["owner_scope"]),
        capability_hash=str(row["capability_hash"]) if row["capability_hash"] is not None else None,
        original_question=str(row["original_question"]),
        as_of_date=row["as_of_date"],
        project_stage=str(row["project_stage"]),
        conversation_id=UUID(str(row["conversation_id"])) if row["conversation_id"] else None,
        case=ClarificationCase(facts),
        status=ClarificationCaseStatus(str(row["status"])),
        version=int(row["version"]),
        expires_at=row["expires_at"],
    )
