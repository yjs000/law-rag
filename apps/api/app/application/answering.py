from uuid import uuid4

from app.domain.provision_queries import parse_provision_reference
from app.domain.schemas import (
    AiFallbackReason,
    AnswerSection,
    ChecklistItem,
    Citation,
    QuestionRequest,
    QuestionResponse,
    SearchHit,
)


def search_only_answer(
    request: QuestionRequest,
    hits: list[SearchHit],
    corpus_as_of=None,
    *,
    fallback_reason: AiFallbackReason | None = None,
) -> QuestionResponse:
    reference = parse_provision_reference(request.question)
    no_results_reason = (
        "requested_path_not_found" if reference is not None else "no_matching_evidence"
    )
    no_results_message = (
        "질문을 뒷받침할 근거를 찾지 못했습니다. "
        f"원인: 요청한 조문 경로({reference.path})가 기준일에 유효한 MVP 법령에 없습니다."
        if reference is not None
        else "질문을 뒷받침할 근거를 찾지 못했습니다. "
        "원인: 질문과 일치하는 근거가 기준일에 유효한 MVP 법령에 없습니다."
    )
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
        summary=(
            "AI 답변을 사용하지 않고 기준일에 유효한 원문 검색 결과를 제공합니다."
            if hits
            else f"검색 결과가 없습니다. {no_results_message}"
        ),
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
            "이 서비스는 법률 자문을 대체하지 않습니다.",
        ]
        + ([] if hits else [no_results_message]),
        corpus_as_of=corpus_as_of,
        result_status="results" if hits else "no_results",
        no_results_reason=None if hits else no_results_reason,
        requested_answer_mode=request.answer_mode,
        fallback_reason=fallback_reason,
    )
