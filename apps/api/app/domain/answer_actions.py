from __future__ import annotations

from typing import Literal

from law_rag_core.domain.schemas import ChecklistItem

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
