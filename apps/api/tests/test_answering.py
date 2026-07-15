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
    assert response.sections[0].claim == "전기사업법 · 제1조"
    assert response.checklist[0].citation_ids == [response.citations[0].id]
    assert "법적 결론을 생성하지 않고" in response.summary
    assert "근거 1건" in response.scope


def test_search_only_answer_keeps_each_check_tied_to_its_own_evidence() -> None:
    hits = [
        SearchHit(
            provision_id=uuid4(),
            document_id=uuid4(),
            document_title=title,
            source_kind=SourceKind.LAW,
            version_label="MST 1",
            effective_from=date(2025, 1, 1),
            effective_to=None,
            path=path,
            heading=heading,
            content=content,
            source_url=f"https://example.test/{index}",
            score=1,
        )
        for index, (title, path, heading, content) in enumerate(
            [
                ("전기사업법", "제7조", "전기사업의 허가", "허가를 받아야 한다."),
                ("전기안전관리법", "제8조", "자체검사", "검사 결과를 기록한다."),
            ],
            1,
        )
    ]
    response = search_only_answer(
        QuestionRequest(
            question="허가와 검사는 무엇을 확인하나요?",
            as_of_date=date(2026, 1, 1),
            project_stage=ProjectStage.PLANNING,
        ),
        hits,
    )
    assert [section.citation_ids for section in response.sections] == [["C1"], ["C2"]]
    assert [item.citation_ids for item in response.checklist] == [["C1"], ["C2"]]
    assert response.sections[0].claim == "전기사업법 · 제7조 · 전기사업의 허가"
    assert response.sections[1].explanation == hits[1].content
