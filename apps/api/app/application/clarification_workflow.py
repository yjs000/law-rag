"""SDK-free contracts and state transforms for clarification conversations."""

from __future__ import annotations

import json
from dataclasses import dataclass, replace
from datetime import date
from typing import Literal, Protocol, runtime_checkable
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, JsonValue

from app.domain.clarification import ClarificationCase, FactStatus, RequiredFact
from app.ports.clarification_case import ClarificationCaseRecord, ClarificationCaseStatus

ClarificationIntent = Literal[
    "provide_facts",
    "ask_about_case",
    "request_answer_now",
    "cancel_case",
    "start_new_question",
    "ambiguous",
]
AnswerPolicy = Literal["interim", "full", "conditional"]


class RequiredFactCandidate(BaseModel):
    """A provider proposal, normalized by the server before it becomes state."""

    model_config = ConfigDict(frozen=True)

    label: str = Field(min_length=1, max_length=120)
    why_needed: str = Field(min_length=1, max_length=300)
    blocking: bool = True
    group: str = Field(default="기본 정보", min_length=1, max_length=80)


class FactSubmission(BaseModel):
    """A candidate update for an already server-assigned fact id."""

    model_config = ConfigDict(frozen=True)

    fact_id: str = Field(min_length=1, max_length=80)
    status: Literal["answered", "declined"]
    value: JsonValue | None = None

    def __init__(
        self,
        fact_id: str | None = None,
        status: Literal["answered", "declined"] | None = None,
        value: JsonValue | None = None,
        **data: object,
    ) -> None:
        """Support concise internal construction without weakening JSON validation."""

        if fact_id is not None:
            data["fact_id"] = fact_id
        if status is not None:
            data["status"] = status
        if "value" not in data:
            data["value"] = value
        super().__init__(**data)


class ClarificationTurnJudgment(BaseModel):
    """Structured provider or transport output consumed by orchestration."""

    model_config = ConfigDict(frozen=True)

    intent: ClarificationIntent
    submitted_facts: tuple[FactSubmission, ...] = ()
    required_facts: tuple[RequiredFactCandidate, ...] = ()


@dataclass(frozen=True)
class ClarificationTurnRequest:
    question: str
    as_of_date: date
    project_stage: str
    case_id: UUID | None = None
    user_text: str | None = None
    conversation_id: UUID | None = None


@dataclass(frozen=True)
class ClarificationOwner:
    owner_scope: str
    capability_hash: str | None


@dataclass(frozen=True)
class ClarificationQuestionFormat:
    facts: tuple[RequiredFact, ...]


@dataclass(frozen=True)
class ClarificationOutcome:
    case: ClarificationCaseRecord | None
    policy: AnswerPolicy
    question_format: ClarificationQuestionFormat
    # V2 persists this transition only after it creates a grounded response.
    next_status: ClarificationCaseStatus | None = None
    error_code: str | None = None


class InitialClarificationJudge(Protocol):
    """Initial fact-candidate judgment, implemented by the configured Ultra adapter."""

    async def judge_initial(self, question: str) -> ClarificationTurnJudgment: ...


class ContinuationFactIntentExtractor(Protocol):
    """Structured continuation extraction without initial-route reasoning."""

    async def extract_continuation(
        self,
        *,
        original_question: str,
        unresolved_facts: tuple[RequiredFact, ...],
        user_text: str,
    ) -> ClarificationTurnJudgment: ...


@runtime_checkable
class ClarificationTurnOrchestrator(Protocol):
    """Application-facing orchestration boundary, independent of workflow SDKs."""

    async def run_turn(
        self, request: ClarificationTurnRequest, owner: ClarificationOwner
    ) -> ClarificationOutcome: ...


def canonicalize_required_facts(
    candidates: tuple[RequiredFactCandidate, ...],
) -> tuple[RequiredFact, ...]:
    """Assign server-owned identifiers and reject incomplete candidate metadata."""

    facts: list[RequiredFact] = []
    seen_labels: set[str] = set()
    for candidate in candidates:
        label = candidate.label.strip()
        why_needed = candidate.why_needed.strip()
        if not label or not why_needed or label in seen_labels:
            continue
        seen_labels.add(label)
        facts.append(
            RequiredFact(
                id=f"fact-{len(facts) + 1}",
                label=label,
                why_needed=why_needed,
                blocking=candidate.blocking,
                group=candidate.group.strip() or "기본 정보",
                priority=len(facts) + 1,
            )
        )
    return tuple(facts)


def merge_submitted_facts(
    case: ClarificationCase, submissions: tuple[FactSubmission, ...]
) -> ClarificationCase:
    """Apply only validated updates to known, server-assigned fact ids."""

    by_id = {submission.fact_id: submission for submission in submissions}
    merged: list[RequiredFact] = []
    for fact in case.required_facts:
        submission = by_id.get(fact.id)
        if submission is None:
            merged.append(fact)
        elif submission.status == "declined":
            merged.append(replace(fact, status=FactStatus.DECLINED, value=None))
        elif _is_json_value(submission.value):
            merged.append(replace(fact, status=FactStatus.ANSWERED, value=submission.value))
        else:
            merged.append(replace(fact, status=FactStatus.INVALID, value=None))
    return replace(case, required_facts=tuple(merged))


def _is_json_value(value: JsonValue | None) -> bool:
    if value is None:
        return False
    try:
        json.dumps(value, allow_nan=False)
    except TypeError, ValueError:
        return False
    return True
