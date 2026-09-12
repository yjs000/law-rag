"""Advance the native D-10 calibration one safe attempt at a time."""

from __future__ import annotations

import argparse
import asyncio
import json
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Protocol
from uuid import uuid4

import httpx

from app.domain.schemas import QuestionResponse
from scripts.d10_answer_judge import AnswerJudgeResult, judge_execution
from scripts.d10_failure_ledger import (
    CITATION_REASON,
    D10_CASE_ORDER,
    AttemptRecord,
    append_attempt,
    validate_final_summary,
    write_final_summary,
)
from scripts.d10_failure_runner import (
    AnswerExecutor,
    D10AnswerObservation,
    D10RunInput,
    load_d10_run_input,
    run_single_answer_case,
)


class SingleCaseExecutor(Protocol):
    async def __call__(self, case_id: str) -> dict[str, object]: ...


E006_RESOLVED_DEFECTS: dict[str, tuple[str, ...]] = {
    "v2_evaluation_phase_transport": ("apps/api/tests/test_run_d10_failure_driven.py",),
    "v2_prepare_budget_and_router_timeout": (
        "apps/api/tests/test_v2_question_executions.py",
    ),
    "sandbox_safe_python_verification": ("scripts/tests/test_run_python.py",),
    "clarification_outcome_preservation": (
        "apps/api/tests/test_clarification_answering.py",
        "apps/api/tests/test_v2_question_executions.py",
    ),
    "explicit_case_retry": ("apps/api/tests/test_run_d10_failure_driven.py",),
    "conditional_answer_classification": (
        "apps/api/tests/test_d10_answer_judge.py",
        "apps/api/tests/test_layperson_prompt_v2.py",
    ),
    "clarification_routing_stability": ("apps/api/tests/test_routing_pipeline.py",),
    "generation_evidence_leaf_preservation": (
        "apps/api/tests/test_generation_evidence_budget.py",
    ),
    "record_comparison_route_search_and_grounding": (
        "apps/api/tests/test_routing_pipeline.py",
        "apps/api/tests/test_search_queries.py",
        "apps/api/tests/test_v2_grounding_events.py",
    ),
    "specific_site_clarification_routing": ("apps/api/tests/test_routing_pipeline.py",),
    "semantic_guard_for_grounded_partial_promotion": (
        "apps/api/tests/test_v2_question_executions.py",
    ),
    "citationless_summary_is_accepted_as_grounded": (
        "apps/api/tests/test_v2_grounding_events.py",
    ),
    "independent_retrieval_citation_and_action_leak_judge": (
        "apps/api/tests/test_d10_answer_judge.py",
        "apps/api/tests/test_d10_failure_runner.py",
    ),
    "sealed_corpus_generation_binding": (
        "apps/api/tests/test_run_d10_failure_driven.py",
        "apps/api/tests/test_v2_question_executions.py",
    ),
}
REPOSITORY_ROOT = Path(__file__).resolve().parents[3]

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

    return await run_next_case(
        ledger_path,
        _execute,
        case_ids=case_ids,
        force_selected_case=arguments.case_id is not None,
    )


def reconcile_final_summary(
    ledger_path: Path,
    summary_path: Path,
    resolved_defects: dict[str, tuple[str, ...]],
    *,
    repository_root: Path,
) -> bool:
    latest = {
        str(item["case_id"]): str(item["status"])
        for item in _existing_records(ledger_path)
    }
    if all(latest.get(case_id) == "pass" for case_id in D10_CASE_ORDER):
        write_final_summary(
            ledger_path,
            summary_path,
            resolved_defects,
            repository_root=repository_root,
        )
        validate_final_summary(
            ledger_path,
            summary_path,
            resolved_defects,
            repository_root=repository_root,
        )
        return True
    summary_path.unlink(missing_ok=True)
    return False

def validate_v2_evaluation_budget(settings: object) -> None:
    """Validate the fixed D-10 V2 evaluation budget contract."""
    phase = getattr(settings, "v2_phase_timeout_seconds", None)
    provider = getattr(settings, "v2_provider_budget_seconds", None)
    if phase != 57 or provider != 55:
        raise RuntimeError("d10_v2_budget_invalid")


def v2_application_answer_executor(
    *,
    app: object,
    prepare_binding: Callable[[D10RunInput], Awaitable[str]],
) -> AnswerExecutor:
    """Compose the V2 HTTP execution boundary."""

    async def _execute(case: D10RunInput) -> object:
        generation_id = await prepare_binding(case)
        idempotency_key = f"d10-{case.case_id}-{uuid4()}"
        transport = httpx.ASGITransport(app=app)  # type: ignore[arg-type]
        execution_id: str | None = None
        capability: str | None = None
        async with httpx.AsyncClient(
            transport=transport, base_url="http://d10-evaluation.local", timeout=None
        ) as client:
            try:
                prepared = await client.post(
                    "/v2/question-executions",
                    headers={
                        "Idempotency-Key": idempotency_key,
                        "X-Evaluation-Corpus-Snapshot": case.corpus_snapshot_id,
                        "X-Evaluation-Generation-Id": generation_id,
                    },
                    json={
                        "question": case.question,
                        "as_of_date": case.as_of_date.isoformat(),
                        "answer_mode": "terra",
                    },
                )
                prepared.raise_for_status()
                prepared_data = prepared.json()
                execution_id = str(prepared_data["execution_id"])
                capability = str(prepared_data["execution_capability"])
                retrieved_evidence_ids = prepared_data.get(
                    "evaluation_retrieved_evidence_ids"
                )
                if not isinstance(retrieved_evidence_ids, list) or any(
                    not isinstance(identifier, str)
                    for identifier in retrieved_evidence_ids
                ):
                    raise RuntimeError("v2_answer_contract_invalid")
                headers = {"X-Execution-Capability": capability}
                core = await client.post(
                    f"/v2/question-executions/{execution_id}/core", headers=headers
                )
                core.raise_for_status()
                _require_successful_sse(core.text, terminal_event="phase_complete")
                finalized = await client.post(
                    f"/v2/question-executions/{execution_id}/finalize", headers=headers
                )
                finalized.raise_for_status()
                complete = _require_successful_sse(finalized.text, terminal_event="complete")
                response = complete.get("response")
                if not isinstance(response, dict):
                    raise RuntimeError("v2_answer_contract_invalid")
                return D10AnswerObservation(
                    response=QuestionResponse.model_validate(response),
                    retrieved_evidence_ids=tuple(retrieved_evidence_ids),
                )
            except Exception:
                if execution_id is not None and capability is not None:
                    try:
                        await client.delete(
                            f"/v2/question-executions/{execution_id}",
                            headers={"X-Execution-Capability": capability},
                        )
                    except Exception:
                        pass
                raise

    return _execute


def _require_successful_sse(body: str, *, terminal_event: str) -> dict[str, object]:
    """Return one required terminal SSE payload or raise a safe contract error."""
    for block in body.replace("\r\n", "\n").split("\n\n"):
        event_type: str | None = None
        data: str | None = None
        for line in block.splitlines():
            if line.startswith("event: "):
                event_type = line.removeprefix("event: ")
            elif line.startswith("data: "):
                data = line.removeprefix("data: ")
        if event_type == "error":
            raise RuntimeError("v2_phase_unavailable")
        if event_type == terminal_event and data is not None:
            payload = json.loads(data)
            if isinstance(payload, dict):
                return payload
    raise RuntimeError("v2_answer_contract_invalid")


def _production_answer_executor() -> AnswerExecutor:
    """Compose the production V2 HTTP boundary only when the CLI is executed."""
    import app.main as main_module

    validate_v2_evaluation_budget(main_module.settings)

    async def prepare_binding(case: D10RunInput) -> str:
        from law_rag_llamaindex.generation.models import source_fingerprint
        from law_rag_llamaindex.ingestion.source_reader import fetch_provisions

        resources = main_module._llamaindex_resources()
        if resources is None or resources[0] is None or resources[2] is None:
            raise RuntimeError("d10_v2_binding_unavailable")
        active = await resources[0].active()
        records = await fetch_provisions(main_module.repository.engine)
        state = await resources[2].corpus_temporal_state(main_module._current_korea_date())
        if (
            not state.ready
            or state.corpus_snapshot_id != case.corpus_snapshot_id
            or source_fingerprint(records) != active.generation.source_fingerprint
        ):
            raise RuntimeError("d10_corpus_binding_invalid")
        return str(active.generation.id)

    return v2_application_answer_executor(
        app=main_module.app,
        prepare_binding=prepare_binding,
    )

def safe_answer_executor_factory(factory: Callable[[], AnswerExecutor]) -> AnswerExecutor:
    """Keep production preflight failures inside the safe per-case ledger boundary."""
    try:
        return factory()
    except Exception:

        async def _unavailable(_: D10RunInput) -> object:
            raise RuntimeError("d10_v2_preflight_unavailable") from None

        return _unavailable


async def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint: emits only the final safe attempt record as JSON."""
    arguments = parse_arguments(argv)
    record = await run_from_arguments(
        arguments,
        case_loader=load_d10_run_input,
        answer_executor=safe_answer_executor_factory(_production_answer_executor),
    )
    ledger_path = arguments.output_dir / "attempts.jsonl"
    reconcile_final_summary(
        ledger_path,
        arguments.output_dir / "summary.json",
        E006_RESOLVED_DEFECTS,
        repository_root=REPOSITORY_ROOT,
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
    force_selected_case: bool = False,
) -> AttemptRecord | None:
    existing_records = _existing_records(ledger_path)
    case_id = (
        case_ids[0]
        if force_selected_case and len(case_ids) == 1
        else next_case_id(ledger_path, case_ids)
    )
    if case_id is None:
        return None
    if force_selected_case and existing_records:
        last_case_id = str(existing_records[-1]["case_id"])
        last_status = str(existing_records[-1]["status"])
        last_index = D10_CASE_ORDER.index(last_case_id)
        selected_index = D10_CASE_ORDER.index(case_id)
        is_same_case = selected_index == last_index
        is_next_case = last_status == "pass" and selected_index == last_index + 1
        if not (is_same_case or is_next_case):
            raise ValueError("selected_case_order_invalid")
    result = await executor(case_id)
    common = {
        "attempt_number": len(existing_records) + 1,
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
