"""Ports and policy values for the v1 question-answering use case."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol

from law_rag_core.ports.repository import LegalRepository

from app.domain.routing import RouteDecision
from app.domain.schemas import MockUser, QuestionRequest, QuestionResponse, SearchHit
from app.domain.search_queries import SearchTrace


class QueryEmbeddingCapability(Protocol):
    """Declare whether this retrieval path needs an application query vector."""

    def requires_application_query_embedding(self) -> bool: ...


class V1AnsweringError(RuntimeError):
    """An application failure that the v1 HTTP router renders for clients."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class V1AnswerDependencies:
    """Injected collaborators for one v1 answer execution."""

    search_only_enabled: bool
    embedding_enabled: bool
    answer_evidence_max_characters: int
    route_classifier_timeout_seconds: float
    question_embedding_timeout_seconds: float
    retrieval_timeout_seconds: float
    answer_timeout_seconds: float
    ai_available: Callable[[], bool]
    ai_unavailable_reason: Callable[[], str | None]
    initial_fallback_reason: Callable[[QuestionRequest], Any]
    check_quota: Callable[[str, MockUser | None], Awaitable[None]]
    require_supported_date: Callable[[Any, LegalRepository], Awaitable[None]]
    route: Callable[[str], Awaitable[RouteDecision]]
    query_embedding_capability: QueryEmbeddingCapability
    embed: Callable[[list[str]], Awaitable[list[list[float]]]]
    retrieve_evidence: Callable[
        [QuestionRequest, list[float] | None, LegalRepository],
        Awaitable[tuple[list[SearchHit], SearchTrace, datetime | None]],
    ]
    answer: Callable[[QuestionRequest, list[SearchHit]], Awaitable[Any]]
    answer_blocked_route: Callable[[QuestionRequest, str, str | None], Awaitable[Any]]
    select_generation_hits: Callable[[list[SearchHit], int], list[SearchHit]]
    validate_draft: Callable[[Any, list[SearchHit]], bool]
    save_response: Callable[
        [MockUser | None, QuestionRequest, QuestionResponse, dict[str, object]],
        Awaitable[QuestionResponse],
    ]
    mark_ai_quota_exhausted: Callable[[], None]
