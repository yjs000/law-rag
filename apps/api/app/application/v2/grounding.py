"""SDK-independent grounding predicates and safe v2 fallback construction."""

from __future__ import annotations

import re
from typing import Any

from app.domain.grounding import CitationRegistry, GroundedSentence
from app.domain.schemas import Citation, QuestionRequest, QuestionResponse


def response_is_grounded(response: QuestionResponse, registry: CitationRegistry) -> bool:
    """Require every published legal claim to be supported by its citation IDs."""

    if not response.citations:
        return not response.sections and not response.checklist
    all_citations = tuple(citation.id for citation in response.citations)
    if not text_is_grounded(response.summary, all_citations, registry):
        return False
    for section in response.sections:
        citation_ids = tuple(section.citation_ids)
        if not text_is_grounded(section.claim, citation_ids, registry):
            return False
        if not text_is_grounded(section.explanation, citation_ids, registry):
            return False
    return all(
        text_is_grounded(item.label, tuple(item.citation_ids), registry)
        for item in response.checklist
    )


def core_is_grounded(core: Any, registry: CitationRegistry) -> bool:
    """Allow an empty-citation core only for the explicit no-answer outcome."""

    if not core.citation_ids:
        return not registry.citations or core.action == "unanswerable"
    return text_is_grounded(core.summary, tuple(core.citation_ids), registry)


def text_is_grounded(text: str, citation_ids: tuple[str, ...], registry: CitationRegistry) -> bool:
    """Verify every sentence independently so no unchecked claim leaks into SSE."""

    sentences = tuple(part.strip() for part in re.split(r"(?<=[.!?])\s+", text) if part.strip())
    return bool(sentences) and all(
        registry.verify(GroundedSentence(sentence, citation_ids)) for sentence in sentences
    )


def grounding_fallback(payload: QuestionRequest) -> QuestionResponse:
    """Return the legal-claim-free result used after all repair paths fail."""

    return QuestionResponse(
        request_id=str(payload.client_request_id),
        mode="ai",
        summary="검증된 법률 주장을 만들지 못했습니다. 인용된 공식 원문을 직접 확인해 주세요.",
        scope="근거 검증 실패",
        sections=[],
        checklist=[],
        citations=[],
        limitations=["이 서비스는 법률 자문을 대체하지 않습니다."],
        result_status="no_results",
        requested_answer_mode=payload.answer_mode,
        action="unanswerable",
        route="legal_search",
    )


def core_degraded_response(
    payload: QuestionRequest, core: Any | None, private_payload: Any
) -> QuestionResponse:
    """Keep the verified core when detail validation or generation fails."""

    if core is None:
        return grounding_fallback(payload)
    raw_citations = private_payload.get("verified_core_citations", [])
    citations = [Citation.model_validate(item) for item in raw_citations if isinstance(item, dict)]
    return QuestionResponse(
        request_id=str(payload.client_request_id),
        mode="ai",
        summary=core.summary,
        scope="상세 설명 검증 실패",
        sections=[],
        checklist=[],
        citations=citations,
        limitations=["검증된 요약만 제공합니다.", "이 서비스는 법률 자문을 대체하지 않습니다."],
        requested_answer_mode=payload.answer_mode,
        action=core.action,
        route="legal_search",
    )
