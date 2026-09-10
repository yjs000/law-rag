from __future__ import annotations

import pytest

from scripts.run_d10_failure_driven import run_next_case


@pytest.mark.asyncio
async def test_pass_advances_only_one_case_per_invocation(tmp_path) -> None:
    called: list[str] = []

    async def execute(case_id: str) -> dict[str, object]:
        called.append(case_id)
        return {"status": "pass", "error_code": None, "retrieved_evidence_count": 1}

    first = await run_next_case(
        tmp_path / "attempts.jsonl", execute, case_ids=("lay-energy-0201", "lay-energy-0251")
    )
    second = await run_next_case(
        tmp_path / "attempts.jsonl", execute, case_ids=("lay-energy-0201", "lay-energy-0251")
    )

    assert [first.case_id, second.case_id] == ["lay-energy-0201", "lay-energy-0251"]
    assert called == ["lay-energy-0201", "lay-energy-0251"]


@pytest.mark.asyncio
async def test_failure_stops_before_next_case(tmp_path) -> None:
    async def execute(_: str) -> dict[str, object]:
        return {
            "status": "failure",
            "error_code": "no_retrieved_evidence",
            "retrieved_evidence_count": 0,
        }

    assert await run_next_case(
        tmp_path / "attempts.jsonl", execute, case_ids=("lay-energy-0201", "lay-energy-0251")
    )
    assert (
        await run_next_case(
            tmp_path / "attempts.jsonl", execute, case_ids=("lay-energy-0201", "lay-energy-0251")
        )
        is None
    )
