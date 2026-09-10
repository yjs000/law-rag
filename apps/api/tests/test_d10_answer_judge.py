from scripts.d10_answer_judge import AnswerJudgeInput, judge_answer


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
