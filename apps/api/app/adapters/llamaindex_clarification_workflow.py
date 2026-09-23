"""LlamaIndex implementation of the clarification orchestration boundary."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import uuid4

from llama_index.core.workflow import Context, Event, StartEvent, StopEvent, Workflow, step
from workflows.context.serializers import PickleSerializer

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

    async def run_turn(
        self, request: ClarificationTurnRequest, owner: ClarificationOwner
    ) -> ClarificationOutcome:
        request_id = str(uuid4())
        # The workflow runtime snapshots Context state in memory before starting.
        # Only trusted, locally created turn objects enter this per-run serializer.
        ctx = Context(self, serializer=PickleSerializer())
        await ctx.store.set("turn_state", _TurnState(request=request, owner=owner))
        return await self.run(ctx=ctx, start_event=TurnStarted(request_id=request_id))

    @step
    async def load_case(self, ctx: Context, event: TurnStarted) -> CaseLoaded:
        state: _TurnState = await ctx.store.get("turn_state")
        if state.request.case_id is not None:
            state.record = await self._dependencies.repository.get_owned(
                state.request.case_id,
                state.owner.owner_scope,
                capability_hash=state.owner.capability_hash,
            )
        return CaseLoaded(request_id=event.request_id)

    @step
    async def interpret_turn(
        self, ctx: Context, event: CaseLoaded
    ) -> TurnInterpreted | InterpreterFailed:
        state: _TurnState = await ctx.store.get("turn_state")
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
    async def safe_provider_failure(self, ctx: Context, event: InterpreterFailed) -> StopEvent:
        state: _TurnState = await ctx.store.get("turn_state")
        record = state.record
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
        state: _TurnState = await ctx.store.get("turn_state")
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
        return CaseMerged(request_id=event.request_id)

    @step
    async def select_policy(self, ctx: Context, event: CaseMerged) -> PolicySelected:
        state: _TurnState = await ctx.store.get("turn_state")
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
        return PolicySelected(request_id=event.request_id, policy=policy)

    @step
    async def format_questions(self, ctx: Context, event: PolicySelected) -> StopEvent:
        state: _TurnState = await ctx.store.get("turn_state")
        record = state.record
        if record is None:
            raise RuntimeError("clarification case is unavailable")
        next_status = (
            None
            if record.status is ClarificationCaseStatus.CANCELLED
            else (
                ClarificationCaseStatus.WAITING_FOR_USER
                if event.policy == "interim"
                else ClarificationCaseStatus.COMPLETED
            )
        )
        facts = (
            group_remaining_facts(record.case.remaining_facts())
            if next_status is ClarificationCaseStatus.WAITING_FOR_USER
            else ()
        )
        return StopEvent(
            result=ClarificationOutcome(
                case=record,
                policy=event.policy,
                question_format=ClarificationQuestionFormat(facts),
                next_status=next_status,
            )
        )
