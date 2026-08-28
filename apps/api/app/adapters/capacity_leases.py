from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.domain.pipeline_issues import ExecutionPhase
from app.ports.question_execution import SystemBusy


class Lease(Protocol):
    slot: int

    async def release(self) -> None: ...


@dataclass(frozen=True)
class _StoredLease:
    lease_id: UUID
    execution_id: UUID
    phase: ExecutionPhase
    slot: int
    expires_at: datetime


class _MemoryLease:
    def __init__(self, limiter: MemoryConcurrencyLimiter, stored: _StoredLease) -> None:
        self._limiter = limiter
        self._stored = stored
        self.slot = stored.slot

    async def release(self) -> None:
        await self._limiter._release(self._stored.lease_id)


class MemoryConcurrencyLimiter:
    def __init__(
        self, *, provider: str, slots: int, now: Callable[[], datetime] | None = None
    ) -> None:
        if slots <= 0:
            raise ValueError("at least one provider slot is required")
        self.provider = provider
        self._slots = slots
        self._now = now or (lambda: datetime.now(UTC))
        self._leases: dict[UUID, _StoredLease] = {}
        self._lock = asyncio.Lock()

    async def acquire(
        self, execution_id: UUID, phase: ExecutionPhase, deadline: datetime
    ) -> Lease:
        async with self._lock:
            now = self._now()
            self._reclaim_expired(now)
            occupied = {lease.slot for lease in self._leases.values()}
            slot = next(
                (candidate for candidate in range(self._slots) if candidate not in occupied),
                None,
            )
            if slot is None or deadline <= now:
                raise SystemBusy
            stored = _StoredLease(
                lease_id=uuid4(),
                execution_id=execution_id,
                phase=phase,
                slot=slot,
                expires_at=deadline,
            )
            self._leases[stored.lease_id] = stored
            return _MemoryLease(self, stored)

    async def active_count(self) -> int:
        async with self._lock:
            self._reclaim_expired(self._now())
            return len(self._leases)

    async def _release(self, lease_id: UUID) -> None:
        async with self._lock:
            self._leases.pop(lease_id, None)

    def _reclaim_expired(self, now: datetime) -> None:
        for lease_id, lease in tuple(self._leases.items()):
            if lease.expires_at <= now:
                del self._leases[lease_id]


class CapacityLeaseStore(Protocol):
    async def acquire_slot(
        self,
        *,
        provider: str,
        slots: int,
        execution_id: UUID,
        phase: ExecutionPhase,
        deadline: datetime,
    ) -> Lease | None: ...


class PostgresConcurrencyLimiter:
    """Fail closed when the global lease store cannot make an admission decision."""

    def __init__(self, *, provider: str, slots: int, lease_store: CapacityLeaseStore) -> None:
        self.provider = provider
        self._slots = slots
        self._lease_store = lease_store

    async def acquire(
        self, execution_id: UUID, phase: ExecutionPhase, deadline: datetime
    ) -> Lease:
        try:
            lease = await self._lease_store.acquire_slot(
                provider=self.provider,
                slots=self._slots,
                execution_id=execution_id,
                phase=phase,
                deadline=deadline,
            )
        except Exception as exc:
            raise SystemBusy from exc
        if lease is None:
            raise SystemBusy
        return lease


class _PostgresLease:
    def __init__(self, engine: AsyncEngine, lease_id: UUID, slot: int) -> None:
        self._engine = engine
        self._lease_id = lease_id
        self.slot = slot

    async def release(self) -> None:
        async with self._engine.begin() as connection:
            await connection.execute(
                text("DELETE FROM provider_capacity_leases WHERE lease_id=:lease_id"),
                {"lease_id": self._lease_id},
            )


class PostgresCapacityLeaseStore:
    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine

    async def acquire_slot(
        self,
        *,
        provider: str,
        slots: int,
        execution_id: UUID,
        phase: ExecutionPhase,
        deadline: datetime,
    ) -> Lease | None:
        async with self._engine.begin() as connection:
            await connection.execute(
                text("DELETE FROM provider_capacity_leases WHERE expires_at<=now()")
            )
            row = (
                await connection.execute(
                    text(
                        """INSERT INTO provider_capacity_leases(
                        provider,slot,execution_id,phase,expires_at)
                        SELECT :provider,slot,:execution_id,:phase,:expires_at
                        FROM generate_series(0,:slots-1) AS slot
                        WHERE NOT EXISTS (
                          SELECT 1 FROM provider_capacity_leases existing
                          WHERE existing.provider=:provider AND existing.slot=slot
                        )
                        ORDER BY slot LIMIT 1
                        ON CONFLICT(provider,slot) DO NOTHING
                        RETURNING lease_id,slot"""
                    ),
                    {
                        "provider": provider,
                        "slots": slots,
                        "execution_id": execution_id,
                        "phase": phase.value,
                        "expires_at": deadline,
                    },
                )
            ).mappings().one_or_none()
        if row is None:
            return None
        return _PostgresLease(self._engine, UUID(str(row["lease_id"])), int(row["slot"]))
