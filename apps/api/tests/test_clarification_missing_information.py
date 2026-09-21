import pytest

from app.application.answering import (
    clarification_resubmission_summary,
    safe_clarification_missing_fields,
)


def test_clarification_summary_preserves_freeform_question_with_example() -> None:
    summary = clarification_resubmission_summary(
        "제 설비 용량에 맞는 절차는 무엇인가요?",
        ["발전설비의 용량은 얼마인가요? (예: 50kW)"],
    )

    assert summary.endswith(
        "추가 정보:\n- 발전설비의 용량은 얼마인가요? (예: 50kW): [ ]"
    )


def test_structural_validation_accepts_new_labels_but_requires_examples_for_questions() -> None:
    fields = safe_clarification_missing_fields(
        [" 계약 체결 방식 ", "계약 체결 방식", "계약 방식은 무엇인가요?"]
    )

    assert fields == ("계약 체결 방식",)


def test_structural_validation_does_not_confuse_noun_labels_with_sentences() -> None:
    fields = safe_clarification_missing_fields(
        ["사업개요", "계약 방식을 알려주세요", "전기사업법이 적용됩니다"]
    )

    assert fields == ("사업개요",)


@pytest.mark.parametrize(
    "unsafe_value",
    [
        "설비\n용량은 얼마인가요? (예: 50kW)",
        "참고할 주소는 무엇인가요? (예: https://example.com)",
        "**계약 조건**은 무엇인가요? (예: 전량 판매)",
        "<b>용도</b>는 무엇인가요? (예: 주거)",
        "설비\u202e 용량은 얼마인가요? (예: 50kW)",
        "전기사업법이 적용됩니다. (예: 적용)",
        "설비 용량은 얼마인가요? (예: 50kW) 전기사업법이 적용됩니다.",
    ],
)
def test_structural_validation_rejects_unsafe_display_patterns(unsafe_value: str) -> None:
    assert safe_clarification_missing_fields([unsafe_value]) == ()


def test_structural_validation_limits_public_questions_to_five() -> None:
    fields = [f"추가 정보 {index}는 무엇인가요? (예: 값 {index})" for index in range(1, 7)]

    assert safe_clarification_missing_fields(fields) == tuple(fields[:5])


def test_structural_validation_accepts_longform_example_marker() -> None:
    value = (
        "발전설비에서 생산한 전기를 어떤 계약 방식으로 사용할 예정인가요? "
        "(예시: 전량 판매)"
    )

    assert safe_clarification_missing_fields([value]) == (value,)


@pytest.mark.parametrize(
    "invalid_example",
    [
        "발전설비의 용량은 얼마인가요? (예: )",
        "발전설비의 용량은 얼마인가요? (예: 50kW",
    ],
)
def test_structural_validation_rejects_incomplete_examples(invalid_example: str) -> None:
    assert safe_clarification_missing_fields([invalid_example]) == ()


def test_structural_validation_rejects_items_over_160_characters() -> None:
    value = f"필요한 내용은 무엇인가요? (예: {'가' * 150})"
    assert len(value) > 160

    assert safe_clarification_missing_fields([value]) == ()
