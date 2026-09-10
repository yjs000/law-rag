from __future__ import annotations

from pathlib import Path

import pytest

from scripts.d10_answer_judge import AnswerJudgeResult
from scripts.run_d10_failure_driven import (
    apply_answer_judgment,
    parse_arguments,
    run_next_case,
)


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


def test_answer_judgment_turns_safe_answer_result_into_failure_record() -> None:
    result = apply_answer_judgment(
        {
            "case_id": "lay-energy-0201",
            "status": "pass",
            "error_code": None,
            "retrieved_evidence_count": 1,
            "citation_count": 1,
            "citation_reason": "validated_by_answer_runner",
            "evaluation_stage": "answer",
            "actual_action": "answer",
            "judge_codes": [],
        },
        AnswerJudgeResult(False, ("citation_not_in_retrieval_evidence",)),
    )

    assert result["status"] == "failure"
    assert result["error_code"] == "citation_not_in_retrieval_evidence"
    assert result["judge_codes"] == ["citation_not_in_retrieval_evidence"]


@pytest.mark.asyncio
async def test_answer_stage_is_preserved_in_ledger(tmp_path) -> None:
    async def execute(_: str) -> dict[str, object]:
        return {
            "status": "pass",
            "error_code": None,
            "retrieved_evidence_count": 1,
            "citation_count": 1,
            "citation_reason": "validated_by_answer_runner",
            "evaluation_stage": "answer",
            "actual_action": "answer",
            "judge_codes": [],
        }

    record = await run_next_case(
        tmp_path / "attempts.jsonl", execute, case_ids=("lay-energy-0201",)
    )

    assert record.evaluation_stage == "answer"
    assert record.citation_count == 1
    assert record.actual_action == "answer"


def test_cli_requires_sealed_directory_and_allows_one_case_override(tmp_path: Path) -> None:
    args = parse_arguments(
        [
            "--sealed-dir",
            str(tmp_path / "sealed"),
            "--case-id",
            "lay-energy-0201",
            "--output-dir",
            str(tmp_path / "output"),
        ]
    )

    assert args.sealed_dir == tmp_path / "sealed"
    assert args.case_id == "lay-energy-0201"
    assert args.output_dir == tmp_path / "output"


def test_cli_rejects_multiple_case_ids(tmp_path: Path) -> None:
    with pytest.raises(SystemExit):
        parse_arguments(
            [
                "--sealed-dir",
                str(tmp_path / "sealed"),
                "--case-id",
                "lay-energy-0201",
                "--case-id",
                "lay-energy-0251",
            ]
        )
