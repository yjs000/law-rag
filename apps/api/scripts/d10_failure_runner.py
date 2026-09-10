"""Native, one-case-at-a-time D-10 retrieval boundary.

This module deliberately does not adapt D-10 into the separate 1,000-case Gold
dataset contract.  Question text stays inside ``D10RunInput`` and never enters
the result payload consumed by the failure ledger.
"""

from __future__ import annotations

import json
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Protocol

from app.domain.schemas import QuestionRequest
from scripts.experiment_d_10_frozen_contract import load_frozen_contract
from scripts.experiment_d_10_gold_review import (
    load_workflow_contract,
    preflight_sealed,
)
from scripts.experiment_d_manual_review_contract import load_manual_pilot_artifacts


class D10FailureRunnerError(RuntimeError):
    """A safe, stable D-10 execution-boundary error code."""


@dataclass(frozen=True, slots=True)
class D10RunInput:
    case_id: str
    question: str
    as_of_date: date
    corpus_snapshot_id: str


class QueryEmbedder(Protocol):
    async def embed(self, texts: list[str]) -> list[list[float]]: ...


class DenseReader(Protocol):
    async def search(
        self, *, as_of_date: date, query_embedding: list[float], limit: int
    ) -> list[object]: ...


class AnswerExecutor(Protocol):
    async def __call__(self, case: D10RunInput) -> object: ...


def application_answer_executor(
    execute: Callable[[QuestionRequest], Awaitable[object]],
) -> AnswerExecutor:
    """Bind a native D-10 input to the application answer request contract."""

    async def _execute(case: D10RunInput) -> object:
        return await execute(QuestionRequest(question=case.question, as_of_date=case.as_of_date))

    return _execute


def live_application_answer_executor(
    *,
    answer_question: Callable[[QuestionRequest, object, object, object, object], Awaitable[object]],
    repository: object,
    budget_factory: Callable[[], object],
) -> AnswerExecutor:
    """Call the v1 application use case directly, without HTTP ownership concerns."""

    async def _execute(case: D10RunInput) -> object:
        request = QuestionRequest(question=case.question, as_of_date=case.as_of_date)
        return await answer_question(request, None, None, budget_factory(), repository)

    return _execute


@dataclass(frozen=True, slots=True)
class D10AnswerExecution:
    """Private answer observation with a deliberately safe public projection."""

    case_id: str
    response: object | None
    retrieved_evidence_count: int
    error_code: str | None = None

    def safe_result(self) -> dict[str, object]:
        if self.response is None:
            return {
                "case_id": self.case_id,
                "status": "blocked",
                "error_code": self.error_code or "answer_unavailable",
                "retrieved_evidence_count": 0,
                "citation_count": 0,
                "citation_reason": "validated_by_answer_runner",
                "evaluation_stage": "answer",
                "actual_action": None,
                "judge_codes": [],
            }
        action = getattr(self.response, "action", None)
        return {
            "case_id": self.case_id,
            "status": "pass",
            "error_code": None,
            "retrieved_evidence_count": self.retrieved_evidence_count,
            "citation_count": len(getattr(self.response, "citations", ())),
            "citation_reason": "validated_by_answer_runner",
            "evaluation_stage": "answer",
            "actual_action": action,
            "judge_codes": [],
        }


def _contract_error() -> D10FailureRunnerError:
    return D10FailureRunnerError("d10_contract_invalid")


def _read_dataset_cases(sealed_directory: Path) -> list[dict[str, object]]:
    try:
        payload = json.loads((sealed_directory / "dataset.json").read_text(encoding="utf-8"))
        cases = payload["cases"]
    except OSError, UnicodeDecodeError, json.JSONDecodeError, KeyError, TypeError:
        raise _contract_error() from None
    if (
        not isinstance(cases, list)
        or len(cases) != 10
        or not all(isinstance(case, dict) for case in cases)
    ):
        raise _contract_error()
    return cases


def load_d10_run_input(
    sealed_directory: Path,
    case_id: str,
    *,
    sealed_preflight: Callable[[Path], dict[str, object]] = preflight_sealed,
    workflow_loader: Callable[[], Any] = load_workflow_contract,
    frozen_loader: Callable[[], Any] = load_frozen_contract,
    manual_loader: Callable[[], Any] = load_manual_pilot_artifacts,
) -> D10RunInput:
    """Validate the native sealed/frozen D-10 chain and select one case."""
    try:
        sealed = sealed_preflight(sealed_directory)
        workflow = workflow_loader()
        frozen = frozen_loader()
        manual = manual_loader()
        dataset_cases = _read_dataset_cases(sealed_directory)
    except Exception:
        raise _contract_error() from None
    if sealed.get("status") != "valid_approved_calibration_gold" or sealed.get("case_count") != 10:
        raise _contract_error()
    dataset_ids = [case.get("case_id") for case in dataset_cases]
    frozen_ids = [case.case_id for case in frozen.cases]
    manual_ids = [question.id for question in manual.questions]
    if dataset_ids != frozen_ids or dataset_ids != manual_ids or len(set(dataset_ids)) != 10:
        raise _contract_error()
    if (
        workflow.corpus_binding.as_of_date != frozen.run_binding.as_of_date
        or workflow.corpus_binding.corpus_snapshot_id != frozen.run_binding.corpus_snapshot_id
    ):
        raise _contract_error()
    by_id = {question.id: question for question in manual.questions}
    frozen_by_id = {case.case_id: case for case in frozen.cases}
    dataset_by_id = {str(case["case_id"]): case for case in dataset_cases}
    question = by_id.get(case_id)
    frozen_case = frozen_by_id.get(case_id)
    dataset_case = dataset_by_id.get(case_id)
    if (
        question is None
        or frozen_case is None
        or dataset_case is None
        or question.question_sha256 != frozen_case.question_sha256
        or question.question_sha256 != dataset_case.get("question_sha256")
    ):
        raise _contract_error()
    return D10RunInput(
        case_id=case_id,
        question=question.question,
        as_of_date=date.fromisoformat(frozen.run_binding.as_of_date),
        corpus_snapshot_id=frozen.run_binding.corpus_snapshot_id,
    )


async def run_single_case(
    case: D10RunInput, *, embedder: QueryEmbedder, reader: DenseReader, limit: int = 10
) -> dict[str, object]:
    """Run one native D-10 retrieval without exposing sensitive execution input."""
    safe = {
        "case_id": case.case_id,
        "citation_count": None,
        "citation_reason": "not_generated_by_retrieval_runner",
    }
    try:
        vectors = await embedder.embed([case.question])
        if len(vectors) != 1 or not vectors[0]:
            raise ValueError("invalid embedding")
        hits = await reader.search(
            as_of_date=case.as_of_date, query_embedding=vectors[0], limit=limit
        )
    except Exception:
        return {
            **safe,
            "status": "blocked",
            "error_code": "retrieval_unavailable",
            "retrieved_evidence_count": 0,
        }
    count = len(hits)
    return {
        **safe,
        "status": "pass" if count else "failure",
        "error_code": None if count else "no_retrieved_evidence",
        "retrieved_evidence_count": count,
    }


async def run_single_answer_case(
    case: D10RunInput, *, answer_executor: AnswerExecutor
) -> D10AnswerExecution:
    """Execute the application answer boundary without serializing its private response."""
    try:
        response = await answer_executor(case)
    except Exception:
        return D10AnswerExecution(
            case_id=case.case_id,
            response=None,
            retrieved_evidence_count=0,
            error_code="answer_unavailable",
        )
    citations = getattr(response, "citations", ())
    if not isinstance(citations, (list, tuple)):
        return D10AnswerExecution(
            case_id=case.case_id,
            response=None,
            retrieved_evidence_count=0,
            error_code="answer_contract_invalid",
        )
    return D10AnswerExecution(
        case_id=case.case_id,
        response=response,
        retrieved_evidence_count=len(citations),
    )
