"""Deterministic, text-free action and grounding checks for native D-10 runs."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

ExpectedAction = Literal[
    "answer",
    "partial_answer_with_limits",
    "ask_clarifying_question",
    "insufficient_evidence",
]


@dataclass(frozen=True, slots=True)
class AnswerJudgeInput:
    expected_action: ExpectedAction
    actual_action: str | None
    answer_present: bool
    has_limit: bool
    retrieved_evidence_ids: tuple[str, ...]
    citation_evidence_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class AnswerJudgeResult:
    passed: bool
    codes: tuple[str, ...]


def judge_answer(value: AnswerJudgeInput) -> AnswerJudgeResult:
    """Judge only structural answer metadata; raw answer/evidence stays private."""
    codes: list[str] = []
    if value.expected_action == "ask_clarifying_question" and value.answer_present:
        codes.append("clarification_answer_leak")
    if value.expected_action == "insufficient_evidence" and value.answer_present:
        codes.append("insufficient_evidence_answer_leak")
    if value.actual_action != value.expected_action:
        codes.append("expected_action_mismatch")
    if value.expected_action in {"answer", "partial_answer_with_limits"}:
        if not value.answer_present:
            codes.append("answer_empty")
        if not value.retrieved_evidence_ids:
            codes.append("answer_missing_retrieved_evidence")
        if not value.citation_evidence_ids or not set(value.citation_evidence_ids) <= set(
            value.retrieved_evidence_ids
        ):
            codes.append("citation_not_in_retrieval_evidence")
    if value.expected_action == "partial_answer_with_limits" and not value.has_limit:
        codes.append("partial_limit_missing")
    return AnswerJudgeResult(passed=not codes, codes=tuple(codes))
