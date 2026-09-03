from __future__ import annotations

import hmac
import json
from collections.abc import Mapping
from datetime import datetime
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.adapters.memory_question_execution import StoredQuestionExecution
from app.domain.answer_events import AnswerEvent
from app.domain.grounding import FrozenCitation
from app.domain.pipeline_issues import PipelineIssue
from app.domain.question_execution import (
    TERMINAL_EXECUTION_STATUSES,
    ExecutionSnapshot,
    ExecutionStatus,
    transition_execution,
)
from app.ports.question_execution import ExecutionConflict, ExecutionNotFound, PhaseClaim

_RECORD_COLUMNS = """
execution_id,owner_scope,prepare_idempotency_key,capability_hash,generation_id,status,version,
private_payload,frozen_citations,verified_response,expires_at,created_at,updated_at
"""


class PostgresQuestionExecutionRepository:
    """Short-transaction PostgreSQL implementation; provider calls remain outside this adapter."""

    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine

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
        async with self._engine.begin() as connection:
            row = (
                await connection.execute(
                    text(
                        f"""INSERT INTO question_executions(
                        owner_scope,prepare_idempotency_key,capability_hash,generation_id,status,
                        private_payload,frozen_citations,expires_at)
                        VALUES(
                        :owner_scope,:prepare_key,:capability_hash,:generation_id,'prepared',
                        CAST(:private_payload AS jsonb),
                        CAST(:frozen_citations AS jsonb),:expires_at)
                        ON CONFLICT(owner_scope,prepare_idempotency_key) DO UPDATE
                        SET owner_scope=EXCLUDED.owner_scope
                        RETURNING {_RECORD_COLUMNS}"""
                    ),
                    {
                        "owner_scope": owner_scope,
                        "prepare_key": prepare_idempotency_key,
                        "capability_hash": capability_hash,
                        "generation_id": generation_id,
                        "private_payload": json.dumps(dict(private_payload or {})),
                        "frozen_citations": json.dumps(
                            [
                                {"id": citation.id, "quote": citation.quote}
                                for citation in frozen_citations
                            ]
                        ),
                        "expires_at": expires_at,
                    },
                )
            ).mappings().one()
        return _record_from_row(row)

    async def find_by_prepare_key(
        self, owner_scope: str, prepare_idempotency_key: str
    ) -> StoredQuestionExecution | None:
        async with self._engine.connect() as connection:
            row = (
                await connection.execute(
                    text(
                        f"""SELECT {_RECORD_COLUMNS} FROM question_executions
                        WHERE owner_scope=:owner_scope AND prepare_idempotency_key=:prepare_key"""
                    ),
                    {"owner_scope": owner_scope, "prepare_key": prepare_idempotency_key},
                )
            ).mappings().one_or_none()
        return _record_from_row(row) if row is not None else None

    async def get_owned(
        self, execution_id: UUID, owner_scope: str, *, capability_hash: str | None = None
    ) -> StoredQuestionExecution:
        async with self._engine.connect() as connection:
            row = (
                await connection.execute(
                    text(
                        f"""SELECT {_RECORD_COLUMNS} FROM question_executions
                        WHERE execution_id=:execution_id AND owner_scope=:owner_scope"""
                    ),
                    {"execution_id": execution_id, "owner_scope": owner_scope},
                )
            ).mappings().one_or_none()
        return _require_owned(row, capability_hash)

    async def transition_phase(
        self,
        execution_id: UUID,
        owner_scope: str,
        *,
        expected_version: int,
        target: ExecutionStatus,
        capability_hash: str | None = None,
    ) -> StoredQuestionExecution:
        async with self._engine.begin() as connection:
            current = _require_owned(
                await _select_owned_for_update(connection, execution_id, owner_scope),
                capability_hash,
            )
            if current.status is target:
                return current
            if current.version != expected_version:
                raise ExecutionConflict("execution version is stale")
            updated = transition_execution(
                ExecutionSnapshot(status=current.status, version=current.version), target
            )
            row = (
                await connection.execute(
                    text(
                        f"""UPDATE question_executions SET
                        status=:status,version=:version,updated_at=now()
                        WHERE execution_id=:execution_id AND owner_scope=:owner_scope
                          AND version=:expected_version
                        RETURNING {_RECORD_COLUMNS}"""
                    ),
                    {
                        "status": updated.status.value,
                        "version": updated.version,
                        "execution_id": execution_id,
                        "owner_scope": owner_scope,
                        "expected_version": expected_version,
                    },
                )
            ).mappings().one_or_none()
            if row is None:
                raise ExecutionConflict("execution version is stale")
        return _record_from_row(row)

    async def claim_phase(
        self,
        execution_id: UUID,
        owner_scope: str,
        *,
        expected_version: int,
        target: ExecutionStatus,
        capability_hash: str | None = None,
    ) -> PhaseClaim:
        async with self._engine.begin() as connection:
            current = _require_owned(
                await _select_owned_for_update(connection, execution_id, owner_scope),
                capability_hash,
            )
            if current.status is target:
                return PhaseClaim(execution=current, started=False)
            if current.version != expected_version:
                raise ExecutionConflict("execution version is stale")
            updated = transition_execution(
                ExecutionSnapshot(status=current.status, version=current.version), target
            )
            row = (
                await connection.execute(
                    text(
                        f"""UPDATE question_executions SET
                        status=:status,version=:version,updated_at=now()
                        WHERE execution_id=:execution_id AND owner_scope=:owner_scope
                          AND version=:expected_version
                        RETURNING {_RECORD_COLUMNS}"""
                    ),
                    {
                        "status": updated.status.value,
                        "version": updated.version,
                        "execution_id": execution_id,
                        "owner_scope": owner_scope,
                        "expected_version": expected_version,
                    },
                )
            ).mappings().one_or_none()
            if row is None:
                raise ExecutionConflict("execution version is stale")
        return PhaseClaim(execution=_record_from_row(row), started=True)

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
        async with self._engine.begin() as connection:
            _require_owned(
                await _select_owned_for_update(connection, execution_id, owner_scope),
                capability_hash,
            )
            row = (
                await connection.execute(
                    text(
                        """INSERT INTO question_execution_events(
                        execution_id,phase,sequence,event_type,public_payload)
                        VALUES(:execution_id,:phase,:sequence,:event_type,CAST(:payload AS jsonb))
                        ON CONFLICT(execution_id,phase,sequence) DO NOTHING
                        RETURNING event_type,public_payload"""
                    ),
                    {
                        "execution_id": execution_id,
                        "phase": phase,
                        "sequence": sequence,
                        "event_type": event.event_type,
                        "payload": json.dumps(dict(event.payload)),
                    },
                )
            ).mappings().one_or_none()
            if row is not None:
                return event
            existing = (
                await connection.execute(
                    text(
                        """SELECT event_type,public_payload FROM question_execution_events
                        WHERE execution_id=:execution_id AND phase=:phase AND sequence=:sequence"""
                    ),
                    {"execution_id": execution_id, "phase": phase, "sequence": sequence},
                )
            ).mappings().one()
            if (
                existing["event_type"] != event.event_type
                or existing["public_payload"] != event.payload
            ):
                raise ExecutionConflict("event sequence is already occupied")
            return event

    async def finish_phase(
        self,
        execution_id: UUID,
        owner_scope: str,
        *,
        expected_version: int,
        target: ExecutionStatus,
        phase: str,
        events: tuple[AnswerEvent, ...],
        response: Mapping[str, object] | None = None,
        private_payload: Mapping[str, object] | None = None,
        capability_hash: str | None = None,
    ) -> StoredQuestionExecution:
        """Atomically commit a completed phase and its replayable event log."""
        async with self._engine.begin() as connection:
            current = _require_owned(
                await _select_owned_for_update(connection, execution_id, owner_scope),
                capability_hash,
            )
            if current.status is target:
                return current
            if current.version != expected_version:
                raise ExecutionConflict("execution version is stale")
            updated = transition_execution(
                ExecutionSnapshot(status=current.status, version=current.version), target
            )
            row = (
                await connection.execute(
                    text(
                        f"""UPDATE question_executions SET status=:status,version=:version,
                        verified_response=COALESCE(CAST(:response AS jsonb), verified_response),
                        private_payload=CASE
                          WHEN CAST(:private_payload AS jsonb) IS NULL THEN private_payload
                          ELSE private_payload || CAST(:private_payload AS jsonb) END,
                        updated_at=now()
                        WHERE execution_id=:execution_id AND owner_scope=:owner_scope
                          AND version=:expected_version
                        RETURNING {_RECORD_COLUMNS}"""
                    ),
                    {
                        "status": updated.status.value,
                        "version": updated.version,
                        "response": json.dumps(dict(response)) if response is not None else None,
                        "private_payload": (
                            json.dumps(dict(private_payload))
                            if private_payload is not None
                            else None
                        ),
                        "execution_id": execution_id,
                        "owner_scope": owner_scope,
                        "expected_version": expected_version,
                    },
                )
            ).mappings().one_or_none()
            if row is None:
                raise ExecutionConflict("execution version is stale")
            for sequence, event in enumerate(events):
                inserted = (
                    await connection.execute(
                        text(
                            """INSERT INTO question_execution_events(
                            execution_id,phase,sequence,event_type,public_payload)
                        VALUES(
                          :execution_id,:phase,:sequence,:event_type,CAST(:payload AS jsonb)
                        )
                            ON CONFLICT(execution_id,phase,sequence) DO NOTHING
                            RETURNING event_type,public_payload"""
                        ),
                        {
                            "execution_id": execution_id,
                            "phase": phase,
                            "sequence": sequence,
                            "event_type": event.event_type,
                            "payload": json.dumps(dict(event.payload)),
                        },
                    )
                ).mappings().one_or_none()
                if inserted is None:
                    existing = (
                        await connection.execute(
                            text(
                                """SELECT event_type,public_payload FROM question_execution_events
                                WHERE execution_id=:execution_id AND phase=:phase
                                  AND sequence=:sequence"""
                            ),
                            {"execution_id": execution_id, "phase": phase, "sequence": sequence},
                        )
                    ).mappings().one()
                    if existing["event_type"] != event.event_type or _json_mapping(
                        existing["public_payload"]
                    ) != event.payload:
                        raise ExecutionConflict("event sequence is already occupied")
        return _record_from_row(row)

    async def events_for(
        self,
        execution_id: UUID,
        owner_scope: str,
        *,
        phase: str,
        capability_hash: str | None = None,
    ) -> tuple[AnswerEvent, ...]:
        async with self._engine.begin() as connection:
            _require_owned(
                await _select_owned_for_update(connection, execution_id, owner_scope),
                capability_hash,
            )
            rows = (
                await connection.execute(
                    text(
                        """SELECT event_type,public_payload FROM question_execution_events
                        WHERE execution_id=:execution_id AND phase=:phase ORDER BY sequence"""
                    ),
                    {"execution_id": execution_id, "phase": phase},
                )
            ).mappings().all()
        return tuple(
            AnswerEvent(
                event_type=str(row["event_type"]),
                payload=_json_mapping(row["public_payload"]),
                terminal=str(row["event_type"]) in {"complete", "error", "cancelled"},
                is_complete=str(row["event_type"]) == "complete",
            )
            for row in rows
        )

    async def append_issue(
        self,
        execution_id: UUID,
        owner_scope: str,
        issue: PipelineIssue,
        *,
        capability_hash: str | None = None,
    ) -> PipelineIssue:
        async with self._engine.begin() as connection:
            _require_owned(
                await _select_owned_for_update(connection, execution_id, owner_scope),
                capability_hash,
            )
            await connection.execute(
                text(
                    """INSERT INTO question_execution_issues(
                    execution_id,phase,stage,public_reason_code,recoverable)
                    VALUES(:execution_id,:phase,:stage,:reason,:recoverable)"""
                ),
                {
                    "execution_id": execution_id,
                    "phase": issue.phase.value,
                    "stage": issue.stage,
                    "reason": issue.public_reason_code,
                    "recoverable": issue.recoverable,
                },
            )
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
        async with self._engine.begin() as connection:
            current = _require_owned(
                await _select_owned_for_update(connection, execution_id, owner_scope),
                capability_hash,
            )
            if current.status is ExecutionStatus.COMPLETED:
                return current
            if current.version != expected_version:
                raise ExecutionConflict("execution version is stale")
            updated = transition_execution(
                ExecutionSnapshot(status=current.status, version=current.version),
                ExecutionStatus.COMPLETED,
            )
            row = (
                await connection.execute(
                    text(
                        f"""UPDATE question_executions SET
                        status='completed',version=:version,
                        verified_response=CAST(:response AS jsonb),updated_at=now()
                        WHERE execution_id=:execution_id AND owner_scope=:owner_scope
                          AND version=:expected_version
                        RETURNING {_RECORD_COLUMNS}"""
                    ),
                    {
                        "version": updated.version,
                        "response": json.dumps(dict(response)),
                        "execution_id": execution_id,
                        "owner_scope": owner_scope,
                        "expected_version": expected_version,
                    },
                )
            ).mappings().one_or_none()
            if row is None:
                raise ExecutionConflict("execution version is stale")
        return _record_from_row(row)

    async def cancel(
        self, execution_id: UUID, owner_scope: str, *, capability_hash: str | None = None
    ) -> StoredQuestionExecution:
        async with self._engine.begin() as connection:
            current = _require_owned(
                await _select_owned_for_update(connection, execution_id, owner_scope),
                capability_hash,
            )
            if current.status in TERMINAL_EXECUTION_STATUSES:
                return current
            updated = transition_execution(
                ExecutionSnapshot(status=current.status, version=current.version),
                ExecutionStatus.CANCELLED,
            )
            row = (
                await connection.execute(
                    text(
                        f"""UPDATE question_executions SET
                        status='cancelled',version=:version,updated_at=now()
                        WHERE execution_id=:execution_id AND version=:expected_version
                        RETURNING {_RECORD_COLUMNS}"""
                    ),
                    {
                        "execution_id": execution_id,
                        "version": updated.version,
                        "expected_version": current.version,
                    },
                )
            ).mappings().one()
        return _record_from_row(row)

    async def expire(self, now: datetime) -> tuple[UUID, ...]:
        async with self._engine.begin() as connection:
            rows = (
                await connection.execute(
                    text(
                        """UPDATE question_executions SET
                        status=CASE
                          WHEN status IN ('completed','failed','cancelled','expired') THEN status
                          ELSE 'expired'
                        END,
                        version=CASE
                          WHEN status IN ('completed','failed','cancelled','expired') THEN version
                          ELSE version+1
                        END,
                        capability_hash=NULL,
                        private_payload='{}'::jsonb,
                        frozen_citations='[]'::jsonb,
                        verified_response=NULL,
                        updated_at=now()
                        WHERE expires_at<=:now AND (
                          status NOT IN ('completed','failed','cancelled','expired')
                          OR capability_hash IS NOT NULL
                          OR private_payload <> '{}'::jsonb
                          OR frozen_citations <> '[]'::jsonb
                          OR verified_response IS NOT NULL
                        )
                        RETURNING execution_id"""
                    ),
                    {"now": now},
                )
            ).scalars().all()
        return tuple(UUID(str(value)) for value in rows)


async def _select_owned_for_update(connection, execution_id: UUID, owner_scope: str):
    return (
        await connection.execute(
            text(
                f"""SELECT {_RECORD_COLUMNS} FROM question_executions
                WHERE execution_id=:execution_id AND owner_scope=:owner_scope FOR UPDATE"""
            ),
            {"execution_id": execution_id, "owner_scope": owner_scope},
        )
    ).mappings().one_or_none()


def _require_owned(
    row: Mapping[str, object] | None, capability_hash: str | None
) -> StoredQuestionExecution:
    if row is None:
        raise ExecutionNotFound
    record = _record_from_row(row)
    if record.capability_hash is not None and (
        capability_hash is None
        or not hmac.compare_digest(record.capability_hash, capability_hash)
    ):
        raise ExecutionNotFound
    return record


def _record_from_row(row: Mapping[str, object]) -> StoredQuestionExecution:
    def as_citations(value: object) -> tuple[FrozenCitation, ...]:
        if isinstance(value, str):
            value = json.loads(value)
        if not isinstance(value, list):
            return ()
        return tuple(
            FrozenCitation(id=item["id"], quote=item["quote"])
            for item in value
            if isinstance(item, Mapping)
            and isinstance(item.get("id"), str)
            and isinstance(item.get("quote"), str)
        )

    return StoredQuestionExecution(
        execution_id=UUID(str(row["execution_id"])),
        owner_scope=str(row["owner_scope"]),
        prepare_idempotency_key=str(row["prepare_idempotency_key"]),
        capability_hash=(
            str(row["capability_hash"]) if row["capability_hash"] is not None else None
        ),
        generation_id=UUID(str(row["generation_id"])),
        status=ExecutionStatus(str(row["status"])),
        version=int(row["version"]),
        private_payload=_json_mapping(row["private_payload"]),
        frozen_citations=as_citations(row["frozen_citations"]),
        verified_response=(
            _json_mapping(row["verified_response"])
            if row["verified_response"] is not None
            else None
        ),
        expires_at=row["expires_at"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _json_mapping(value: object) -> Mapping[str, object]:
    if isinstance(value, str):
        value = json.loads(value)
    return value if isinstance(value, Mapping) else {}
