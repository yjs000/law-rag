from app.domain.question_execution import (
    ExecutionSnapshot,
    ExecutionStatus,
    InvalidExecutionTransition,
    NextAction,
    next_action_for,
    transition_execution,
)


def test_prepared_execution_can_only_start_core() -> None:
    snapshot = ExecutionSnapshot(status=ExecutionStatus.PREPARED, version=3)

    assert next_action_for(snapshot) is NextAction.GENERATE_CORE
    assert transition_execution(snapshot, ExecutionStatus.CORE_RUNNING).version == 4


def test_core_result_drives_the_only_allowed_finalize_action() -> None:
    assert (
        next_action_for(ExecutionSnapshot(status=ExecutionStatus.CORE_ANSWERED))
        is NextAction.GENERATE_DETAIL
    )
    assert (
        next_action_for(ExecutionSnapshot(status=ExecutionStatus.CORE_REPAIR_REQUIRED))
        is NextAction.REPAIR_CORE
    )


def test_terminal_execution_has_no_follow_up_action() -> None:
    assert next_action_for(ExecutionSnapshot(status=ExecutionStatus.COMPLETED)) is None


def test_unknown_or_illegal_state_transition_fails_closed() -> None:
    snapshot = ExecutionSnapshot(status=ExecutionStatus.PREPARED)

    try:
        transition_execution(snapshot, ExecutionStatus.FINALIZE_RUNNING)
    except InvalidExecutionTransition:
        pass
    else:
        raise AssertionError("illegal transition must fail closed")
