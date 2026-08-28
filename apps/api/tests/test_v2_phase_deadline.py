from datetime import UTC, datetime, timedelta

from app.application.phase_deadline import PhaseDeadline


def test_repair_and_detail_share_one_fifty_five_second_budget() -> None:
    started_at = datetime(2026, 8, 28, tzinfo=UTC)
    deadline = PhaseDeadline.started(started_at, provider_budget_seconds=55)

    assert deadline.remaining_seconds(started_at + timedelta(seconds=20)) == 35
    assert deadline.remaining_seconds(started_at + timedelta(seconds=54, milliseconds=500)) == 0.5
    assert deadline.remaining_seconds(started_at + timedelta(seconds=56)) == 0
