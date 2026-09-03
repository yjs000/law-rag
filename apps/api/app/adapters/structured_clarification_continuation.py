"""Non-NVIDIA structured continuation intent and fact extraction."""

from __future__ import annotations

from typing import Literal

from app.application.clarification_workflow import ClarificationTurnJudgment
from app.domain.clarification import RequiredFact


class StructuredClarificationContinuationExtractor:
    """Accept structured client facts without invoking the initial Ultra judge."""

    async def extract_continuation(
        self,
        *,
        original_question: str,
        unresolved_facts: tuple[RequiredFact, ...],
        user_text: str,
    ) -> ClarificationTurnJudgment:
        del original_question, unresolved_facts
        try:
            parsed = ClarificationTurnJudgment.model_validate_json(user_text)
        except ValueError:
            return ClarificationTurnJudgment(intent=_free_text_intent(user_text))
        return ClarificationTurnJudgment(
            intent=parsed.intent,
            submitted_facts=parsed.submitted_facts,
            required_facts=(),
        )


def _free_text_intent(
    user_text: str,
) -> Literal["ask_about_case", "cancel_case", "request_answer_now", "start_new_question"]:
    normalized = " ".join(user_text.split())
    if "취소" in normalized:
        return "cancel_case"
    if "새 질문" in normalized:
        return "start_new_question"
    if "답변" in normalized and ("현재" in normalized or "지금" in normalized):
        return "request_answer_now"
    return "ask_about_case"
