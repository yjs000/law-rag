"""V1 retrieval-stage helpers independent of FastAPI route registration."""

from __future__ import annotations

import time
from datetime import datetime

from law_rag_core.ports.repository import LegalRepository

from app.adapters.llamaindex_repository import LlamaIndexLegalRepository
from app.domain.embedding_profiles import NVIDIA_NEMOTRON_512_PROFILE
from app.domain.schemas import QuestionRequest, SearchHit
from app.domain.search_queries import SearchTrace


async def retrieve_question_evidence(
    payload: QuestionRequest,
    query_embedding: list[float] | None,
    repository: LegalRepository,
) -> tuple[list[SearchHit], SearchTrace, datetime | None]:
    """Retrieve evidence and the matching corpus timestamp in one stage."""

    hits, trace = await repository.search_with_trace(
        payload.question,
        payload.as_of_date,
        10,
        query_embedding,
        NVIDIA_NEMOTRON_512_PROFILE.key if query_embedding is not None else None,
    )
    return hits, trace, await repository.last_sync()


def elapsed_ms(started_at: float) -> int:
    """Return elapsed wall-clock time without consuming a budget clock."""

    return max(0, round((time.monotonic() - started_at) * 1000))


def remaining_ms(budget: object) -> int:
    """Return the remaining request budget without advancing its test clock."""

    return max(0, round((budget.deadline - time.monotonic()) * 1000))


def requires_legacy_query_embedding(repository: LegalRepository) -> bool:
    """V1 retrieval alone owns application-generated query embeddings."""

    return not isinstance(repository, LlamaIndexLegalRepository)
