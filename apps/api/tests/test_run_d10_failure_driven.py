from __future__ import annotations

from pathlib import Path

import pytest

from scripts.d10_answer_judge import AnswerJudgeResult
from scripts.d10_failure_runner import D10RunInput
from scripts.run_d10_failure_driven import (
    apply_answer_judgment,
    evaluate_live_answer_case,
    parse_arguments,
    run_from_arguments,
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


@pytest.mark.asyncio
async def test_live_answer_case_applies_judge_failure_without_answer_text() -> None:
    async def execute(_: D10RunInput) -> object:
        from types import SimpleNamespace

        return SimpleNamespace(action="fully_answerable", sections=(), limitations=(), citations=())

    result = await evaluate_live_answer_case(
        D10RunInput(
            "lay-energy-0201",
            "private question",
            __import__("datetime").date(2026, 8, 5),
            "snapshot-1",
            "answer",
        ),
        answer_executor=execute,
    )

    assert result["status"] == "failure"
    assert result["error_code"] == "answer_empty"
    assert "private question" not in str(result)


@pytest.mark.asyncio
async def test_live_answer_case_records_routing_provider_failure_as_blocked() -> None:
    async def execute(_: D10RunInput) -> object:
        from types import SimpleNamespace

        return SimpleNamespace(
            action="unanswerable",
            route="routing_unavailable",
            sections=(),
            limitations=(),
            citations=(),
        )

    result = await evaluate_live_answer_case(
        D10RunInput(
            "lay-energy-0201",
            "private question",
            __import__("datetime").date(2026, 8, 5),
            "snapshot-1",
            "ask_clarifying_question",
        ),
        answer_executor=execute,
    )

    assert result["status"] == "blocked"
    assert result["error_code"] == "routing_unavailable"
    assert result["actual_action"] is None


@pytest.mark.asyncio
async def test_cli_runs_one_selected_case_and_writes_answer_ledger(tmp_path: Path) -> None:
    args = parse_arguments(
        [
            "--sealed-dir",
            str(tmp_path / "sealed"),
            "--case-id",
            "lay-energy-0201",
            "--output-dir",
            str(tmp_path),
        ]
    )

    def load_case(_: Path, case_id: str) -> D10RunInput:
        return D10RunInput(
            case_id,
            "private question",
            __import__("datetime").date(2026, 8, 5),
            "snapshot",
            "answer",
        )

    async def execute(_: D10RunInput) -> object:
        from types import SimpleNamespace

        return SimpleNamespace(
            action="fully_answerable", sections=(object(),), limitations=(), citations=()
        )

    record = await run_from_arguments(args, case_loader=load_case, answer_executor=execute)

    assert record.case_id == "lay-energy-0201"
    assert record.evaluation_stage == "answer"
