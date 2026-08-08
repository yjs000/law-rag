from app.domain.answer_actions import derive_answer_action
from app.domain.schemas import ChecklistItem


def _item(status: str) -> ChecklistItem:
    return ChecklistItem(label="x", status=status, citation_ids=["C1"])  # type: ignore[arg-type]


def test_empty_checklist_is_unanswerable() -> None:
    assert derive_answer_action([]) == "unanswerable"


def test_any_check_status_is_clarification_required() -> None:
    checklist = [_item("required"), _item("check")]
    assert derive_answer_action(checklist) == "clarification_required"


def test_any_conditional_without_check_is_partially_answerable() -> None:
    checklist = [_item("required"), _item("conditional")]
    assert derive_answer_action(checklist) == "partially_answerable"


def test_all_required_or_not_applicable_is_fully_answerable() -> None:
    checklist = [_item("required"), _item("not_applicable")]
    assert derive_answer_action(checklist) == "fully_answerable"
