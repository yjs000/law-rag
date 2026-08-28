"""Frozen-evidence mapping helpers for the v2 execution flow."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from app.domain.grounding import FrozenCitation
from app.domain.schemas import Citation, QuestionRequest, SearchHit


def execution_request_and_hits(
    execution: Any,
) -> tuple[QuestionRequest, list[SearchHit], datetime | None]:
    """Read the persisted prepare payload without triggering a second retrieval."""

    payload = execution.private_payload
    request_data = payload.get("request")
    hit_data = payload.get("hits")
    if not isinstance(request_data, dict) or not isinstance(hit_data, list):
        raise ValueError("execution payload is incomplete")
    corpus_as_of = payload.get("corpus_as_of")
    return (
        QuestionRequest.model_validate(request_data),
        [SearchHit.model_validate(item) for item in hit_data if isinstance(item, dict)],
        datetime.fromisoformat(corpus_as_of) if isinstance(corpus_as_of, str) else None,
    )


def execution_generation_hits(execution: Any, hits: list[SearchHit]) -> list[SearchHit] | None:
    """Return a persisted provider-evidence subset when prepare stored one."""

    stored = execution.private_payload.get("generation_hits")
    if not isinstance(stored, list):
        return None
    return [SearchHit.model_validate(item) for item in stored if isinstance(item, dict)]


def freeze_citations(hits: list[SearchHit]) -> tuple[FrozenCitation, ...]:
    """Store only the citation ID and immutable quote used by grounding."""

    return tuple(
        FrozenCitation(id=f"C{index}", quote=hit.content) for index, hit in enumerate(hits, 1)
    )


def citations_for_hits(hits: list[SearchHit]) -> list[Citation]:
    """Present frozen provider evidence as the public citation schema."""

    return [
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
