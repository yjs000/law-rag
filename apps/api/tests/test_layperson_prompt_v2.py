from datetime import date
from uuid import uuid4

from fixtures.layperson_plain_language_questions import PLAIN_LANGUAGE_CASES

from app.adapters.openai_answerer import (
    CoreDraft,
    build_blocked_route_messages,
    build_core_messages,
    build_messages,
    build_messages_v2,
)
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

def test_v2_system_prompt_separates_evidence_review_from_legal_obligations() -> None:
    text = _v2_system_text()
    assert "확인하세요" in text
    assert "대조하세요" in text
    assert "확인해야 합니다" in text


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


def test_v2_action_prompt_keeps_conditional_legal_guidance_partial() -> None:
    text = _v2_system_text()
    assert "조건부로 설명할 수 있으면 'partially_answerable'" in text
    assert "실질적인 답을 전혀 제공할 수 없을 때만 'clarification_required'" in text
    assert "개별 결론을 확정할 수 없다는 이유만으로 'clarification_required'" in text
    assert "어느 경로가 적용되는지" in text
    assert "결정 사실의 실제 값" in text
    assert "결정축을 질문에서 직접 지목" in text
    assert "특정 설비에 적용될 경로" in text
    assert "하나라도 빠졌다면 'clarification_required'를 우선" in text
    assert "상충하면 이 규칙이 'partially_answerable' 일반 설명 규칙보다 우선" in text
    assert "허가·신고의 종류와 일반 구분 기준" in text
    assert "용량과 사용 방식에 따라 달라지는 자기 설비의 절차" in text
    assert "발급·신청의 법적 대상·요건·제한" in text
    assert "실제 미발급·미처리 사유" in text


def test_v2_core_prompt_separates_general_criteria_from_unknown_individual_reason() -> None:
    text = build_core_messages(_request(), _hits())[0]["content"]
    assert "decision_limitations에는 확인하지 못한 개별 사유" in text
    assert "action은 'partially_answerable'" in text


def test_v2_core_decision_limitations_are_never_persisted() -> None:
    draft = CoreDraft(
        summary="근거로 일반 기준을 확인할 수 있습니다.",
        citation_ids=["C1"],
        action="partially_answerable",
        decision_limitations=["개별 미처리 사유"],
    )
    assert "decision_limitations" in CoreDraft.model_json_schema()["properties"]
    assert "decision_limitations" not in draft.model_dump(mode="json")


def test_v1_prompt_has_its_own_plain_language_contract() -> None:
    v1_text = build_messages(_request(), _hits())[0]["content"]
    assert "첫 문장에서 질문에 직접 답한다" in v1_text
    assert "처음 나오는 전문용어와 약어" in v1_text
    assert "사용자가 먼저 할 수 있는 구체적인 행동" in v1_text
    assert "C번호는 citation_ids에만" in v1_text
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


# --- F-010: 초등학생도 이해할 수 있는 쉬운 한국어 언어 계약 회귀 ---
#
# 네 가지 합격 기준(fixtures/layperson_plain_language_questions.py와 동일하게 유지):
# no_unexplained_jargon, directly_answers, clear_next_action, no_ungrounded_claims.


def test_plain_language_fixture_covers_representative_categories() -> None:
    categories = {case.category for case in PLAIN_LANGUAGE_CASES}
    assert categories == {"허가", "신고", "기준일", "적용 대상", "근거 부족", "clarification"}
    expected_criteria = {
        "no_unexplained_jargon",
        "directly_answers",
        "clear_next_action",
        "no_ungrounded_claims",
    }
    for case in PLAIN_LANGUAGE_CASES:
        assert set(case.pass_criteria) == expected_criteria
        assert case.question.strip()


def test_v2_system_prompt_requires_short_one_idea_sentences() -> None:
    """F-010: 문장은 짧게, 한 문장에는 한 가지 뜻만 담아야 한다(길이 상한 명시)."""
    text = _v2_system_text()
    assert "짧은 문장" in text
    assert "한 문장에는 한 가지 뜻만" in text


def test_v2_system_prompt_requires_plain_word_before_legal_term() -> None:
    """F-010: 쉬운 생활 언어를 먼저 쓰고, 법률 용어는 그 다음에 보조로만 쓴다."""
    text = _v2_system_text()
    assert "쉬운 말을 먼저" in text


def test_v2_system_prompt_requires_immediate_gloss_next_to_legal_term() -> None:
    """F-010: 법률 용어가 나오면 바로 옆에서 쉬운 뜻을 풀어줘야 한다(문단 뒤가 아니라)."""
    text = _v2_system_text()
    assert "법률 용어 바로 뒤에 쉬운 뜻을 붙인다" in text


def test_v2_system_prompt_forbids_internal_state_names_and_stray_english() -> None:
    """F-010: 내부 상태명(예: action 값)이나 불필요한 영어를 답변 문장에 그대로 쓰지 않는다."""
    text = _v2_system_text()
    assert "내부 상태명" in text
    assert "불필요한 영어" in text


def test_v2_no_search_results_prompt_uses_plain_language_contract() -> None:
    """F-010: 검색 근거가 없을 때 안내 문구도 같은 쉬운 말 계약을 따라야 한다."""
    messages = build_blocked_route_messages(_request(), "realtime_required", None)
    text = messages[0]["content"]
    assert "짧은 문장" in text
    assert "쉬운 말을 먼저" in text


def test_clarification_route_missing_information_requires_example_value() -> None:
    """F-010: clarification 요청은 "무엇을 알려 달라는지"뿐 아니라 간단한 입력 예시(값)도
    바로 이해할 수 있게 써야 한다 - 필드명만이 아니라 구체적인 예시 값을 요구한다."""
    messages = build_blocked_route_messages(_request(), "clarification_required", None)
    text = messages[0]["content"]
    assert "간단한 예시 값" in text


def test_all_clarification_prompts_require_questions_examples_and_no_legal_answers() -> None:
    prompt_texts = [
        build_messages(_request(), _hits())[0]["content"],
        build_messages_v2(_request(), _hits())[0]["content"],
        build_core_messages(_request(), _hits())[0]["content"],
        build_blocked_route_messages(_request(), "clarification_required", None)[0]["content"],
    ]

    for text in prompt_texts:
        assert "사용자가 답할 수 있는 질문" in text
        assert "간단한 예시 값" in text
        assert "법률 판단이나 답변" in text


def test_nvidia_clarification_judgment_prompt_uses_plain_language_contract() -> None:
    """F-010: NVIDIA NIM clarification 후보 생성 프롬프트도 같은 언어 계약을 따라야 한다."""
    from app.adapters.nvidia_nim_clarification import build_initial_judgment_messages

    text = build_initial_judgment_messages("태양광 발전사업 허가가 필요한가요?")[0]["content"]
    assert "짧은 문장" in text
    assert "한 문장에는 한 가지 뜻만" in text
    assert "쉬운 말을 먼저" in text
    assert "법률 용어 바로 뒤에 쉬운 뜻을 붙인다" in text
    assert "간단한 예시 값" in text


def test_v2_core_answers_the_exact_question_in_the_first_sentence() -> None:
    text = build_core_messages(_request(), _hits())[0]["content"]
    assert "첫 문장에서 질문에 직접 답한다" in text
    assert "신고만으로 충분한지" in text
    assert "C번호는 citation_ids에만" in text
