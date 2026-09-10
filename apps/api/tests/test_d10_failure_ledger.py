from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.d10_failure_ledger import (
    AttemptRecord,
    LedgerValidationError,
    append_attempt,
    summarize_attempts,
)


def _record(
    attempt_number: int,
    *,
    case_id: str = "lay-energy-0201",
    status: str = "pass",
    error_code: str | None = None,
    retrieved_evidence_count: int = 1,
) -> AttemptRecord:
    return AttemptRecord(
        attempt_number=attempt_number,
        case_id=case_id,
        status=status,
        error_code=error_code,
        retrieved_evidence_count=retrieved_evidence_count,
        citation_count=None,
        citation_reason="not_generated_by_retrieval_runner",
    )


def test_append_attempt_writes_contiguous_safe_jsonl_and_summary(tmp_path: Path) -> None:
    ledger_path = tmp_path / "attempts.jsonl"

    append_attempt(ledger_path, _record(1))
    append_attempt(
        ledger_path,
        _record(
            2,
            case_id="lay-energy-0251",
            status="blocked",
            error_code="nvidia_api_key_required",
        ),
    )

    rows = [json.loads(line) for line in ledger_path.read_text(encoding="utf-8").splitlines()]
    assert [row["attempt_number"] for row in rows] == [1, 2]
    assert all(set(row) == set(AttemptRecord.allowed_field_names()) for row in rows)
    assert summarize_attempts(ledger_path) == {
        "total_attempts": 2,
        "attempts_by_case": {"lay-energy-0201": 1, "lay-energy-0251": 1},
        "status_counts": {"pass": 1, "failure": 0, "blocked": 1},
        "failure_code_histogram": {},
    }


@pytest.mark.parametrize(
    "record",
    (
        _record(0),
        _record("1"),
        _record(1, case_id="not-a-d10-case"),
        _record(1, status="unknown"),
    ),
)
def test_append_attempt_rejects_invalid_attempt_contract(
    tmp_path: Path,
    record: AttemptRecord,
) -> None:
    with pytest.raises(LedgerValidationError):
        append_attempt(tmp_path / "attempts.jsonl", record)


def test_zero_retrieved_evidence_rejects_pass_status(tmp_path: Path) -> None:
    with pytest.raises(LedgerValidationError):
        append_attempt(
            tmp_path / "attempts.jsonl",
            _record(1, status="pass", retrieved_evidence_count=0),
        )


def test_zero_retrieved_evidence_allows_blocked_external_gate(tmp_path: Path) -> None:
    record = append_attempt(
        tmp_path / "attempts.jsonl",
        _record(
            1,
            status="blocked",
            error_code="nvidia_api_key_required",
            retrieved_evidence_count=0,
        ),
    )

    assert record.status == "blocked"


def test_zero_retrieved_evidence_rejects_blocked_without_safe_code(tmp_path: Path) -> None:
    with pytest.raises(LedgerValidationError):
        append_attempt(
            tmp_path / "attempts.jsonl",
            _record(1, status="blocked", retrieved_evidence_count=0),
        )


@pytest.mark.parametrize(
    "field",
    ("question", "source_text", "prompt", "exception_message", "api_key"),
)
def test_append_attempt_rejects_forbidden_input_fields(tmp_path: Path, field: str) -> None:
    payload = _record(1).to_dict()
    payload[field] = "sensitive value"

    with pytest.raises(LedgerValidationError):
        append_attempt(tmp_path / "attempts.jsonl", payload)


@pytest.mark.parametrize(
    "field",
    ("question", "source_text", "prompt", "exception_message", "api_key"),
)
def test_summary_rejects_forbidden_jsonl_fields(tmp_path: Path, field: str) -> None:
    ledger_path = tmp_path / "attempts.jsonl"
    payload = _record(1).to_dict()
    payload[field] = "sensitive value"
    ledger_path.write_text(json.dumps(payload) + "\n", encoding="utf-8")

    with pytest.raises(LedgerValidationError):
        summarize_attempts(ledger_path)


def test_attempt_record_requires_null_retrieval_only_citation(tmp_path: Path) -> None:
    with pytest.raises(LedgerValidationError):
        append_attempt(
            tmp_path / "attempts.jsonl",
            AttemptRecord(
                attempt_number=1,
                case_id="lay-energy-0201",
                status="pass",
                error_code=None,
                retrieved_evidence_count=1,
                citation_count=0,
                citation_reason="not_generated_by_retrieval_runner",
            ),
        )


def test_answer_attempt_records_action_judgment_without_answer_text(tmp_path: Path) -> None:
    record = append_attempt(
        tmp_path / "attempts.jsonl",
        AttemptRecord(
            attempt_number=1,
            case_id="lay-energy-0201",
            status="pass",
            error_code=None,
            retrieved_evidence_count=2,
            citation_count=2,
            citation_reason="validated_by_answer_runner",
            evaluation_stage="answer",
            actual_action="answer",
            judge_codes=(),
        ),
    )

    assert record.to_dict() == {
        "attempt_number": 1,
        "case_id": "lay-energy-0201",
        "status": "pass",
        "error_code": None,
        "retrieved_evidence_count": 2,
        "citation_count": 2,
        "citation_reason": "validated_by_answer_runner",
        "evaluation_stage": "answer",
        "actual_action": "answer",
        "judge_codes": [],
    }


@pytest.mark.parametrize("field", ("answer", "answer_text", "citation_text", "prompt"))
def test_answer_attempt_rejects_sensitive_or_answer_text_fields(tmp_path: Path, field: str) -> None:
    payload = {
        "attempt_number": 1,
        "case_id": "lay-energy-0201",
        "status": "failure",
        "error_code": "answer_empty",
        "retrieved_evidence_count": 1,
        "citation_count": 0,
        "citation_reason": "validated_by_answer_runner",
        "evaluation_stage": "answer",
        "actual_action": "answer",
        "judge_codes": ["answer_empty"],
        field: "must never be persisted",
    }

    with pytest.raises(LedgerValidationError):
        append_attempt(tmp_path / "attempts.jsonl", payload)
