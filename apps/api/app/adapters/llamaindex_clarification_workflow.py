"""LlamaIndex implementation of the clarification orchestration boundary."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import uuid4

from llama_index.core.workflow import Context, Event, StartEvent, StopEvent, Workflow, step

from app.application.clarification_workflow import (
    AnswerPolicy,
    ClarificationOutcome,
    ClarificationOwner,
    ClarificationQuestionFormat,
    ClarificationTurnJudgment,
    ClarificationTurnRequest,
    canonicalize_required_facts,
    merge_submitted_facts,
)
from app.application.v2.dependencies import ClarificationWorkflowDependencies
from app.domain.clarification import ClarificationCase, group_remaining_facts
from app.ports.clarification_case import ClarificationCaseRecord, ClarificationCaseStatus


@dataclass
class _TurnState:
    """Private data for one invocation; never serialized into workflow events."""

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


class LlamaIndexClarificationWorkflow(Workflow):
    """Adapter that realizes the application orchestrator with LlamaIndex steps."""

    def __init__(self, dependencies: ClarificationWorkflowDependencies) -> None:
        super().__init__()
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
                state.judgment = await self._dependencies.initial_judge.judge_initial(
                    state.request.question
                )
            else:
                extractor = self._dependencies.continuation_extractor
                state.judgment = await extractor.extract_continuation(
                    original_question=state.record.original_question,
                    unresolved_facts=state.record.case.remaining_facts(),
                    user_text=state.request.user_text or state.request.question,
                )
        except Exception:
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
                case=ClarificationCase(canonicalize_required_facts(judgment.required_facts)),
                expires_at=self._dependencies.now() + self._dependencies.case_ttl,
            )
        elif judgment.intent not in {"cancel_case", "start_new_question"}:
            state.record = await self._dependencies.repository.merge(
                state.record.case_id,
                state.owner.owner_scope,
                expected_version=state.record.version,
                case=merge_submitted_facts(state.record.case, judgment.submitted_facts),
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
