"""Request-scoped orchestration for clarification conversations.

The workflow keeps durable case state in ``ClarificationCaseRepository``.  A
LlamaIndex ``Context`` is used only for a request id and a case id; it never
contains question text, fact values, or a case snapshot.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, replace
from datetime import date
from typing import Literal
from uuid import UUID, uuid4

from llama_index.core.workflow import Context, Event, StartEvent, StopEvent, Workflow, step
from pydantic import BaseModel, ConfigDict, Field, JsonValue

from app.application.v2.dependencies import ClarificationWorkflowDependencies
from app.domain.clarification import (
    ClarificationCase,
    FactStatus,
    RequiredFact,
    group_remaining_facts,
)
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
    """Structured provider output consumed by the orchestration boundary."""

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
    error_code: str | None = None


@dataclass
class _TurnState:
    """Ephemeral private data for a single in-flight workflow invocation."""

    request: ClarificationTurnRequest
    owner: ClarificationOwner
    record: ClarificationCaseRecord | None = None
    judgment: ClarificationTurnJudgment | None = None


class TurnStarted(StartEvent):
    request_id: str


class CaseLoaded(Event):
    request_id: str


class TurnInterpreted(Event):
    request_id: str


class InterpreterFailed(Event):
    request_id: str


class CaseMerged(Event):
    request_id: str


class PolicySelected(Event):
    request_id: str
    policy: AnswerPolicy


class ClarificationWorkflow(Workflow):
    """Load, interpret, merge, decide, and format one clarification turn."""

    def __init__(
        self,
        dependencies: ClarificationWorkflowDependencies | None = None,
        *,
        repository: object | None = None,
        interpreter: object | None = None,
        now: object | None = None,
        case_ttl: object | None = None,
    ) -> None:
        super().__init__()
        if dependencies is None:
            if repository is None or interpreter is None or now is None or case_ttl is None:
                raise ValueError("clarification workflow dependencies are required")
            dependencies = ClarificationWorkflowDependencies(
                repository=repository,  # type: ignore[arg-type]
                interpreter=interpreter,
                now=now,  # type: ignore[arg-type]
                case_ttl=case_ttl,  # type: ignore[arg-type]
            )
        self._dependencies = dependencies
        self._turns: dict[str, _TurnState] = {}

    async def run_turn(
        self, request: ClarificationTurnRequest, owner: ClarificationOwner
    ) -> ClarificationOutcome:
        request_id = str(uuid4())
        self._turns[request_id] = _TurnState(request=request, owner=owner)
        try:
            return await self.run(start_event=TurnStarted(request_id=request_id))
        finally:
            self._turns.pop(request_id, None)

    @step
    async def load_case(self, ctx: Context, event: TurnStarted) -> CaseLoaded:
        # Context is intentionally identifier-only request bookkeeping.
        state = self._state(event.request_id)
        await ctx.store.set("request_id", event.request_id)
        await ctx.store.set(
            "case_id", str(state.request.case_id) if state.request.case_id else None
        )
        if state.request.case_id is not None:
            state.record = await self._dependencies.repository.get_owned(
                state.request.case_id,
                state.owner.owner_scope,
                capability_hash=state.owner.capability_hash,
            )
        return CaseLoaded(request_id=event.request_id)

    @step
    async def interpret_turn(self, event: CaseLoaded) -> TurnInterpreted | InterpreterFailed:
        state = self._state(event.request_id)
        try:
            if state.record is None:
                state.judgment = await self._dependencies.interpreter.judge_initial(
                    state.request.question
                )
            else:
                state.judgment = await self._dependencies.interpreter.extract_continuation(
                    original_question=state.record.original_question,
                    unresolved_facts=state.record.case.remaining_facts(),
                    user_text=state.request.user_text or state.request.question,
                )
        except Exception:
            # Provider bodies may include private user values.  Do not expose them.
            return InterpreterFailed(request_id=event.request_id)
        return TurnInterpreted(request_id=event.request_id)

    @step
    async def safe_provider_failure(self, event: InterpreterFailed) -> StopEvent:
        record = self._state(event.request_id).record
        facts = record.case.remaining_facts() if record is not None else ()
        return StopEvent(
            result=ClarificationOutcome(
                case=record,
                policy="interim",
                question_format=ClarificationQuestionFormat(group_remaining_facts(facts)),
                error_code="clarification_interpreter_unavailable",
            )
        )

    @step
    async def validate_and_merge(self, ctx: Context, event: TurnInterpreted) -> CaseMerged:
        state = self._state(event.request_id)
        judgment = state.judgment
        if judgment is None:
            raise RuntimeError("clarification judgment is unavailable")
        if state.record is None:
            state.record = await self._dependencies.repository.create_or_get(
                owner_scope=state.owner.owner_scope,
                capability_hash=state.owner.capability_hash,
                original_question=state.request.question,
                as_of_date=state.request.as_of_date,
                project_stage=state.request.project_stage,
                conversation_id=state.request.conversation_id,
                case=ClarificationCase(_required_facts(judgment.required_facts)),
                expires_at=self._dependencies.now() + self._dependencies.case_ttl,
            )
        elif judgment.intent not in {"cancel_case", "start_new_question"}:
            state.record = await self._dependencies.repository.merge(
                state.record.case_id,
                state.owner.owner_scope,
                expected_version=state.record.version,
                case=_merge_submitted_facts(state.record.case, judgment.submitted_facts),
                capability_hash=state.owner.capability_hash,
            )
        if state.record is None:
            raise RuntimeError("clarification case is unavailable")
        await ctx.store.set("case_id", str(state.record.case_id))
        return CaseMerged(request_id=event.request_id)

    @step
    async def select_policy(self, event: CaseMerged) -> PolicySelected:
        state = self._state(event.request_id)
        record = state.record
        judgment = state.judgment
        if record is None or judgment is None:
            raise RuntimeError("clarification turn state is unavailable")
        if judgment.intent in {"cancel_case", "start_new_question"}:
            state.record = await self._dependencies.repository.cancel(
                record.case_id,
                state.owner.owner_scope,
                expected_version=record.version,
                capability_hash=state.owner.capability_hash,
            )
            return PolicySelected(request_id=event.request_id, policy="interim")
        if judgment.intent == "request_answer_now":
            policy: AnswerPolicy = "conditional"
        elif record.case.all_blocking_facts_answered():
            policy = "full"
        else:
            policy = "interim"
        if policy == "interim":
            state.record = await self._dependencies.repository.mark_waiting(
                record.case_id,
                state.owner.owner_scope,
                expected_version=record.version,
                capability_hash=state.owner.capability_hash,
            )
        else:
            state.record = await self._dependencies.repository.complete(
                record.case_id,
                state.owner.owner_scope,
                expected_version=record.version,
                capability_hash=state.owner.capability_hash,
            )
        return PolicySelected(request_id=event.request_id, policy=policy)

    @step
    async def format_questions(self, event: PolicySelected) -> StopEvent:
        record = self._state(event.request_id).record
        if record is None:
            raise RuntimeError("clarification case is unavailable")
        facts = (
            group_remaining_facts(record.case.remaining_facts())
            if record.status is ClarificationCaseStatus.WAITING_FOR_USER
            else ()
        )
        return StopEvent(
            result=ClarificationOutcome(
                case=record,
                policy=event.policy,
                question_format=ClarificationQuestionFormat(facts),
            )
        )

    def _state(self, request_id: str) -> _TurnState:
        try:
            return self._turns[request_id]
        except KeyError as exc:
            raise RuntimeError("clarification request is unavailable") from exc


def _required_facts(candidates: tuple[RequiredFactCandidate, ...]) -> tuple[RequiredFact, ...]:
    """Assign identifiers, status, and priority on the server boundary."""

    facts: list[RequiredFact] = []
    seen_labels: set[str] = set()
    for candidate in candidates:
        label = candidate.label.strip()
        if not label or label in seen_labels:
            continue
        seen_labels.add(label)
        facts.append(
            RequiredFact(
                id=f"fact-{len(facts) + 1}",
                label=label,
                why_needed=candidate.why_needed.strip(),
                blocking=candidate.blocking,
                group=candidate.group.strip(),
                priority=len(facts) + 1,
            )
        )
    return tuple(facts)


def _merge_submitted_facts(
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
