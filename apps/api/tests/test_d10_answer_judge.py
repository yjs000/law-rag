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
        retrieved_evidence_ids=("p1",),
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
            limitations=("검색된 근거와 제공된 사실만으로 확인 가능한 범위의 답변입니다.",),
            citations=(SimpleNamespace(provision_id="p1", quote="private statute"),),
        ),
        retrieved_evidence_ids=("p1",),
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


def test_execution_judge_rejects_generic_disclaimer_as_partial_limit() -> None:
    execution = D10AnswerExecution(
        case_id="lay-energy-0201",
        response=SimpleNamespace(
            action="partially_answerable",
            summary="private grounded summary",
            sections=(),
            limitations=("이 서비스는 법률 자문을 대체하지 않습니다.",),
            citations=(SimpleNamespace(provision_id="p1", quote="private statute"),),
        ),
        retrieved_evidence_ids=("p1",),
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
    assert result.codes == ("partial_limit_missing",)


def test_execution_judge_rejects_substantive_legal_claim_in_limitations() -> None:
    execution = D10AnswerExecution(
        case_id="lay-energy-0201",
        response=SimpleNamespace(
            action="partially_answerable",
            summary="private grounded summary",
            sections=(),
            limitations=(
                "사업자는 허가를 받아야 합니다.",
                "이 서비스는 법률 자문을 대체하지 않습니다.",
            ),
            citations=(SimpleNamespace(provision_id="p1", quote="private statute"),),
        ),
        retrieved_evidence_ids=("p1",),
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
    assert result.codes == ("unsafe_limit", "partial_limit_missing")


@pytest.mark.parametrize("summary", ["", "   "])
def test_execution_judge_rejects_empty_summary_when_sections_are_empty(summary: str) -> None:
    execution = D10AnswerExecution(
        case_id="lay-energy-0201",
        response=SimpleNamespace(
            action="partially_answerable",
            summary=summary,
            sections=(),
            limitations=("검색된 근거와 제공된 사실만으로 확인 가능한 범위의 답변입니다.",),
            citations=(SimpleNamespace(provision_id="p1", quote="private statute"),),
        ),
        retrieved_evidence_ids=("p1",),
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

def test_execution_judge_rejects_citation_not_in_independent_retrieval() -> None:
    execution = D10AnswerExecution(
        case_id="lay-energy-0201",
        response=SimpleNamespace(
            action="fully_answerable",
            summary="private answer",
            sections=(),
            checklist=(),
            limitations=(),
            citations=(SimpleNamespace(provision_id="p2"),),
        ),
        retrieved_evidence_ids=("p1",),
    )
    case = D10RunInput(
        "lay-energy-0201", "private question", date(2026, 8, 5), "snapshot-1", "answer"
    )

    result = judge_execution(case, execution)

    assert result.codes == ("citation_not_in_retrieval_evidence",)


@pytest.mark.parametrize(
    ("expected_action", "runtime_action", "expected_code"),
    (
        ("ask_clarifying_question", "clarification_required", "clarification_answer_leak"),
        ("insufficient_evidence", "unanswerable", "insufficient_evidence_answer_leak"),
    ),
)
@pytest.mark.parametrize(
    "summary",
    (
        "사업자는 허가를 받아야 합니다.",
        "이 사업은 허가 대상입니다.",
        "이 시설은 설치할 수 있습니다.",
        "관할 기관에 신고가 필요합니다.",
        "이 경우 허가가 면제됩니다.",
        "전기사업법이 적용됩니다.",
        "관할청 승인을 받으면 됩니다.",
        "신고 없이 진행 가능합니다.",
        "농지전용 대상에 해당합니다.",
        "정확한 판단을 위해 용량 정보가 필요하며 전기사업법이 적용됩니다.",
        "검색 근거는 부족하지만 전기사업법이 적용됩니다.",
        "용량 정보가 필요합니다.전기사업법이 적용됩니다.",
        (
            "정확한 절차를 확인하려면 추가 정보가 필요합니다.\n"
            "다음 메시지에는 아래 내용을 전체 복사한 뒤 [ ]를 채워 한 번에 보내주세요.\n"
            "추가 정보만 따로 보내지 마세요.\n\n"
            "질문: 용량은 얼마인가요?\n"
            "추가 정보:\n- 전기사업법이 적용됩니다: [ ]"
        ),
    ),
)
def test_execution_judge_rejects_declarative_legal_answer_leak(
    expected_action: str, runtime_action: str, expected_code: str, summary: str
) -> None:
    execution = D10AnswerExecution(
        case_id="lay-energy-0201",
        response=SimpleNamespace(
            action=runtime_action,
            summary=summary,
            sections=(),
            checklist=(),
            limitations=(),
            citations=(),
        ),
        retrieved_evidence_ids=(),
    )
    case = D10RunInput(
        "lay-energy-0201",
        "private question",
        date(2026, 8, 5),
        "snapshot-1",
        expected_action,
    )

    result = judge_execution(case, execution)

    assert result.codes == (expected_code,)

@pytest.mark.parametrize(
    ("expected_action", "runtime_action", "summary"),
    (
        (
            "ask_clarifying_question",
            "clarification_required",
            (
                "정확한 절차를 확인하려면 추가 정보가 필요합니다.\n"
                "다음 메시지에는 아래 내용을 전체 복사한 뒤 [ ]를 채워 한 번에 보내주세요.\n"
                "추가 정보만 따로 보내지 마세요.\n\n"
                "질문: 용량은 얼마인가요?\n"
                "추가 정보:\n- 설비용량: [ ]"
            ),
        ),
        (
            "insufficient_evidence",
            "unanswerable",
            "검증된 법률 주장을 만들지 못했습니다. 인용된 공식 원문을 직접 확인해 주세요.",
        ),
    ),
)
def test_execution_judge_allows_only_explicit_nonanswer_explanations(
    expected_action: str, runtime_action: str, summary: str
) -> None:
    execution = D10AnswerExecution(
        case_id="lay-energy-0201",
        response=SimpleNamespace(
            action=runtime_action,
            summary=summary,
            sections=(),
            checklist=(),
            limitations=(),
            citations=(),
        ),
        retrieved_evidence_ids=(),
    )
    case = D10RunInput(
        "lay-energy-0201",
        "private question",
        date(2026, 8, 5),
        "snapshot-1",
        expected_action,
    )

    assert judge_execution(case, execution).passed is True

@pytest.mark.parametrize(
    ("route", "summary"),
    (
        (
            "realtime_required",
            (
                "이 질문은 시점에 따라 달라지는 정보"
                "(예: 올해 예산, 현재 가격, 고장 상태)가 필요합니다.\n"
                "법령 corpus만으로는 답할 수 없으니 해당 연도·기관의 최신 공고나 "
                "담당 기관에 직접 확인해 주세요."
            ),
        ),
        (
            "external_document_required",
            (
                "이 질문은 계약서·정산서·공사비 산출서 같은 문서 확인이 필요합니다.\n"
                "법령 corpus만으로는 확정할 수 없으니 해당 문서를 직접 대조해 확인해 주세요."
            ),
        ),
    ),
)
def test_execution_judge_allows_deterministic_nonlegal_route_guidance(
    route: str, summary: str
) -> None:
    execution = D10AnswerExecution(
        case_id="lay-energy-0201",
        response=SimpleNamespace(
            action="unanswerable",
            route=route,
            summary=summary,
            sections=(),
            checklist=(),
            limitations=(),
            citations=(),
        ),
        retrieved_evidence_ids=(),
    )
    case = D10RunInput(
        "lay-energy-0201",
        "private question",
        date(2026, 8, 5),
        "snapshot-1",
        "insufficient_evidence",
    )

    assert judge_execution(case, execution).passed is True

def test_execution_judge_rejects_legal_claim_forged_as_nonlegal_route() -> None:
    execution = D10AnswerExecution(
        case_id="lay-energy-0201",
        response=SimpleNamespace(
            action="unanswerable",
            route="realtime_required",
            summary="전기사업법이 적용되며 허가를 받아야 합니다.",
            sections=(),
            checklist=(),
            limitations=(),
            citations=(),
        ),
        retrieved_evidence_ids=(),
    )
    case = D10RunInput(
        "lay-energy-0201",
        "private question",
        date(2026, 8, 5),
        "snapshot-1",
        "insufficient_evidence",
    )

    assert judge_execution(case, execution).codes == ("insufficient_evidence_answer_leak",)
