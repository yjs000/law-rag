from datetime import date
from uuid import uuid4

from app.application.answering import search_only_answer
from app.domain.catalog import SourceKind
from app.domain.schemas import ProjectStage, QuestionRequest, SearchHit


def test_search_only_answer_citations_are_existing_exact_evidence() -> None:
    hit = SearchHit(
        provision_id=uuid4(),
        document_id=uuid4(),
        document_title="전기사업법",
        source_kind=SourceKind.LAW,
        version_label="MST 1",
        effective_from=date(2025, 1, 1),
        effective_to=None,
        path="제1조",
        content="원문 내용",
        source_url="https://example.test",
        score=1,
    )
    response = search_only_answer(
        QuestionRequest(
            question="무엇을 확인하나요?",
            as_of_date=date(2026, 1, 1),
            project_stage=ProjectStage.PLANNING,
        ),
        [hit],
    )
    assert response.mode == "search_only"
    assert response.citations[0].quote == hit.content
    assert response.sections[0].citation_ids == [response.citations[0].id]
