import ast
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pytest

import app.application.clarification_workflow as clarification_application
from app.adapters.llamaindex_clarification_workflow import (
    CaseLoaded,
    CaseMerged,
    InterpreterFailed,
    LlamaIndexClarificationWorkflow,
    PolicySelected,
    TurnInterpreted,
    TurnStarted,
)
from app.adapters.memory_clarification_case import MemoryClarificationCaseRepository
from app.application.clarification_workflow import (
    ClarificationOwner,
    ClarificationTurnJudgment,
    ClarificationTurnOrchestrator,
    ClarificationTurnRequest,
    FactSubmission,
    RequiredFactCandidate,
)
from app.application.v2.dependencies import ClarificationWorkflowDependencies
from app.ports.clarification_case import ClarificationCaseStatus


class _FakeInterpreter:
    def __init__(
        self,
        *,
        initial: ClarificationTurnJudgment,
        continuation: ClarificationTurnJudgment | Exception | None = None,
    ) -> None:
        self.initial = initial
        self.continuation = continuation
        self.initial_calls = 0
        self.continuation_calls = 0

    async def judge_initial(self, question: str) -> ClarificationTurnJudgment:
        self.initial_calls += 1
        return self.initial

    async def extract_continuation(
        self,
        *,
        original_question: str,
        unresolved_facts: tuple[object, ...],
        user_text: str,
    ) -> ClarificationTurnJudgment:
        self.continuation_calls += 1
        if isinstance(self.continuation, Exception):
            raise self.continuation
        assert self.continuation is not None
        return self.continuation


def _candidate(index: int) -> RequiredFactCandidate:
    return RequiredFactCandidate(
        label=f"사실 {index}",
        why_needed=f"판단에 필요한 사실 {index}",
        blocking=True,
        group="사업 정보",
    )


def _initial(*candidates: RequiredFactCandidate) -> ClarificationTurnJudgment:
    return ClarificationTurnJudgment(
        intent="provide_facts", submitted_facts=(), required_facts=tuple(candidates)
    )


def _workflow(interpreter: _FakeInterpreter) -> LlamaIndexClarificationWorkflow:
    now = datetime(2026, 9, 3, tzinfo=UTC)
    return LlamaIndexClarificationWorkflow(
        ClarificationWorkflowDependencies(
            repository=MemoryClarificationCaseRepository(now=lambda: now),
            initial_judge=interpreter,
            continuation_extractor=interpreter,
            now=lambda: now,
            case_ttl=timedelta(days=1),
        )
    )


def _request(*, case_id=None, user_text: str | None = None) -> ClarificationTurnRequest:
    return ClarificationTurnRequest(
        question="태양광 발전 사업의 허가 요건은 무엇인가요?",
        as_of_date=date(2026, 9, 3),
        project_stage="planning",
        case_id=case_id,
        user_text=user_text,
    )


def _owner() -> ClarificationOwner:
    return ClarificationOwner(owner_scope="user:owner", capability_hash=None)


def test_application_layer_does_not_import_llamaindex_workflow_sdk() -> None:
    application_dir = Path(clarification_application.__file__).parent
    imports: list[str] = []
    for source_file in application_dir.rglob("*.py"):
        for node in ast.walk(ast.parse(source_file.read_text(encoding="utf-8"))):
            if isinstance(node, ast.ImportFrom):
                imports.append(node.module or "")
            elif isinstance(node, ast.Import):
                imports.extend(alias.name for alias in node.names)

    assert all(not module.startswith("llama_index") for module in imports)


def test_llamaindex_adapter_implements_application_orchestrator_protocol() -> None:
    workflow = _workflow(_FakeInterpreter(initial=_initial(_candidate(1))))

    assert isinstance(workflow, ClarificationTurnOrchestrator)


def test_workflow_events_do_not_carry_private_case_or_fact_payloads() -> None:
    event_fields = {
        event.__name__: set(event.model_fields)
        for event in (
            TurnStarted,
            CaseLoaded,
            TurnInterpreted,
            InterpreterFailed,
            CaseMerged,
            PolicySelected,
        )
    }

    assert event_fields == {
        "TurnStarted": {"request_id"},
        "CaseLoaded": {"request_id"},
        "TurnInterpreted": {"request_id"},
        "InterpreterFailed": {"request_id"},
        "CaseMerged": {"request_id"},
        "PolicySelected": {"request_id", "policy"},
    }


@pytest.mark.asyncio
async def test_initial_turn_formats_every_blocking_fact() -> None:
    interpreter = _FakeInterpreter(initial=_initial(*(_candidate(index) for index in range(1, 4))))
    workflow = _workflow(interpreter)

    outcome = await workflow.run_turn(_request(), _owner())

    assert outcome.policy == "interim"
    assert outcome.case is not None
    assert tuple(fact.id for fact in outcome.question_format.facts) == (
        "fact-1",
        "fact-2",
        "fact-3",
    )
    assert all(fact.blocking for fact in outcome.question_format.facts)
    assert outcome.case.version == 0
    assert outcome.next_status is ClarificationCaseStatus.WAITING_FOR_USER
    assert interpreter.initial_calls == 1
    assert interpreter.continuation_calls == 0


@pytest.mark.asyncio
async def test_candidate_persistence_rejects_blank_reason_and_normalizes_blank_group() -> None:
    interpreter = _FakeInterpreter(
        initial=_initial(
            RequiredFactCandidate(
                label="무효 후보", why_needed=" \t", blocking=True, group="사업 정보"
            ),
            RequiredFactCandidate(
                label="유효 후보", why_needed="적용 요건을 가릅니다.", blocking=True, group=" \n"
            ),
        )
    )

    outcome = await _workflow(interpreter).run_turn(_request(), _owner())

    assert outcome.case is not None
    assert tuple(fact.id for fact in outcome.case.case.required_facts) == ("fact-1",)
    assert outcome.case.case.required_facts[0].label == "유효 후보"
    assert outcome.case.case.required_facts[0].group == "기본 정보"


@pytest.mark.asyncio
async def test_continuation_removes_answered_and_declined_facts_from_question_format() -> None:
    interpreter = _FakeInterpreter(
        initial=_initial(*(_candidate(index) for index in range(1, 4))),
        continuation=ClarificationTurnJudgment(
            intent="provide_facts",
            submitted_facts=(
                FactSubmission("fact-1", "answered", "100kW"),
                FactSubmission("fact-2", "declined", None),
            ),
            required_facts=(),
        ),
    )
    workflow = _workflow(interpreter)
    initial = await workflow.run_turn(_request(), _owner())
    assert initial.case is not None

    outcome = await workflow.run_turn(
        _request(
            case_id=initial.case.case_id, user_text="용량은 100kW이고 위치는 말하기 어렵습니다."
        ),
        _owner(),
    )

    assert outcome.case is not None
    assert outcome.case.case_id == initial.case.case_id
    assert outcome.case.status is ClarificationCaseStatus.WAITING_FOR_USER
    assert outcome.case.version == 1
    assert outcome.next_status is ClarificationCaseStatus.WAITING_FOR_USER
    assert tuple(fact.id for fact in outcome.question_format.facts) == ("fact-3",)
    assert outcome.policy == "interim"
    assert interpreter.initial_calls == 1
    assert interpreter.continuation_calls == 1


@pytest.mark.asyncio
async def test_six_remaining_facts_expose_a_three_to_five_fact_group() -> None:
    interpreter = _FakeInterpreter(initial=_initial(*(_candidate(index) for index in range(1, 7))))

    outcome = await _workflow(interpreter).run_turn(_request(), _owner())

    assert outcome.case is not None
    assert 3 <= len(outcome.question_format.facts) <= 5
    assert {fact.id for fact in outcome.question_format.facts} <= {
        f"fact-{index}" for index in range(1, 7)
    }


@pytest.mark.asyncio
async def test_free_conversation_keeps_the_same_waiting_case() -> None:
    interpreter = _FakeInterpreter(
        initial=_initial(_candidate(1)),
        continuation=ClarificationTurnJudgment(
            intent="ask_about_case", submitted_facts=(), required_facts=()
        ),
    )
    workflow = _workflow(interpreter)
    initial = await workflow.run_turn(_request(), _owner())
    assert initial.case is not None

    outcome = await workflow.run_turn(
        _request(case_id=initial.case.case_id, user_text="그 사실이 왜 필요한가요?"), _owner()
    )

    assert outcome.case is not None
    assert outcome.case.case_id == initial.case.case_id
    assert outcome.case.status is ClarificationCaseStatus.WAITING_FOR_USER
    assert tuple(fact.id for fact in outcome.question_format.facts) == ("fact-1",)


@pytest.mark.asyncio
async def test_answered_blocking_facts_complete_the_case_with_full_policy() -> None:
    interpreter = _FakeInterpreter(
        initial=_initial(_candidate(1)),
        continuation=ClarificationTurnJudgment(
            intent="provide_facts",
            submitted_facts=(FactSubmission("fact-1", "answered", "100kW"),),
        ),
    )
    workflow = _workflow(interpreter)
    initial = await workflow.run_turn(_request(), _owner())
    assert initial.case is not None

    outcome = await workflow.run_turn(
        _request(case_id=initial.case.case_id, user_text="100kW입니다."), _owner()
    )

    assert outcome.case is not None
    assert outcome.policy == "full"
    assert outcome.case.status is ClarificationCaseStatus.WAITING_FOR_USER
    assert outcome.next_status is ClarificationCaseStatus.COMPLETED
    assert outcome.question_format.facts == ()


@pytest.mark.asyncio
async def test_explicit_answer_request_completes_case_with_conditional_policy() -> None:
    interpreter = _FakeInterpreter(
        initial=_initial(_candidate(1)),
        continuation=ClarificationTurnJudgment(
            intent="request_answer_now", submitted_facts=(), required_facts=()
        ),
    )
    workflow = _workflow(interpreter)
    initial = await workflow.run_turn(_request(), _owner())
    assert initial.case is not None

    outcome = await workflow.run_turn(
        _request(case_id=initial.case.case_id, user_text="현재 정보로 답해주세요."), _owner()
    )

    assert outcome.case is not None
    assert outcome.policy == "conditional"
    assert outcome.case.status is ClarificationCaseStatus.WAITING_FOR_USER
    assert outcome.next_status is ClarificationCaseStatus.COMPLETED
    assert outcome.question_format.facts == ()


@pytest.mark.asyncio
async def test_provider_failure_returns_safe_outcome_without_case_mutation() -> None:
    interpreter = _FakeInterpreter(
        initial=_initial(_candidate(1)),
        continuation=RuntimeError("user fact must not escape provider failure"),
    )
    workflow = _workflow(interpreter)
    initial = await workflow.run_turn(_request(), _owner())
    assert initial.case is not None

    outcome = await workflow.run_turn(
        _request(case_id=initial.case.case_id, user_text="민감한 사실"), _owner()
    )

    assert outcome.case == initial.case
    assert outcome.error_code == "clarification_interpreter_unavailable"
    assert "user fact" not in outcome.error_code
