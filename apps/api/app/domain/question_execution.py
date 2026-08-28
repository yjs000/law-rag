from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class ExecutionStatus(StrEnum):
    PREPARED = "prepared"
    CORE_RUNNING = "core_running"
    CORE_ANSWERED = "core_answered"
    CORE_REPAIR_REQUIRED = "core_repair_required"
    FINALIZE_RUNNING = "finalize_running"
    PHASE_RECOVERY_REQUIRED = "phase_recovery_required"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


class NextAction(StrEnum):
    GENERATE_CORE = "generate_core"
    GENERATE_DETAIL = "generate_detail"
    REPAIR_CORE = "repair_core"
    COMPLETE = "complete"


TERMINAL_EXECUTION_STATUSES = frozenset(
    {
        ExecutionStatus.COMPLETED,
        ExecutionStatus.FAILED,
        ExecutionStatus.CANCELLED,
        ExecutionStatus.EXPIRED,
    }
)


@dataclass(frozen=True)
class ExecutionSnapshot:
    status: ExecutionStatus
    version: int = 0


class InvalidExecutionTransition(ValueError):
    pass


_ALLOWED_TRANSITIONS: dict[ExecutionStatus, frozenset[ExecutionStatus]] = {
    ExecutionStatus.PREPARED: frozenset(
        {
            ExecutionStatus.CORE_RUNNING,
            ExecutionStatus.CANCELLED,
            ExecutionStatus.EXPIRED,
            ExecutionStatus.FAILED,
        }
    ),
    ExecutionStatus.CORE_RUNNING: frozenset(
        {
            ExecutionStatus.CORE_ANSWERED,
            ExecutionStatus.CORE_REPAIR_REQUIRED,
            ExecutionStatus.PHASE_RECOVERY_REQUIRED,
            ExecutionStatus.CANCELLED,
            ExecutionStatus.FAILED,
            ExecutionStatus.EXPIRED,
        }
    ),
    ExecutionStatus.CORE_ANSWERED: frozenset(
        {
            ExecutionStatus.FINALIZE_RUNNING,
            ExecutionStatus.COMPLETED,
            ExecutionStatus.CANCELLED,
            ExecutionStatus.EXPIRED,
        }
    ),
    ExecutionStatus.CORE_REPAIR_REQUIRED: frozenset(
        {ExecutionStatus.FINALIZE_RUNNING, ExecutionStatus.CANCELLED, ExecutionStatus.EXPIRED}
    ),
    ExecutionStatus.FINALIZE_RUNNING: frozenset(
        {
            ExecutionStatus.COMPLETED,
            ExecutionStatus.PHASE_RECOVERY_REQUIRED,
            ExecutionStatus.CANCELLED,
            ExecutionStatus.FAILED,
            ExecutionStatus.EXPIRED,
        }
    ),
    ExecutionStatus.PHASE_RECOVERY_REQUIRED: frozenset({ExecutionStatus.EXPIRED}),
    ExecutionStatus.COMPLETED: frozenset(),
    ExecutionStatus.FAILED: frozenset(),
    ExecutionStatus.CANCELLED: frozenset(),
    ExecutionStatus.EXPIRED: frozenset(),
}


def next_action_for(snapshot: ExecutionSnapshot) -> NextAction | None:
    match snapshot.status:
        case ExecutionStatus.PREPARED:
            return NextAction.GENERATE_CORE
        case ExecutionStatus.CORE_ANSWERED:
            return NextAction.GENERATE_DETAIL
        case ExecutionStatus.CORE_REPAIR_REQUIRED:
            return NextAction.REPAIR_CORE
        case _:
            return None


def transition_execution(
    snapshot: ExecutionSnapshot, target: ExecutionStatus
) -> ExecutionSnapshot:
    if target not in _ALLOWED_TRANSITIONS[snapshot.status]:
        raise InvalidExecutionTransition(f"cannot transition {snapshot.status} to {target}")
    return ExecutionSnapshot(status=target, version=snapshot.version + 1)
