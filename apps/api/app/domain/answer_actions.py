from __future__ import annotations

from typing import Literal

from law_rag_core.domain.schemas import AiFallbackReason, ChecklistItem

AnswerAction = Literal[
    "fully_answerable",
    "partially_answerable",
    "clarification_required",
    "unanswerable",
]

# MOCK/미확정, 2026-08-08 (0025 M5 item 2): D-10 gold의 answerability 네 값
# (fully_answerable | partially_answerable | clarification_required | unanswerable, 0025
# 문서 라인 256)과 이름을 맞췄지만, checklist status -> action 매핑 규칙 자체는 D-10 gold
# 기준으로 검증된 적이 없다 - 첫 추정치이며 실제 D-10 10문항에 돌려서 gold와 비교한 뒤
# 확정해야 한다. 규칙: 어떤 항목이든 "check"(모델이 스스로 적용 여부 불확실 표시)가 있으면
# clarification_required, "conditional"이 있으면(단 "check"는 없을 때) partially_answerable,
# 전부 required/not_applicable이면 fully_answerable, checklist가 비어 있으면 unanswerable
# (validate_draft가 이미 빈 checklist를 걸러내므로 이 경로는 생성 성공 시 거의 발생하지
# 않고, 검색 전용 fallback 쪽에서 별도로 unanswerable을 붙이는 게 더 정확할 수 있다).
def derive_answer_action(checklist: list[ChecklistItem]) -> AnswerAction:
    if not checklist:
        return "unanswerable"
    statuses = {item.status for item in checklist}
    if "check" in statuses:
        return "clarification_required"
    if "conditional" in statuses:
        return "partially_answerable"
    return "fully_answerable"


# 2026-08-08: search_only_answer()의 fallback checklist는 근거가 있으면 무조건 전부
# "check" 상태를 쓴다("원문에서 요건을 대조하세요") - 이는 AI가 판단을 유보했다는 뜻이
# 아니라 애초에 AI 생성을 시도조차 안 했다는 뜻이라 derive_answer_action()을 그대로
# 적용하면 항상 clarification_required로 잘못 나온다. fallback_reason만으로 판단한다:
# NO_EVIDENCE·GROUNDING_FAILED는 "법령 corpus로 답을 못 냈다"는 뜻이라 unanswerable로
# 본다. 나머지(AI_DISABLED·QUOTA_EXHAUSTED·BILLING_OR_QUOTA_ERROR·EMBEDDING_ERROR·
# GENERATION_ERROR)는 시스템/운영 실패이지 "법령으로 답할 수 있는지"에 대한 판단이
# 아니므로 action을 모른다는 뜻의 None을 반환한다. fallback_reason이 아예 없으면
# (사용자가 search_only를 직접 요청한 경우) 마찬가지로 None.
def derive_fallback_action(fallback_reason: AiFallbackReason | None) -> AnswerAction | None:
    if fallback_reason in (AiFallbackReason.NO_EVIDENCE, AiFallbackReason.GROUNDING_FAILED):
        return "unanswerable"
    return None
