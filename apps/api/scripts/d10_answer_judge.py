"""Deterministic, text-free action and grounding checks for native D-10 runs."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from app.application.answering import is_deterministic_nonanswer_route_guidance
from scripts.d10_failure_runner import D10AnswerExecution, D10RunInput

ExpectedAction = Literal[
    "answer",
    "partial_answer_with_limits",
    "ask_clarifying_question",
    "insufficient_evidence",
]

_SAFE_CLARIFICATION_HEADER = (
    "정확한 절차를 확인하려면 추가 정보가 필요합니다.\n"
    "다음 메시지에는 아래 내용을 전체 복사한 뒤 [ ]를 채워 한 번에 보내주세요.\n"
    "추가 정보만 따로 보내지 마세요."
)
_SAFE_UNANSWERABLE_SUMMARIES = {
    "검증된 법률 주장을 만들지 못했습니다. 인용된 공식 원문을 직접 확인해 주세요.",
}
_SAFE_CLARIFICATION_FIELDS = {
    "설비용량",
    "전압",
    "전기 사용 방식",
    "공사 종류",
    "토지 지목",
    "용도지역",
}
_GENERIC_LEGAL_DISCLAIMER = "이 서비스는 법률 자문을 대체하지 않습니다."
_SAFE_PARTIAL_LIMITATION = "검색된 근거와 제공된 사실만으로 확인 가능한 범위의 답변입니다."

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


def _is_safe_clarification_summary(summary: str) -> bool:
    prefix = f"{_SAFE_CLARIFICATION_HEADER}\n\n질문: "
    if not summary.startswith(prefix):
        return False
    question_and_fields = summary.removeprefix(prefix)
    marker = "\n추가 정보:\n"
    if marker not in question_and_fields:
        return False
    question, fields = question_and_fields.rsplit(marker, 1)
    field_lines = fields.splitlines()
    expected_lines = {f"- {field}: [ ]" for field in _SAFE_CLARIFICATION_FIELDS}
    return (
        bool(question.strip())
        and bool(field_lines)
        and all(line in expected_lines for line in field_lines)
        and len(field_lines) == len(set(field_lines))
    )


def _contains_substantive_nonanswer(
    summary: str, actual_action: str | None, route: str | None
) -> bool:
    if actual_action == "clarification_required":
        return not _is_safe_clarification_summary(summary)
    if actual_action == "unanswerable":
        if is_deterministic_nonanswer_route_guidance(route, summary):
            return False
        return summary not in _SAFE_UNANSWERABLE_SUMMARIES
    return bool(summary.strip())

def judge_execution(case: D10RunInput, execution: D10AnswerExecution) -> AnswerJudgeResult:
    """Extract only structural metadata from a private response for deterministic judgment."""
    if execution.response is None or case.expected_action is None:
        return AnswerJudgeResult(False, ("answer_unavailable",))
    safe = execution.safe_result()
    response = execution.response
    actual_action = safe["actual_action"]
    summary = getattr(response, "summary", "")
    sections = getattr(response, "sections", ())
    checklist = getattr(response, "checklist", ())
    citations = getattr(response, "citations", ())
    citation_ids = tuple(
        str(citation.provision_id)
        for citation in citations
        if getattr(citation, "provision_id", None) is not None
    )
    substantive_answer = bool(sections) or bool(checklist) or bool(citations)
    if isinstance(summary, str):
        substantive_answer = substantive_answer or _contains_substantive_nonanswer(
            summary,
            str(getattr(response, "action", "")) or None,
            str(getattr(response, "route", "")) or None,
        )
    answer_present = (
        bool(sections) or (isinstance(summary, str) and bool(summary.strip()))
        if case.expected_action in {"answer", "partial_answer_with_limits"}
        else substantive_answer
    )
    limitations = tuple(
        limit.strip()
        for limit in getattr(response, "limitations", ())
        if isinstance(limit, str) and limit.strip()
    )
    result = judge_answer(
        AnswerJudgeInput(
            expected_action=case.expected_action,  # validated by the sealed loader
            actual_action=actual_action if isinstance(actual_action, str) else None,
            answer_present=answer_present,
            has_limit=_SAFE_PARTIAL_LIMITATION in limitations,
            retrieved_evidence_ids=execution.retrieved_evidence_ids,
            citation_evidence_ids=citation_ids,
        )
    )
    unsafe_limit = case.expected_action == "partial_answer_with_limits" and any(
        limit not in {_SAFE_PARTIAL_LIMITATION, _GENERIC_LEGAL_DISCLAIMER}
        for limit in limitations
    )
    if unsafe_limit:
        return AnswerJudgeResult(False, ("unsafe_limit", *result.codes))
    return result
