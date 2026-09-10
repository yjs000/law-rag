from datetime import date
from types import SimpleNamespace

import pytest

from scripts.d10_answer_judge import AnswerJudgeInput, judge_answer, judge_execution
from scripts.d10_failure_runner import D10AnswerExecution, D10RunInput


def test_answer_requires_retrieved_evidence_and_bound_citations() -> None:
    result = judge_answer(
        AnswerJudgeInput(
            expected_action="answer",
            actual_action="answer",
            answer_present=True,
            has_limit=False,
            retrieved_evidence_ids=("p1",),
            citation_evidence_ids=("p2",),
        )
    )

    assert result.passed is False
    assert result.codes == ("citation_not_in_retrieval_evidence",)


def test_clarification_rejects_substantive_answer_leak() -> None:
    result = judge_answer(
        AnswerJudgeInput(
            expected_action="ask_clarifying_question",
            actual_action="answer",
            answer_present=True,
            has_limit=False,
            retrieved_evidence_ids=(),
            citation_evidence_ids=(),
        )
    )

    assert result.passed is False
    assert result.codes == ("clarification_answer_leak", "expected_action_mismatch")


def test_partial_answer_requires_limit_marker() -> None:
    result = judge_answer(
        AnswerJudgeInput(
            expected_action="partial_answer_with_limits",
            actual_action="partial_answer_with_limits",
            answer_present=True,
            has_limit=False,
            retrieved_evidence_ids=("p1",),
            citation_evidence_ids=("p1",),
        )
    )

    assert result.codes == ("partial_limit_missing",)


def test_insufficient_evidence_passes_without_substantive_answer() -> None:
    result = judge_answer(
        AnswerJudgeInput(
            expected_action="insufficient_evidence",
            actual_action="insufficient_evidence",
            answer_present=False,
            has_limit=False,
            retrieved_evidence_ids=(),
            citation_evidence_ids=(),
        )
    )

    assert result.passed is True
    assert result.codes == ()


def test_execution_judge_uses_private_response_only_for_structural_metadata() -> None:
    execution = D10AnswerExecution(
        case_id="lay-energy-0201",
        response=SimpleNamespace(
            action="fully_answerable",
            sections=(SimpleNamespace(claim="private answer"),),
            limitations=(),
            citations=(SimpleNamespace(provision_id="p1", quote="private statute"),),
        ),
        retrieved_evidence_count=1,
    )
    case = D10RunInput(
        "lay-energy-0201", "private question", date(2026, 8, 5), "snapshot-1", "answer"
    )

    result = judge_execution(case, execution)

    assert result.passed is True
    assert result.codes == ()


def test_execution_judge_accepts_nonempty_summary_when_sections_are_empty() -> None:
    execution = D10AnswerExecution(
        case_id="lay-energy-0201",
        response=SimpleNamespace(
            action="partially_answerable",
            summary="private grounded summary",
            sections=(),
            limitations=("private limit",),
            citations=(SimpleNamespace(provision_id="p1", quote="private statute"),),
        ),
        retrieved_evidence_count=1,
    )
    case = D10RunInput(
        "lay-energy-0201",
        "private question",
        date(2026, 8, 5),
        "snapshot-1",
        "partial_answer_with_limits",
    )

    result = judge_execution(case, execution)

    assert result.passed is True
    assert result.codes == ()


@pytest.mark.parametrize("summary", ["", "   "])
def test_execution_judge_rejects_empty_summary_when_sections_are_empty(summary: str) -> None:
    execution = D10AnswerExecution(
        case_id="lay-energy-0201",
        response=SimpleNamespace(
            action="partially_answerable",
            summary=summary,
            sections=(),
            limitations=("private limit",),
            citations=(SimpleNamespace(provision_id="p1", quote="private statute"),),
        ),
        retrieved_evidence_count=1,
    )
    case = D10RunInput(
        "lay-energy-0201",
        "private question",
        date(2026, 8, 5),
        "snapshot-1",
        "partial_answer_with_limits",
    )

    result = judge_execution(case, execution)

    assert result.passed is False
    assert result.codes == ("answer_empty",)
