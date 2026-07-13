from uuid import uuid4

from app.domain.schemas import (
    AnswerSection,
    ChecklistItem,
    Citation,
    QuestionRequest,
    QuestionResponse,
    SearchHit,
)


def search_only_answer(
    request: QuestionRequest, hits: list[SearchHit], corpus_as_of=None
) -> QuestionResponse:
    citations = [
        Citation(
            id=f"C{index}",
            provision_id=hit.provision_id,
            document_title=hit.document_title,
            version_label=hit.version_label,
            path=hit.path,
            quote=hit.content,
            source_url=hit.source_url,
        )
        for index, hit in enumerate(hits, 1)
    ]
    return QuestionResponse(
        request_id=str(uuid4()),
        mode="search_only",
        summary="AI 답변을 사용하지 않고 기준일에 유효한 원문 검색 결과를 제공합니다.",
        scope=f"기준일 {request.as_of_date.isoformat()} · 사업 단계 {request.project_stage.value}",
        sections=[
            AnswerSection(
                claim=f"관련 근거 후보: {hit.document_title} {hit.path}",
                explanation=hit.content,
                citation_ids=[f"C{index}"],
            )
            for index, hit in enumerate(hits, 1)
        ],
        checklist=[
            ChecklistItem(
                label="표시된 원문과 적용 조건을 확인하세요.",
                status="check",
                citation_ids=[citation.id for citation in citations],
            )
        ]
        if citations
        else [],
        citations=citations,
        limitations=[
            "국가법령정보 공동활용 Open API의 MVP 허용 목록만 검색했습니다.",
            "검색 결과는 법률 자문을 대체하지 않습니다.",
        ]
        + ([] if hits else ["질문을 뒷받침할 근거를 찾지 못했습니다."]),
        corpus_as_of=corpus_as_of,
    )
