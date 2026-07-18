from uuid import uuid4

from app.domain.provision_queries import parse_provision_references
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
    provision_query = parse_provision_references(request.question)
    no_results_reason = (
        "requested_path_not_found" if provision_query is not None else "no_matching_evidence"
    )
    if provision_query is None:
        no_results_message = (
            "질문을 뒷받침할 근거를 찾지 못했습니다. "
            "원인: 질문과 일치하는 근거가 기준일에 유효한 MVP 법령에 없습니다."
        )
    elif provision_query.invalid_reason == "descending_range":
        no_results_message = (
            "질문을 뒷받침할 근거를 찾지 못했습니다. "
            "원인: 조문 범위의 시작 조가 끝 조보다 큽니다. 범위를 오름차순으로 입력해 주세요."
        )
    elif provision_query.invalid_reason == "range_too_wide":
        no_results_message = (
            "질문을 뒷받침할 근거를 찾지 못했습니다. "
            "원인: 한 번에 조회할 수 있는 조문 범위는 20개 조까지입니다. 범위를 나눠 입력해 주세요."
        )
    elif provision_query.unrecognized_document_title:
        no_results_message = (
            "질문을 뒷받침할 근거를 찾지 못했습니다. "
            f"원인: 입력한 법령명({provision_query.unrecognized_document_title})을 "
            "MVP 대상 법령에서 확인하지 못했습니다. 법령명을 다시 확인해 주세요."
        )
    elif provision_query.document_title:
        requested_paths = ", ".join(item.path for item in provision_query.references)
        no_results_message = (
            "질문을 뒷받침할 근거를 찾지 못했습니다. "
            f"원인: {provision_query.document_title}에서 요청한 조문 경로({requested_paths})를 "
            "기준일 현재 찾지 못했습니다. 요청 경로와 상위 조문은 같은 근거가 아니므로 "
            "상위 조문을 정확한 검색 결과로 대신 제시하지 않았습니다. "
            "해당 조 본문이나 인접 조문을 별도로 확인해 주세요."
        )
    else:
        requested_paths = ", ".join(item.path for item in provision_query.references)
        no_results_message = (
            "질문을 뒷받침할 근거를 찾지 못했습니다. "
            f"원인: 기준일에 유효한 MVP 대상 법령 전체에서 요청한 조문 경로"
            f"({requested_paths})를 찾지 못했습니다."
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
    evidence_count = len(citations)
    evidence_summary = (
        f"질문과 관련된 기준일 유효 근거 {evidence_count}건을 찾았습니다. "
        "아래 원문과 확인 항목을 제공합니다."
    )
    return QuestionResponse(
        request_id=str(uuid4()),
        mode="search_only",
        summary=(evidence_summary if hits else f"검색 결과가 없습니다. {no_results_message}"),
        scope=(
            f"기준일 {request.as_of_date.isoformat()} · 사업 단계 "
            f"{request.project_stage.value} · 검색된 근거 {evidence_count}건"
        ),
        sections=[
            AnswerSection(
                claim=" · ".join(
                    part for part in (hit.document_title, hit.path, hit.heading) if part
                ),
                explanation=hit.content,
                citation_ids=[f"C{index}"],
            )
            for index, hit in enumerate(hits, 1)
        ],
        checklist=[
            ChecklistItem(
                label=(
                    f"{hit.document_title} {hit.path} 원문에서 적용 주체, 요건과 예외를 "
                    "현재 사업 사실관계에 대조하세요."
                ),
                status="check",
                citation_ids=[f"C{index}"],
            )
            for index, hit in enumerate(hits, 1)
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
