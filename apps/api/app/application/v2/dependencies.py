"""Explicit ports used by the v2 question-execution use case."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Literal, Protocol
from uuid import UUID

from law_rag_core.ports.repository import LegalRepository

from app.application.question_phase_coordinator import PhaseResult
from app.domain.schemas import MockUser, QuestionRequest, QuestionResponse, SearchHit
from app.ports.clarification_case import ClarificationCaseRepository
from app.ports.question_execution import QuestionExecutionRecord, QuestionExecutionRepository


class ActiveGeneration(Protocol):
    """The frozen generation and index used for one prepare operation."""

    generation: Any
    index: Any


class ActiveGenerationProvider(Protocol):
    """Port for resolving the current generation once at prepare time."""

    async def active(self) -> ActiveGeneration: ...


class PhaseLease(Protocol):
    """A provider-capacity lease whose owner performs its own cleanup."""

    async def release(self) -> None: ...


@dataclass(frozen=True)
class V2ExecutionDependencies:
    """All collaborator ports for a single v2 service instance.

    The composition root supplies adapters.  This module intentionally uses no
    FastAPI, SQLAlchemy, LlamaIndex, or NVIDIA SDK types.
    """

    executions: QuestionExecutionRepository
    resolve_repository: Callable[[], Awaitable[LegalRepository]]
    active_provider: Callable[[], ActiveGenerationProvider]
    retrieve_evidence: Callable[
        [QuestionRequest, ActiveGeneration, LegalRepository],
        Awaitable[tuple[list[SearchHit], datetime | None]],
    ]
    route: Callable[[str], Awaitable[Any]]
    answerer: Callable[[], Any]
    ai_available: Callable[[], bool]
    check_quota: Callable[[str, MockUser | None], Awaitable[None]]
    require_supported_date: Callable[[Any, LegalRepository], Awaitable[None]]
    save_authenticated: Callable[
        [MockUser | None, QuestionRequest, QuestionResponse], Awaitable[QuestionResponse]
    ]
    select_generation_hits: Callable[[list[SearchHit], int], list[SearchHit]]
    validate_core: Callable[[Any, list[SearchHit]], bool]
    validate_response: Callable[[Any, list[SearchHit]], bool]
    make_core_draft: Callable[[str, list[str], str], Any]
    answer_evidence_max_characters: int
    phase_timeout: timedelta
    now: Callable[[], datetime]
    execution_capability: Callable[[str, str], str]
    capability_hash: Callable[[str | None], str | None]
    admit_phase: Callable[
        [QuestionExecutionRecord, Literal["core", "finalize"]], Awaitable[PhaseLease | None]
    ]
    run_core: Callable[[QuestionExecutionRecord], Awaitable[PhaseResult]]
    run_finalize: Callable[[QuestionExecutionRecord, MockUser | None], Awaitable[PhaseResult]]


@dataclass(frozen=True)
class ClarificationWorkflowDependencies:
    """SDK-free collaborators for one clarification workflow instance."""

    repository: ClarificationCaseRepository
    interpreter: Any
    now: Callable[[], datetime]
    case_ttl: timedelta


@dataclass(frozen=True)
class PrepareQuestion:
    """Validated transport input needed to create or replay an execution."""

    payload: QuestionRequest
    owner_scope: str
    idempotency_key: str
    user: MockUser | None


@dataclass(frozen=True)
class PreparedExecution:
    """Prepared execution plus the anonymous replay capability, if any."""

    execution: QuestionExecutionRecord
    execution_capability: str | None


@dataclass(frozen=True)
class PhaseRequest:
    """Validated transport ownership input for a core or finalize phase."""

    execution_id: UUID
    owner_scope: str
    capability_hash: str | None
    user: MockUser | None
