from __future__ import annotations

import json
from datetime import date
from types import SimpleNamespace

import pytest

from scripts.d10_failure_runner import (
    D10FailureRunnerError,
    D10RunInput,
    load_d10_run_input,
    run_single_case,
)


def _workflow() -> object:
    return SimpleNamespace(
        corpus_binding=SimpleNamespace(as_of_date="2026-08-05", corpus_snapshot_id="snapshot-1")
    )


CASE_IDS = tuple(f"lay-energy-{number:04d}" for number in range(201, 211))


def _frozen(case_id: str = "lay-energy-0201") -> object:
    return SimpleNamespace(
        run_binding=SimpleNamespace(as_of_date="2026-08-05", corpus_snapshot_id="snapshot-1"),
        cases=tuple(
            SimpleNamespace(case_id=case_id, question_sha256="question-hash")
            for case_id in CASE_IDS
        ),
    )


def _manual(case_id: str = "lay-energy-0201") -> object:
    return SimpleNamespace(
        questions=tuple(
            SimpleNamespace(
                id=case_id, question="private question", question_sha256="question-hash"
            )
            for case_id in CASE_IDS
        ),
    )


def test_load_rejects_sealed_case_order_mismatch(tmp_path) -> None:
    (tmp_path / "dataset.json").write_text(
        '{"cases":[{"case_id":"different","question_sha256":"question-hash"}]}',
        encoding="utf-8",
    )

    with pytest.raises(D10FailureRunnerError, match="d10_contract_invalid"):
        load_d10_run_input(
            tmp_path,
            "lay-energy-0201",
            sealed_preflight=lambda _: {
                "status": "valid_approved_calibration_gold",
                "case_count": 10,
            },
            workflow_loader=_workflow,
            frozen_loader=_frozen,
            manual_loader=_manual,
        )


def test_load_returns_only_selected_case_and_frozen_binding(tmp_path) -> None:
    (tmp_path / "dataset.json").write_text(
        json.dumps(
            {"cases": [{"case_id": item, "question_sha256": "question-hash"} for item in CASE_IDS]}
        ),
        encoding="utf-8",
    )

    result = load_d10_run_input(
        tmp_path,
        "lay-energy-0201",
        sealed_preflight=lambda _: {"status": "valid_approved_calibration_gold", "case_count": 10},
        workflow_loader=_workflow,
        frozen_loader=_frozen,
        manual_loader=_manual,
    )

    assert result == D10RunInput(
        "lay-energy-0201", "private question", date(2026, 8, 5), "snapshot-1"
    )


class _Embedder:
    async def embed(self, texts: list[str]) -> list[list[float]]:
        assert texts == ["private question"]
        return [[0.1, 0.2]]


class _Reader:
    async def search(self, **_: object) -> list[object]:
        return [object()]


@pytest.mark.asyncio
async def test_single_case_returns_safe_pass_payload() -> None:
    result = await run_single_case(
        D10RunInput("lay-energy-0201", "private question", date(2026, 8, 5), "snapshot-1"),
        embedder=_Embedder(),
        reader=_Reader(),
    )

    assert result == {
        "case_id": "lay-energy-0201",
        "status": "pass",
        "error_code": None,
        "retrieved_evidence_count": 1,
        "citation_count": None,
        "citation_reason": "not_generated_by_retrieval_runner",
    }


@pytest.mark.asyncio
async def test_single_case_hides_provider_exception_and_marks_blocked() -> None:
    class BrokenEmbedder:
        async def embed(self, _: list[str]) -> list[list[float]]:
            raise RuntimeError("secret provider response")

    result = await run_single_case(
        D10RunInput("lay-energy-0201", "private question", date(2026, 8, 5), "snapshot-1"),
        embedder=BrokenEmbedder(),
        reader=_Reader(),
    )

    assert result["status"] == "blocked"
    assert result["error_code"] == "retrieval_unavailable"
    assert "private question" not in str(result)
    assert "secret provider response" not in str(result)
