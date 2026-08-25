from uuid import uuid4

from app.domain.answer_actions import derive_fallback_action
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
            source_kind=hit.source_kind,
            law_type_code=hit.law_type_code,
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
        action=derive_fallback_action(fallback_reason),
    )


_REALTIME_BLOCKED_MESSAGE = (
    "이 질문은 시점에 따라 달라지는 정보(예: 올해 예산, 현재 가격, 고장 상태)가 필요합니다.\n"
    "법령 corpus만으로는 답할 수 없으니 해당 연도·기관의 최신 공고나 담당 기관에 직접 확인해 "
    "주세요."
)
_EXTERNAL_DOCUMENT_BLOCKED_MESSAGE = (
    "이 질문은 계약서·정산서·공사비 산출서 같은 문서 확인이 필요합니다.\n"
    "법령 corpus만으로는 확정할 수 없으니 해당 문서를 직접 대조해 확인해 주세요."
)


def clarification_resubmission_summary(
    question: str, missing_fields: tuple[str, ...] | list[str]
) -> str:
    """0028 "비용 최소화 결정"의 재제출 템플릿. route_guidance_fallback(사전 라우팅)와
    post_generation_clarification_answer(생성 후 발견된 부족)가 같은 문구를 쓴다 - 사용자가
    보는 안내가 어느 단계에서 왔든 일관되게 한다.
    """
    fields_block = "\n".join(f"- {field}: [ ]" for field in missing_fields) or "- [ ]"
    return (
        "정확한 절차를 확인하려면 추가 정보가 필요합니다.\n"
        "다음 메시지에는 아래 내용을 전체 복사한 뒤 [ ]를 채워 한 번에 보내주세요.\n"
        "추가 정보만 따로 보내지 마세요.\n\n"
        f"질문: {question}\n추가 정보:\n{fields_block}"
    )


def post_generation_clarification_answer(
    request: QuestionRequest,
    missing_information: list[str],
    *,
    mode: str = "search_only",
) -> QuestionResponse:
    """2026-08-08: DraftAnswer.action == "clarification_required"일 때 쓴다 - 사전 라우팅이
    못 잡고 검색·생성까지 해본 뒤에야 드러난 clarification 케이스다. route는 그대로
    legal_search로 둔다(라우팅 판단 자체는 맞았다 - "검색해도 됐다"는 사실은 변하지 않는다.
    "생성된 답이 충분한가"는 별개 축이다).
    """
    return QuestionResponse(
        request_id=str(request.client_request_id),
        mode=mode,
        summary=clarification_resubmission_summary(request.question, missing_information),
        scope="답변 생성 중 추가 정보 필요 확인됨 (검색은 실행됨)",
        sections=[],
        checklist=[],
        citations=[],
        limitations=["이 서비스는 법률 자문을 대체하지 않습니다."],
        result_status="no_results",
        requested_answer_mode=request.answer_mode,
        route="legal_search",
        action="clarification_required",
    )


def route_guidance_fallback(
    request: QuestionRequest,
    route: str,
    *,
    missing_fields: tuple[str, ...] = (),
    explanation: str | None = None,
) -> QuestionResponse:
    """Build the deterministic AI-mode fallback for a route without evidence.

    realtime_required and external_document_required end here with a deterministic
    block message (0 embedding/search/LLM calls - see 0028 "받지 않는 두 경로").
    clarification_required ends here with the "완성 질문 재제출" template (0028 "비용
    최소화 결정"): the caller resends the original question plus the missing facts in one
    message; the server never auto-merges turns.

    The fallback never presents a search-only response: route guidance is an AI-mode
    response even when the optional guidance generation cannot run.
    """
    if route == "routing_unavailable":
        summary = (
            "질문 분류를 일시적으로 처리할 수 없습니다. 법령 검색을 시작하지 않았습니다. "
            "잠시 후 다시 시도해 주세요."
        )
        action = "unanswerable"
    elif route == "realtime_required":
        summary = _REALTIME_BLOCKED_MESSAGE
        if explanation:
            summary += f"\n\n(참고: {explanation})"
        action = "unanswerable"
    elif route == "external_document_required":
        summary = _EXTERNAL_DOCUMENT_BLOCKED_MESSAGE
        if explanation:
            summary += f"\n\n(참고: {explanation})"
        action = "unanswerable"
    elif route == "clarification_required":
        summary = clarification_resubmission_summary(request.question, missing_fields)
        action = "clarification_required"
    else:
        raise ValueError(f"route_guidance_fallback does not handle route={route!r}")
    return QuestionResponse(
        request_id=str(request.client_request_id),
        mode="ai",
        summary=summary,
        scope=f"라우팅: {route} (검색 미실행)",
        sections=[],
        checklist=[],
        citations=[],
        limitations=["이 서비스는 법률 자문을 대체하지 않습니다."],
        result_status="no_results",
        requested_answer_mode=request.answer_mode,
        route=route,  # type: ignore[arg-type]
        action=action,
    )
