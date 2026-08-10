import asyncio

import pytest

from app.application.request_budget import RequestBudget, StageTimeoutError


def test_stage_timeout_uses_smaller_of_cap_and_remaining_work_budget() -> None:
    now = {"value": 100.0}
    budget = RequestBudget.start(52, 3, clock=lambda: now["value"])
    assert budget.stage_timeout_seconds(40) == 40
    now["value"] = 120.0
    assert budget.stage_timeout_seconds(40) == 29


def test_stage_timeout_rejects_work_when_only_response_reserve_remains() -> None:
    now = {"value": 100.0}
    budget = RequestBudget.start(52, 3, clock=lambda: now["value"])
    now["value"] = 149.0
    with pytest.raises(StageTimeoutError) as caught:
        budget.stage_timeout_seconds(40, stage="generation")
    assert caught.value.stage == "generation"


@pytest.mark.asyncio
async def test_run_converts_asyncio_timeout_to_stage_timeout() -> None:
    budget = RequestBudget.start(0.02, 0.005)
    with pytest.raises(StageTimeoutError) as caught:
        await budget.run("retrieval", lambda: asyncio.sleep(1), cap_seconds=0.01)
    assert caught.value.stage == "retrieval"
