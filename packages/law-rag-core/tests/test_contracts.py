from datetime import UTC, date, datetime, timedelta
from uuid import uuid4

import pytest
from pydantic import ValidationError

from law_rag_core.domain.schemas import (
    AiFailureCategory,
    AiRuntimeState,
    AnswerMode,
    ChecklistDocument,
    ChecklistExportFormat,
    ChecklistItem,
    MockUser,
    ProjectStage,
    QuestionHistoryEntry,
    QuestionRequest,
    QuestionResponse,
)


def test_terra_failure_requires_search_only_with_reason() -> None:
    state = AiRuntimeState(
        mode=AnswerMode.SEARCH_ONLY,
        failure_category=AiFailureCategory.QUOTA,
    )

    assert state.requested_model == "gpt-5.6-terra"
    assert state.mode is AnswerMode.SEARCH_ONLY
    with pytest.raises(ValidationError):
        AiRuntimeState(mode=AnswerMode.SEARCH_ONLY)


def test_mock_user_history_and_checklist_share_canonical_contracts() -> None:
    now = datetime.now(UTC)
    user = MockUser(
        id=uuid4(), email="learner@example.test", display_name="학습자", created_at=now
    )
    request = QuestionRequest(question="허가가 필요한가요?", as_of_date=date(2026, 7, 13))
    response = QuestionResponse(
        request_id="request-1",
        mode=AnswerMode.SEARCH_ONLY,
        summary="검색 결과",
        scope="MVP",
        sections=[],
        checklist=[],
        citations=[],
        limitations=["법률 자문을 대체하지 않습니다."],
    )
    history = QuestionHistoryEntry(
        id=uuid4(),
        user_id=user.id,
        request=request,
        response=response,
        created_at=now,
        expires_at=now + timedelta(days=365),
    )
    checklist = ChecklistDocument(
        title="사업 체크리스트",
        as_of_date=request.as_of_date,
        project_stage=ProjectStage.PLANNING,
        items=[ChecklistItem(label="원문 확인", status="check", citation_ids=[])],
        citations=[],
    )

    assert history.user_id == user.id
    assert checklist.items[0].label == "원문 확인"
    assert ChecklistExportFormat.MARKDOWN.value == "md"
