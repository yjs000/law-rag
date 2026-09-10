"""Advance the native D-10 calibration one safe attempt at a time."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from scripts.d10_answer_judge import AnswerJudgeResult
from scripts.d10_failure_ledger import (
    CITATION_REASON,
    D10_CASE_ORDER,
    AttemptRecord,
    append_attempt,
)


class SingleCaseExecutor(Protocol):
    async def __call__(self, case_id: str) -> dict[str, object]: ...


def apply_answer_judgment(
    safe_result: dict[str, object], judgment: AnswerJudgeResult
) -> dict[str, object]:
    """Make a deterministic judge failure terminal without exposing private answer text."""
    result = dict(safe_result)
    result["judge_codes"] = list(judgment.codes)
    if not judgment.passed:
        result["status"] = "failure"
        result["error_code"] = judgment.codes[0]
    return result


def _existing_records(path: Path) -> list[dict[str, object]]:
    if not path.exists():
        return []
    import json

    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def next_case_id(ledger_path: Path, case_ids: tuple[str, ...] = D10_CASE_ORDER) -> str | None:
    records = _existing_records(ledger_path)
    latest = {str(record["case_id"]): str(record["status"]) for record in records}
    for case_id in case_ids:
        status = latest.get(case_id)
        if status is None:
            return case_id
        if status != "pass":
            return None
    return None


async def run_next_case(
    ledger_path: Path,
    executor: SingleCaseExecutor,
    *,
    case_ids: tuple[str, ...] = D10_CASE_ORDER,
) -> AttemptRecord | None:
    case_id = next_case_id(ledger_path, case_ids)
    if case_id is None:
        return None
    result = await executor(case_id)
    common = {
        "attempt_number": len(_existing_records(ledger_path)) + 1,
        "case_id": case_id,
        "status": str(result["status"]),  # validated before persistence
        "error_code": result.get("error_code")
        if isinstance(result.get("error_code"), str)
        else None,
        "retrieved_evidence_count": int(result["retrieved_evidence_count"]),
    }
    if result.get("evaluation_stage") == "answer":
        record = AttemptRecord(
            **common,
            citation_count=result.get("citation_count"),
            citation_reason=str(result.get("citation_reason")),
            evaluation_stage="answer",
            actual_action=(
                result.get("actual_action")
                if isinstance(result.get("actual_action"), str)
                else None
            ),
            judge_codes=tuple(result.get("judge_codes", ())),
        )
    else:
        record = AttemptRecord(
            **common,
            citation_count=None,
            citation_reason=CITATION_REASON,
        )
    return append_attempt(ledger_path, record)
