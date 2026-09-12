from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID

import pytest
from fastapi import FastAPI, Header
from fastapi.responses import StreamingResponse

from scripts.d10_answer_judge import AnswerJudgeResult
from scripts.d10_failure_ledger import D10_CASE_ORDER
from scripts.d10_failure_runner import D10AnswerObservation, D10RunInput
from scripts.run_d10_failure_driven import (
    E006_RESOLVED_DEFECTS,
    apply_answer_judgment,
    evaluate_live_answer_case,
    parse_arguments,
    reconcile_final_summary,
    run_from_arguments,
    run_next_case,
    safe_answer_executor_factory,
    v2_application_answer_executor,
    validate_v2_evaluation_budget,
)


def test_final_summary_defects_include_frozen_citationless_grounding_regression() -> None:
    assert E006_RESOLVED_DEFECTS["citationless_summary_is_accepted_as_grounded"] == (
        "apps/api/tests/test_v2_grounding_events.py",
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


@pytest.mark.asyncio
async def test_forced_case_rejects_regression_before_executor_runs(tmp_path) -> None:
    ledger_path = tmp_path / "attempts.jsonl"
    ledger_path.write_text(
        "".join(
            json.dumps({"case_id": case_id, "status": "pass"}) + "\n"
            for case_id in D10_CASE_ORDER[:2]
        ),
        encoding="utf-8",
    )
    called = False

    async def execute(_: str) -> dict[str, object]:
        nonlocal called
        called = True
        return {"status": "pass", "error_code": None, "retrieved_evidence_count": 1}

    with pytest.raises(ValueError, match="selected_case_order_invalid"):
        await run_next_case(
            ledger_path,
            execute,
            case_ids=(D10_CASE_ORDER[0],),
            force_selected_case=True,
        )

    assert called is False


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


@pytest.mark.asyncio
async def test_cli_explicit_case_retries_latest_nonpass_in_same_ledger(tmp_path: Path) -> None:
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

    async def unavailable(_: D10RunInput) -> object:
        raise RuntimeError("provider unavailable")

    async def available(_: D10RunInput) -> object:
        return SimpleNamespace(
            action="fully_answerable", sections=(object(),), limitations=(), citations=()
        )

    first = await run_from_arguments(args, case_loader=load_case, answer_executor=unavailable)
    second = await run_from_arguments(args, case_loader=load_case, answer_executor=available)

    assert first is not None and first.status == "blocked"
    assert second is not None and second.attempt_number == 2
    assert second.case_id == "lay-energy-0201"


@pytest.mark.asyncio
async def test_v2_executor_runs_prepare_core_finalize_over_http_without_v1_budget() -> None:
    app = FastAPI()
    calls: list[str] = []
    execution_id = UUID("00000000-0000-0000-0000-000000000123")

    @app.post("/v2/question-executions")
    async def prepare(
        payload: dict[str, object],
        idempotency_key: str = Header(),
        x_evaluation_corpus_snapshot: str = Header(),
        x_evaluation_generation_id: str = Header(),
    ) -> dict[str, object]:
        calls.append("prepare")
        assert x_evaluation_corpus_snapshot == "snapshot"
        assert x_evaluation_generation_id == str(execution_id)
        assert payload == {
            "question": "private question",
            "as_of_date": "2026-08-05",
            "answer_mode": "terra",
        }
        assert idempotency_key.startswith("d10-lay-energy-0201-")
        return {
            "execution_id": str(execution_id),
            "execution_capability": "opaque-capability",
            "next_action": "generate_core",
            "evaluation_retrieved_evidence_ids": [
                "00000000-0000-0000-0000-000000000001"
            ],
        }

    @app.post("/v2/question-executions/{requested_execution_id}/core")
    async def core(
        requested_execution_id: UUID, x_execution_capability: str = Header()
    ) -> StreamingResponse:
        calls.append("core")
        assert requested_execution_id == execution_id
        assert x_execution_capability == "opaque-capability"
        return StreamingResponse(
            iter([b'event: phase_complete\ndata: {"next_action": "generate_detail"}\n\n']),
            media_type="text/event-stream",
        )

    @app.post("/v2/question-executions/{requested_execution_id}/finalize")
    async def finalize(
        requested_execution_id: UUID, x_execution_capability: str = Header()
    ) -> StreamingResponse:
        calls.append("finalize")
        assert requested_execution_id == execution_id
        assert x_execution_capability == "opaque-capability"
        response = {
            "request_id": "request-1",
            "mode": "ai",
            "summary": "summary [C1]",
            "scope": "scope",
            "sections": [{"claim": "claim", "explanation": "explanation", "citation_ids": ["C1"]}],
            "checklist": [],
            "citations": [
                {
                    "id": "C1",
                    "provision_id": "00000000-0000-0000-0000-000000000001",
                    "document_title": "title",
                    "version_label": "version",
                    "path": "article 1",
                    "quote": "quote",
                    "source_url": "https://example.test/source",
                    "source_kind": "law",
                }
            ],
            "limitations": [],
            "requested_answer_mode": "terra",
            "action": "fully_answerable",
            "route": "legal_search",
        }
        return StreamingResponse(
            iter([f"event: complete\ndata: {json.dumps({'response': response})}\n\n".encode()]),
            media_type="text/event-stream",
        )

    async def prepare_binding(_case: D10RunInput) -> str:
        return str(execution_id)

    observation = await v2_application_answer_executor(
        app=app,
        prepare_binding=prepare_binding,
    )(
        D10RunInput(
            "lay-energy-0201",
            "private question",
            __import__("datetime").date(2026, 8, 5),
            "snapshot",
            "answer",
        )
    )

    assert calls == ["prepare", "core", "finalize"]
    assert isinstance(observation, D10AnswerObservation)
    assert observation.response.action == "fully_answerable"
    assert observation.retrieved_evidence_ids == (
        "00000000-0000-0000-0000-000000000001",
    )


def test_v2_evaluation_budget_rejects_non_contract_values_without_reading_v1_budget() -> None:
    class Settings:
        v2_phase_timeout_seconds = 57
        v2_provider_budget_seconds = 55

        @property
        def question_request_timeout_seconds(self) -> float:
            raise AssertionError("v1 budget must not be read")

    validate_v2_evaluation_budget(Settings())

    with pytest.raises(RuntimeError, match="d10_v2_budget_invalid"):
        validate_v2_evaluation_budget(
            SimpleNamespace(v2_phase_timeout_seconds=56, v2_provider_budget_seconds=55)
        )


@pytest.mark.asyncio
async def test_factory_failure_is_normalized_into_safe_blocked_ledger(tmp_path: Path) -> None:
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
            "private question must not reach the ledger",
            __import__("datetime").date(2026, 8, 5),
            "snapshot",
            "answer",
        )

    def fail_factory() -> object:
        raise RuntimeError("secret provider setup detail")

    record = await run_from_arguments(
        args,
        case_loader=load_case,
        answer_executor=safe_answer_executor_factory(fail_factory),
    )

    assert record is not None
    assert record.status == "blocked"
    assert record.error_code == "answer_unavailable"
    ledger = (tmp_path / "attempts.jsonl").read_text(encoding="utf-8")
    assert "private question" not in ledger
    assert "secret provider setup detail" not in ledger


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "core_body",
    [
        'event: error\ndata: {"detail": "secret provider payload"}\n\n',
        'event: progress\ndata: {"detail": "secret provider payload"}\n\n',
    ],
)
async def test_v2_core_failure_cancels_and_writes_only_safe_ledger(
    tmp_path: Path, core_body: str
) -> None:
    app = FastAPI()
    calls: list[str] = []
    execution_id = UUID("00000000-0000-0000-0000-000000000456")

    @app.post("/v2/question-executions")
    async def prepare() -> dict[str, object]:
        calls.append("prepare")
        return {
            "execution_id": str(execution_id),
            "execution_capability": "secret-capability",
            "next_action": "generate_core",
            "evaluation_retrieved_evidence_ids": [
                "00000000-0000-0000-0000-000000000001"
            ],
        }

    @app.post("/v2/question-executions/{requested_execution_id}/core")
    async def core(requested_execution_id: UUID) -> StreamingResponse:
        calls.append("core")
        assert requested_execution_id == execution_id
        return StreamingResponse(iter([core_body.encode()]), media_type="text/event-stream")

    @app.post("/v2/question-executions/{requested_execution_id}/finalize")
    async def finalize(requested_execution_id: UUID) -> None:
        calls.append("finalize")
        assert requested_execution_id == execution_id

    @app.delete("/v2/question-executions/{requested_execution_id}", status_code=500)
    async def cancel(requested_execution_id: UUID) -> dict[str, str]:
        calls.append("cancel")
        assert requested_execution_id == execution_id
        return {"detail": "secret cleanup failure"}

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

    async def prepare_binding(_case: D10RunInput) -> str:
        return str(execution_id)

    record = await run_from_arguments(
        args,
        case_loader=load_case,
        answer_executor=v2_application_answer_executor(
            app=app,
            prepare_binding=prepare_binding,
        ),
    )

    assert record is not None
    assert record.status == "blocked"
    assert record.error_code == "answer_unavailable"
    assert calls == ["prepare", "core", "cancel"]
    ledger = (tmp_path / "attempts.jsonl").read_text(encoding="utf-8")
    assert "private question" not in ledger
    assert "secret provider payload" not in ledger
    assert "secret-capability" not in ledger
    assert "secret cleanup failure" not in ledger

def test_reconcile_final_summary_invalidates_failure_and_recovers_missing_pass(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ledger_path = tmp_path / "attempts.jsonl"
    summary_path = tmp_path / "summary.json"
    pass_rows = [
        {"case_id": case_id, "status": "pass"}
        for case_id in D10_CASE_ORDER
    ]
    ledger_path.write_text(
        "".join(json.dumps(row) + "\n" for row in pass_rows), encoding="utf-8"
    )
    calls: list[str] = []

    def write_summary(*_args, **_kwargs):
        calls.append("write")
        summary_path.write_text("{}", encoding="utf-8")

    def validate_summary(*_args, **_kwargs):
        calls.append("validate")

    import scripts.run_d10_failure_driven as runner_module

    monkeypatch.setattr(runner_module, "write_final_summary", write_summary)
    monkeypatch.setattr(runner_module, "validate_final_summary", validate_summary)

    assert reconcile_final_summary(
        ledger_path, summary_path, {}, repository_root=tmp_path
    ) is True
    assert calls == ["write", "validate"]
    ledger_path.write_text(
        ledger_path.read_text(encoding="utf-8")
        + json.dumps({"case_id": pass_rows[0]["case_id"], "status": "failure"})
        + "\n",
        encoding="utf-8",
    )

    assert reconcile_final_summary(
        ledger_path, summary_path, {}, repository_root=tmp_path
    ) is False
    assert not summary_path.exists()
