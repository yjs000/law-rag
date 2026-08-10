from datetime import date
from uuid import uuid4

from app.adapters.openai_answerer import build_messages, build_messages_v2
from app.domain.catalog import SourceKind
from app.domain.schemas import QuestionRequest, SearchHit


def _request() -> QuestionRequest:
    return QuestionRequest(question="태양광 발전사업 허가가 필요한가요?")


def _hits() -> list[SearchHit]:
    return [
        SearchHit(
            provision_id=uuid4(),
            document_id=uuid4(),
            document_title="전기사업법",
            source_kind=SourceKind.LAW,
            version_label="MST 1",
            effective_from=date(2026, 1, 1),
            effective_to=None,
            path="제7조제1항",
            heading="전기사업의 허가",
            content="전기사업을 하려는 자는 산업통상자원부장관의 허가를 받아야 한다.",
            source_url="https://www.law.go.kr/법령/전기사업법",
        )
    ]


def _v2_system_text() -> str:
    messages = build_messages_v2(_request(), _hits())
    return messages[0]["content"]


def test_v2_system_prompt_limits_summary_to_three_sentences() -> None:
    assert "summary" in _v2_system_text()
    assert "최대 3문장" in _v2_system_text()


def test_v2_system_prompt_requires_plain_term_before_legal_term() -> None:
    text = _v2_system_text()
    assert "쉬운 뜻" in text
    assert "괄호 안에 한 번만" in text


def test_v2_system_prompt_limits_one_condition_per_sentence() -> None:
    assert "한 문장에는" in _v2_system_text()
    assert "하나만" in _v2_system_text()


def test_v2_system_prompt_requires_actionable_checklist_labels() -> None:
    assert "동사형" in _v2_system_text()


def test_v2_system_prompt_caps_limitations_and_splits_confirmed_vs_unconfirmed() -> None:
    text = _v2_system_text()
    assert "최대 3개" in text
    assert "현재 확인된 것" in text
    assert "아직 확정할 수 없는 것" in text


def test_v2_system_prompt_still_forbids_ungrounded_additions() -> None:
    assert "근거에 없는" in _v2_system_text()


def test_v2_system_prompt_still_has_v1_citation_safety_rules() -> None:
    text = _v2_system_text()
    assert "제공된 근거만 사용" in text
    assert "존재하는 C번호" in text


def test_v2_system_prompt_still_forbids_guessing_applicability() -> None:
    """v1 has "적용 여부를 추정하지 않는다" right after the summary/결론 guidance;
    v2 must carry the same substance even though it phrases summary rules differently."""
    assert "적용 여부를 추정하지 않는다" in _v2_system_text()


def test_v2_system_prompt_still_forbids_new_claims_via_limitations() -> None:
    """v1 ends its limitations guidance with "limitations에 새로운 법률 주장을
    추가하지 않는다." v2 lets limitations do more work (capped at 3, confirmed vs
    unconfirmed split) so it especially needs this guardrail preserved."""
    assert "limitations에도 새로운 법률 주장을 추가하지 않는다" in _v2_system_text()


def test_v1_prompt_text_is_unchanged_by_v2_addition() -> None:
    v1_text = build_messages(_request(), _hits())[0]["content"]
    assert "최대 3문장" not in v1_text
    assert "제공된 근거만 사용" in v1_text


def test_v2_system_prompt_requires_unanswerable_when_evidence_is_empty() -> None:
    messages = build_messages_v2(_request(), [])
    text = messages[0]["content"]
    assert "근거가 비어 있으면" in text
    assert "unanswerable" in text


def test_v2_user_message_carries_same_evidence_block_as_v1() -> None:
    v1_user = build_messages(_request(), _hits())[-1]["content"]
    v2_user = build_messages_v2(_request(), _hits())[-1]["content"]
    assert v1_user == v2_user
