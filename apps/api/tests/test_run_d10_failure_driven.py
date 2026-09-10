from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID

import pytest
from fastapi import FastAPI, Header
from fastapi.responses import StreamingResponse

from scripts.d10_answer_judge import AnswerJudgeResult
from scripts.d10_failure_runner import D10RunInput
from scripts.run_d10_failure_driven import (
    apply_answer_judgment,
    evaluate_live_answer_case,
    parse_arguments,
    run_from_arguments,
    run_next_case,
    safe_answer_executor_factory,
    v2_application_answer_executor,
    validate_v2_evaluation_budget,
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


@pytest.mark.asyncio
async def test_v2_executor_runs_prepare_core_finalize_over_http_without_v1_budget() -> None:
    app = FastAPI()
    calls: list[str] = []
    execution_id = UUID("00000000-0000-0000-0000-000000000123")

    @app.post("/v2/question-executions")
    async def prepare(
        payload: dict[str, object], idempotency_key: str = Header()
    ) -> dict[str, str]:
        calls.append("prepare")
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

    response = await v2_application_answer_executor(app=app)(
        D10RunInput(
            "lay-energy-0201",
            "private question",
            __import__("datetime").date(2026, 8, 5),
            "snapshot",
            "answer",
        )
    )

    assert calls == ["prepare", "core", "finalize"]
    assert response.action == "fully_answerable"
    assert str(response.citations[0].provision_id) == "00000000-0000-0000-0000-000000000001"


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
    async def prepare() -> dict[str, str]:
        calls.append("prepare")
        return {
            "execution_id": str(execution_id),
            "execution_capability": "secret-capability",
            "next_action": "generate_core",
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

    record = await run_from_arguments(
        args,
        case_loader=load_case,
        answer_executor=v2_application_answer_executor(app=app),
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
