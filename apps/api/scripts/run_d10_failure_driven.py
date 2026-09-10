"""Advance the native D-10 calibration one safe attempt at a time."""

from __future__ import annotations

import argparse
import asyncio
import json
from collections.abc import Callable
from pathlib import Path
from typing import Protocol

from scripts.d10_answer_judge import AnswerJudgeResult, judge_execution
from scripts.d10_failure_ledger import (
    CITATION_REASON,
    D10_CASE_ORDER,
    AttemptRecord,
    append_attempt,
)
from scripts.d10_failure_runner import (
    AnswerExecutor,
    D10RunInput,
    live_application_answer_executor,
    load_d10_run_input,
    run_single_answer_case,
)


class SingleCaseExecutor(Protocol):
    async def __call__(self, case_id: str) -> dict[str, object]: ...


def parse_arguments(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse the intentionally one-case-at-a-time native D-10 command."""
    parser = argparse.ArgumentParser(description="Run one native D-10 answer evaluation case")
    parser.add_argument("--sealed-dir", type=Path, required=True)
    parser.add_argument("--case-id", action="append")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--output-dir", type=Path, default=Path(".data/experiments/d-gold-10"))
    arguments = parser.parse_args(argv)
    if arguments.case_id is not None and len(arguments.case_id) != 1:
        parser.error("--case-id may be supplied at most once")
    arguments.case_id = arguments.case_id[0] if arguments.case_id else None
    if arguments.case_id is not None and arguments.resume:
        parser.error("--case-id and --resume are mutually exclusive")
    return arguments


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


async def evaluate_live_answer_case(
    case: D10RunInput, *, answer_executor: AnswerExecutor
) -> dict[str, object]:
    """Run and judge one private answer execution before it reaches the ledger."""
    execution = await run_single_answer_case(case, answer_executor=answer_executor)
    result = execution.safe_result()
    if result["status"] == "blocked":
        return result
    return apply_answer_judgment(result, judge_execution(case, execution))


async def run_from_arguments(
    arguments: argparse.Namespace,
    *,
    case_loader: Callable[[Path, str], D10RunInput],
    answer_executor: AnswerExecutor,
) -> AttemptRecord | None:
    """Execute exactly the requested/resumed case and append only its safe result."""
    ledger_path = arguments.output_dir / "attempts.jsonl"
    case_ids = (arguments.case_id,) if arguments.case_id else D10_CASE_ORDER

    async def _execute(case_id: str) -> dict[str, object]:
        case = case_loader(arguments.sealed_dir, case_id)
        return await evaluate_live_answer_case(case, answer_executor=answer_executor)

    return await run_next_case(ledger_path, _execute, case_ids=case_ids)


def _production_answer_executor() -> AnswerExecutor:
    """Compose the existing v1 application boundary only when the CLI is executed."""
    import app.main as main_module
    from app.application.request_budget import RequestBudget

    return live_application_answer_executor(
        answer_question=main_module._answer_question,
        repository=main_module.repository,
        budget_factory=lambda: RequestBudget.start(
            main_module.settings.question_request_timeout_seconds,
            main_module.settings.response_reserve_seconds,
        ),
    )


async def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint: emits only the final safe attempt record as JSON."""
    arguments = parse_arguments(argv)
    record = await run_from_arguments(
        arguments,
        case_loader=load_d10_run_input,
        answer_executor=_production_answer_executor(),
    )
    print(json.dumps(record.to_dict() if record is not None else {"status": "no_case"}))
    return 0


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


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
