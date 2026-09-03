"""SDK-independent grounding predicates and safe v2 fallback construction."""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any, Literal

from app.domain.clarification import (
    ClarificationCase,
    FactStatus,
    GroundedClaim,
    RequiredFact,
    validate_claim,
)
from app.domain.grounding import CitationRegistry, GroundedSentence
from app.domain.schemas import Citation, QuestionRequest, QuestionResponse


@dataclass(frozen=True)
class ClarificationGrounding:
    """The policy and private case state frozen with one v2 execution.

    Only identifiers, blocking flags, and statuses are serialized into the
    execution.  Fact values remain owned by ``clarification_cases`` and are
    never copied into an SSE payload or execution record.
    """

    policy: Literal["interim", "full", "conditional"]
    case: ClarificationCase

    def to_payload(self) -> dict[str, object]:
        return {
            "policy": self.policy,
            "facts": [
                {"id": fact.id, "blocking": fact.blocking, "status": fact.status.value}
                for fact in self.case.required_facts
            ],
        }

    @classmethod
    def from_payload(cls, payload: object) -> ClarificationGrounding:
        if not isinstance(payload, dict):
            raise ValueError("clarification grounding payload is invalid")
        policy = payload.get("policy")
        raw_facts = payload.get("facts")
        if policy not in {"interim", "full", "conditional"} or not isinstance(raw_facts, list):
            raise ValueError("clarification grounding payload is incomplete")
        facts: list[RequiredFact] = []
        for priority, raw_fact in enumerate(raw_facts):
            if not isinstance(raw_fact, dict):
                raise ValueError("clarification grounding fact is invalid")
            identifier = raw_fact.get("id")
            status = raw_fact.get("status")
            blocking = raw_fact.get("blocking")
            if (
                not isinstance(identifier, str)
                or not identifier
                or not isinstance(status, str)
                or not isinstance(blocking, bool)
            ):
                raise ValueError("clarification grounding fact is incomplete")
            try:
                fact_status = FactStatus(status)
            except ValueError as exc:
                raise ValueError("clarification grounding fact has an unknown status") from exc
            facts.append(
                RequiredFact(
                    id=identifier,
                    label=identifier,
                    why_needed="frozen clarification fact",
                    blocking=blocking,
                    group="frozen",
                    priority=priority,
                    status=fact_status,
                )
            )
        return cls(policy=policy, case=ClarificationCase(tuple(facts)))


def claims_are_grounded(
    claims: Iterable[GroundedClaim], grounding: ClarificationGrounding, registry: CitationRegistry
) -> bool:
    """Validate F-006 claims by structure, frozen IDs, and fact state only.

    Deliberately do not inspect generated wording or match phrases against the
    citation quote.  ``validate_claim`` is the single claim-kind rule and the
    policy check only determines whether a declared full answer is possible.
    """

    if grounding.policy == "full" and not grounding.case.all_blocking_facts_answered():
        return False
    return all(validate_claim(claim, grounding.case, registry) for claim in claims)


def clarification_grounding_from_payload(payload: object) -> ClarificationGrounding | None:
    if not isinstance(payload, dict) or "clarification_grounding" not in payload:
        return None
    return ClarificationGrounding.from_payload(payload["clarification_grounding"])


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
