"""F-010: representative plain-language questions and their pass criteria.

각 항목은 초등학생도 이해할 수 있는 쉬운 한국어 답변 기준을 고정하기 위한 대표 질문이다.
실제 모델 호출 평가(Task 3)는 NVIDIA 개발 credential과 network 실행 승인이 필요해 이
worktree에서는 수행하지 않는다 - 여기서는 각 질문이 어떤 네 가지 기준으로 판정되어야
하는지만 회귀 가능한 데이터로 고정한다.

네 가지 합격 기준(모든 질문 공통):
- no_unexplained_jargon: 설명 없는 전문용어가 없어야 한다(법률 용어가 나오면 바로 쉬운
  뜻을 붙인다).
- directly_answers: 질문에 바로 답해야 한다(에두르거나 다른 질문에 답하지 않는다).
- clear_next_action: 사용자가 다음에 할 일이 분명해야 한다(동사형 행동 문장).
- no_ungrounded_claims: 근거 밖의 법률·기관·절차를 주장하지 않아야 한다.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PlainLanguageCase:
    id: str
    category: str
    question: str
    pass_criteria: tuple[str, str, str, str]


PLAIN_LANGUAGE_CASES: tuple[PlainLanguageCase, ...] = (
    PlainLanguageCase(
        id="permit",
        category="허가",
        question="태양광 발전사업을 하려면 허가를 받아야 하나요?",
        pass_criteria=(
            "no_unexplained_jargon",
            "directly_answers",
            "clear_next_action",
            "no_ungrounded_claims",
        ),
    ),
    PlainLanguageCase(
        id="report",
        category="신고",
        question="소규모 태양광 설비는 신고만 하면 되나요?",
        pass_criteria=(
            "no_unexplained_jargon",
            "directly_answers",
            "clear_next_action",
            "no_ungrounded_claims",
        ),
    ),
    PlainLanguageCase(
        id="effective_date",
        category="기준일",
        question="이 기준은 언제부터 적용되나요?",
        pass_criteria=(
            "no_unexplained_jargon",
            "directly_answers",
            "clear_next_action",
            "no_ungrounded_claims",
        ),
    ),
    PlainLanguageCase(
        id="applicability",
        category="적용 대상",
        question="저희 발전소도 이 규정의 적용 대상인가요?",
        pass_criteria=(
            "no_unexplained_jargon",
            "directly_answers",
            "clear_next_action",
            "no_ungrounded_claims",
        ),
    ),
    PlainLanguageCase(
        id="insufficient_evidence",
        category="근거 부족",
        question="계약서상 위약금 조항이 유효한가요?",
        pass_criteria=(
            "no_unexplained_jargon",
            "directly_answers",
            "clear_next_action",
            "no_ungrounded_claims",
        ),
    ),
    PlainLanguageCase(
        id="clarification",
        category="clarification",
        question="제 설비 용량에 맞는 절차는 무엇인가요?",
        pass_criteria=(
            "no_unexplained_jargon",
            "directly_answers",
            "clear_next_action",
            "no_ungrounded_claims",
        ),
    ),
)
