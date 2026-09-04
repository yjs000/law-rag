from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.adapters.memory_clarification_case import MemoryClarificationCaseRepository
from app.adapters.memory_question_execution import MemoryQuestionExecutionRepository
from app.adapters.openai_answerer import ClarificationCoreDraft, ClarificationDraftAnswer, CoreDraft
from app.application.clarification_workflow import (
    ClarificationOutcome,
    ClarificationQuestionFormat,
)
from app.application.v2.dependencies import PrepareQuestion
from app.application.v2.grounding import ClarificationGrounding, claims_are_grounded
from app.application.v2.phase_service import V2QuestionExecutionService
from app.domain.clarification import ClarificationCase, FactStatus, GroundedClaim, RequiredFact
from app.domain.grounding import CitationRegistry, FrozenCitation
from app.domain.question_execution import ExecutionStatus
from app.domain.schemas import AnswerSection, QuestionRequest, SearchHit, SourceKind
from app.ports.clarification_case import ClarificationCaseStatus


def _hit() -> SearchHit:
    return SearchHit(
        provision_id=uuid4(),
        document_id=uuid4(),
        document_title="전기사업법",
        source_kind=SourceKind.LAW,
        version_label="2026-01-01",
        effective_from=date(2026, 1, 1),
        effective_to=None,
        path="제1조",
        content="전기사업자는 허가를 받아야 합니다.",
        source_url="https://www.law.go.kr/법령/전기사업법/제1조",
    )


def _context(
    policy: str,
    *,
    capacity_status: FactStatus = FactStatus.ANSWERED,
    site_status: FactStatus = FactStatus.UNANSWERED,
) -> ClarificationGrounding:
    return ClarificationGrounding(
        policy=policy,
        case=ClarificationCase(
            (
                RequiredFact(
                    id="capacity",
                    label="발전 용량",
                    why_needed="적용 범위를 판단합니다.",
                    blocking=True,
                    group="사업 정보",
                    priority=1,
                    status=capacity_status,
                    value="100kW",
                ),
                RequiredFact(
                    id="site",
                    label="설치 위치",
                    why_needed="관할을 판단합니다.",
                    blocking=True,
                    group="사업 정보",
                    priority=2,
                    status=site_status,
                ),
            )
        ),
    )


def _draft(*, claims: list[GroundedClaim]) -> ClarificationDraftAnswer:
    return ClarificationDraftAnswer(
        summary="현재 근거로 확인되는 안내입니다.",
        scope="기준일 현재",
        sections=[
            AnswerSection(
                claim="허가 요건을 확인하세요.",
                explanation="공식 원문에 허가 요건이 있습니다.",
                citation_ids=["C1"],
            )
        ],
        checklist=[{"label": "원문을 확인하세요.", "status": "check", "citation_ids": ["C1"]}],
        action="partially_answerable",
        grounded_claims=claims,
    )


def _detail_claims() -> list[GroundedClaim]:
    return [
        GroundedClaim(
            "요약의 문구는 원문과 일치할 필요가 없습니다.",
            "general_rule",
            ("C1",),
            surface="summary",
            surface_index=None,
        ),
        GroundedClaim(
            "소제목의 문구는 원문과 일치할 필요가 없습니다.",
            "general_rule",
            ("C1",),
            surface="section_claim",
            surface_index=0,
        ),
        GroundedClaim(
            "설명의 문구는 원문과 일치할 필요가 없습니다.",
            "general_rule",
            ("C1",),
            surface="section_explanation",
            surface_index=0,
        ),
        GroundedClaim(
            "체크 항목의 문구는 원문과 일치할 필요가 없습니다.",
            "general_rule",
            ("C1",),
            surface="checklist_label",
            surface_index=0,
        ),
    ]


class _CapturingAnswerer:
    def __init__(self, *, claims: list[GroundedClaim]) -> None:
        self.claims = claims
        self.core_context: ClarificationGrounding | None = None
        self.detail_context: ClarificationGrounding | None = None
        self.core_calls = 0
        self.detail_calls = 0

    async def answer_core(
        self,
        _request: QuestionRequest,
        _hits: list[SearchHit],
        *,
        clarification: ClarificationGrounding,
    ) -> CoreDraft:
        self.core_calls += 1
        self.core_context = clarification
        return ClarificationCoreDraft(
            summary="전혀 다른 표현의 일반 규칙입니다.",
            citation_ids=["C1"],
            action="partially_answerable",
            grounded_claims=self.claims,
        )

    async def answer(
        self,
        _request: QuestionRequest,
        _hits: list[SearchHit],
        *,
        clarification: ClarificationGrounding,
    ) -> ClarificationDraftAnswer:
        self.detail_calls += 1
        self.detail_context = clarification
        return _draft(claims=self.claims)


def _service(
    answerer: _CapturingAnswerer,
    *,
    clarification_cases: MemoryClarificationCaseRepository | None = None,
    ai_available: bool = True,
) -> tuple[V2QuestionExecutionService, MemoryQuestionExecutionRepository]:
    executions = MemoryQuestionExecutionRepository()
    now = datetime(2026, 9, 3, tzinfo=UTC)

    async def _resolve_repository() -> object:
        return object()

    async def _retrieve(*_args: object) -> tuple[list[SearchHit], datetime]:
        return [_hit()], now

    async def _route(_question: str) -> SimpleNamespace:
        return SimpleNamespace(route="legal_search", missing_fields=())

    async def _allow(*_args: object) -> None:
        return None

    async def _save(_user: object, _request: QuestionRequest, response: object) -> object:
        return response

    dependencies = SimpleNamespace(
        executions=executions,
        clarification_cases=clarification_cases,
        resolve_repository=_resolve_repository,
        active_provider=lambda: SimpleNamespace(
            active=lambda: _active_generation()
        ),
        retrieve_evidence=_retrieve,
        route=_route,
        answerer=lambda: answerer,
        ai_available=lambda: ai_available,
        check_quota=_allow,
        require_supported_date=_allow,
        save_authenticated=_save,
        select_generation_hits=lambda hits, _limit: hits,
        validate_core=lambda _draft, _hits: True,
        validate_response=lambda _draft, _hits: True,
        make_core_draft=lambda summary, citation_ids, action: CoreDraft(
            summary=summary, citation_ids=citation_ids, action=action
        ),
        answer_evidence_max_characters=12_000,
        phase_timeout=timedelta(seconds=10),
        now=lambda: now,
        execution_capability=lambda _owner, _key: "execution-capability",
        capability_hash=lambda _capability: None,
        admit_phase=lambda *_args: None,
        run_core=lambda *_args: None,
        run_finalize=lambda *_args: None,
    )
    return V2QuestionExecutionService(lambda: dependencies), executions


async def _active_generation() -> SimpleNamespace:
    return SimpleNamespace(generation=SimpleNamespace(id=uuid4()))


async def _case_record(
    cases: MemoryClarificationCaseRepository, context: ClarificationGrounding
):
    return await cases.create_or_get(
        owner_scope="anonymous:test",
        capability_hash=None,
        original_question="전기사업 허가가 필요한가요?",
        as_of_date=date(2026, 9, 3),
        project_stage="planning",
        conversation_id=None,
        case=context.case,
        expires_at=datetime(2026, 9, 4, tzinfo=UTC),
    )


@pytest.mark.asyncio
async def test_prepare_and_core_preserve_policy_and_sanitized_fact_state() -> None:
    claims = [
        GroundedClaim(
            "전혀 다른 표현의 일반 규칙입니다.",
            "general_rule",
            ("C1",),
            surface="summary",
            surface_index=None,
        )
    ]
    answerer = _CapturingAnswerer(claims=claims)
    service, _executions = _service(answerer)
    context = _context("interim")

    prepared = await service.prepare(
        PrepareQuestion(
            payload=QuestionRequest(
                question="전기사업 허가가 필요한가요?",
                clarification_capability="case-capability-must-not-be-copied",
            ),
            owner_scope="anonymous:test",
            idempotency_key="clarification-context",
            user=None,
            clarification=context,
        )
    )
    core = await service.run_core(prepared.execution)

    assert "100kW" not in str(prepared.execution.private_payload)
    assert "case-capability-must-not-be-copied" not in str(prepared.execution.private_payload)
    assert answerer.core_context is not None
    assert answerer.core_context.policy == "interim"
    assert [fact.status for fact in answerer.core_context.case.required_facts] == [
        FactStatus.ANSWERED,
        FactStatus.UNANSWERED,
    ]
    assert core.target.value == "core_answered"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("policy", "site_status", "next_status"),
    [
        ("interim", FactStatus.UNANSWERED, ClarificationCaseStatus.WAITING_FOR_USER),
        ("full", FactStatus.ANSWERED, ClarificationCaseStatus.COMPLETED),
    ],
)
async def test_grounded_finalize_persists_the_pending_case_transition(
    policy: str, site_status: FactStatus, next_status: ClarificationCaseStatus
) -> None:
    context = _context(policy, site_status=site_status)
    cases = MemoryClarificationCaseRepository()
    record = await _case_record(cases, context)
    outcome = ClarificationOutcome(
        case=record,
        policy=policy,
        question_format=ClarificationQuestionFormat(record.case.remaining_facts()),
        next_status=next_status,
    )
    service, _executions = _service(
        _CapturingAnswerer(claims=_detail_claims()), clarification_cases=cases
    )

    prepared = await service.prepare(
        PrepareQuestion(
            payload=QuestionRequest(question="전기사업 허가가 필요한가요?"),
            owner_scope="anonymous:test",
            idempotency_key=f"persist-{policy}",
            user=None,
            clarification=context,
            clarification_outcome=outcome,
        )
    )
    before_finalize = await cases.get_owned(record.case_id, "anonymous:test")

    result = await service.run_finalize(prepared.execution, None)

    persisted = await cases.get_owned(record.case_id, "anonymous:test")
    assert before_finalize.version == 0
    assert persisted.version == 1
    assert persisted.status is next_status
    published = result.events[0].payload["response"]
    if next_status is ClarificationCaseStatus.WAITING_FOR_USER:
        assert published["clarification"] == {
            "case_id": str(record.case_id),
            "status": "waiting_for_user",
            "question_format": [
                {
                    "id": "site",
                    "label": "설치 위치",
                    "why_needed": "관할을 판단합니다.",
                    "group": "사업 정보",
                    "priority": 2,
                }
            ],
            "remaining_count": 1,
        }
    else:
        assert published["clarification"] is None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("answer_mode", "ai_available", "policy", "site_status", "next_status"),
    [
        (
            "search_only",
            True,
            "interim",
            FactStatus.UNANSWERED,
            ClarificationCaseStatus.WAITING_FOR_USER,
        ),
        (
            "terra",
            False,
            "full",
            FactStatus.ANSWERED,
            ClarificationCaseStatus.COMPLETED,
        ),
    ],
)
async def test_clarification_safe_fallback_skips_structured_core_and_preserves_transition(
    answer_mode: str,
    ai_available: bool,
    policy: str,
    site_status: FactStatus,
    next_status: ClarificationCaseStatus,
) -> None:
    """A non-AI clarification still completes its phase and deferred case transition."""

    context = _context(policy, site_status=site_status)
    cases = MemoryClarificationCaseRepository()
    record = await _case_record(cases, context)
    outcome = ClarificationOutcome(
        case=record,
        policy=policy,
        question_format=ClarificationQuestionFormat(record.case.remaining_facts()),
        next_status=next_status,
    )
    answerer = _CapturingAnswerer(claims=_detail_claims())
    service, _executions = _service(
        answerer,
        clarification_cases=cases,
        ai_available=ai_available,
    )
    prepared = await service.prepare(
        PrepareQuestion(
            payload=QuestionRequest(
                question="전기사업 허가가 필요한가요?", answer_mode=answer_mode
            ),
            owner_scope="anonymous:test",
            idempotency_key=f"safe-fallback-{answer_mode}-{policy}",
            user=None,
            clarification=context,
            clarification_outcome=outcome,
        )
    )

    core = await service.run_core(prepared.execution)
    finalized = await service.run_finalize(prepared.execution, None)

    persisted = await cases.get_owned(record.case_id, "anonymous:test")
    published = finalized.events[0].payload["response"]
    assert core.target.value == "core_answered"
    assert answerer.core_calls == 0
    assert answerer.detail_calls == 0
    assert published["mode"] == "search_only"
    assert persisted.status is next_status
    assert persisted.version == 1
    if next_status is ClarificationCaseStatus.WAITING_FOR_USER:
        assert published["clarification"]["status"] == "waiting_for_user"
    else:
        assert published["clarification"] is None


@pytest.mark.asyncio
async def test_ungrounded_finalize_leaves_the_pending_case_untransitioned() -> None:
    context = _context("full", site_status=FactStatus.ANSWERED)
    cases = MemoryClarificationCaseRepository()
    record = await _case_record(cases, context)
    outcome = ClarificationOutcome(
        case=record,
        policy="full",
        question_format=ClarificationQuestionFormat(()),
        next_status=ClarificationCaseStatus.COMPLETED,
    )
    service, _executions = _service(
        _CapturingAnswerer(
            claims=[
                GroundedClaim(
                    "미검증 구조입니다.",
                    "general_rule",
                    ("C1",),
                    surface="summary",
                    surface_index=None,
                )
            ]
        ),
        clarification_cases=cases,
    )
    prepared = await service.prepare(
        PrepareQuestion(
            payload=QuestionRequest(question="전기사업 허가가 필요한가요?"),
            owner_scope="anonymous:test",
            idempotency_key="ungrounded-does-not-complete-case",
            user=None,
            clarification=context,
            clarification_outcome=outcome,
        )
    )

    await service.run_finalize(prepared.execution, None)

    persisted = await cases.get_owned(record.case_id, "anonymous:test")
    assert persisted.status is ClarificationCaseStatus.WAITING_FOR_USER
    assert persisted.version == 0


@pytest.mark.asyncio
async def test_invalid_waiting_metadata_leaves_the_case_untransitioned() -> None:
    context = _context("interim")
    cases = MemoryClarificationCaseRepository()
    record = await _case_record(cases, context)
    outcome = ClarificationOutcome(
        case=record,
        policy="interim",
        question_format=ClarificationQuestionFormat(record.case.remaining_facts()),
        next_status=ClarificationCaseStatus.WAITING_FOR_USER,
    )
    service, _executions = _service(
        _CapturingAnswerer(claims=_detail_claims()), clarification_cases=cases
    )
    prepared = await service.prepare(
        PrepareQuestion(
            payload=QuestionRequest(question="전기사업 허가가 필요한가요?"),
            owner_scope="anonymous:test",
            idempotency_key="invalid-waiting-metadata",
            user=None,
            clarification=context,
            clarification_outcome=outcome,
        )
    )
    prepared.execution.private_payload["clarification_outcome"]["question_format"] = [
        {"id": ""}
    ]

    await service.run_finalize(prepared.execution, None)

    persisted = await cases.get_owned(record.case_id, "anonymous:test")
    assert persisted.status is ClarificationCaseStatus.WAITING_FOR_USER
    assert persisted.version == 0


def test_interim_claims_are_structural_and_allow_answered_case_application() -> None:
    context = _context("interim")
    registry = CitationRegistry((FrozenCitation(id="C1", quote="원문과 무관한 문구"),))

    assert claims_are_grounded(
        (
            GroundedClaim(
                "전혀 다른 표현의 일반 규칙입니다.",
                "general_rule",
                ("C1",),
                surface="summary",
                surface_index=None,
            ),
            GroundedClaim(
                "설치 위치에 따라 결과가 달라집니다.",
                "conditional",
                ("C1",),
                surface="summary",
                surface_index=None,
                required_fact_ids=("site",),
            ),
            GroundedClaim(
                "용량 사실에 따른 안내입니다.",
                "case_application",
                ("C1",),
                surface="summary",
                surface_index=None,
                required_fact_ids=("capacity",),
            ),
        ),
        context,
        registry,
    )


def test_claim_gate_rejects_an_empty_claim_list() -> None:
    context = _context("interim")
    registry = CitationRegistry((FrozenCitation(id="C1", quote="공식 원문"),))

    assert not claims_are_grounded((), context, registry)


def test_grounded_claim_declares_its_published_target() -> None:
    assert {"surface", "surface_index"} <= set(GroundedClaim.__dataclass_fields__)


def test_claim_gate_requires_complete_unique_structural_coverage() -> None:
    context = _context("interim")
    registry = CitationRegistry((FrozenCitation(id="C1", quote="공식 원문"),))
    summary = GroundedClaim(
        "원문과 다른 표현의 일반 규칙입니다.",
        "general_rule",
        ("C1",),
        surface="summary",
        surface_index=None,
    )
    section = GroundedClaim(
        "이 설명의 문구는 원문과 일치할 필요가 없습니다.",
        "general_rule",
        ("C1",),
        surface="section_claim",
        surface_index=0,
    )
    targets = (("summary", None), ("section_claim", 0))

    assert not claims_are_grounded(
        (summary,), context, registry, required_targets=targets
    )
    assert not claims_are_grounded(
        (summary, summary), context, registry, required_targets=(("summary", None),)
    )
    assert claims_are_grounded((summary, section), context, registry, required_targets=targets)


@pytest.mark.parametrize(
    ("policy", "capacity_status", "site_status", "claim"),
    [
        (
            "full",
            FactStatus.ANSWERED,
            FactStatus.ANSWERED,
            GroundedClaim(
                "확정 사실에 따른 안내입니다.",
                "case_application",
                ("C1",),
                surface="summary",
                surface_index=None,
                required_fact_ids=("capacity",),
            ),
        ),
        (
            "conditional",
            FactStatus.ANSWERED,
            FactStatus.UNANSWERED,
            GroundedClaim(
                "설치 위치에 따라 결과가 달라집니다.",
                "conditional",
                ("C1",),
                surface="summary",
                surface_index=None,
                required_fact_ids=("site",),
            ),
        ),
    ],
)
def test_full_and_explicit_conditional_policies_accept_their_grounded_claims(
    policy: str, capacity_status: FactStatus, site_status: FactStatus, claim: GroundedClaim
) -> None:
    context = _context(policy, capacity_status=capacity_status, site_status=site_status)
    registry = CitationRegistry((FrozenCitation(id="C1", quote="공식 원문"),))

    assert claims_are_grounded((claim,), context, registry)


@pytest.mark.asyncio
async def test_invalid_claim_is_replaced_before_terminal_sse_publication() -> None:
    answerer = _CapturingAnswerer(
        claims=[
            GroundedClaim(
                "근거 없는 사례 적용입니다.",
                "case_application",
                ("C1",),
                surface="summary",
                surface_index=None,
                required_fact_ids=("site",),
            )
        ]
    )
    service, executions = _service(answerer)
    context = _context("interim")
    hit = _hit()
    execution = await executions.prepare_or_get(
        owner_scope="anonymous:test",
        prepare_idempotency_key="invalid-claim",
        generation_id=uuid4(),
        expires_at=datetime.now(UTC) + timedelta(minutes=10),
        private_payload={
            "request": QuestionRequest(
                question="전기사업 허가가 필요한가요?"
            ).model_dump(mode="json"),
            "hits": [hit.model_dump(mode="json")],
            "generation_hits": [hit.model_dump(mode="json")],
            "route": "legal_search",
            "clarification_grounding": context.to_payload(),
            "verified_core": {
                "summary": "검증된 요약입니다.",
                "citation_ids": ["C1"],
                "action": "partially_answerable",
            },
            "verified_core_citations": [],
        },
        frozen_citations=(FrozenCitation(id="C1", quote=hit.content),),
    )

    result = await service.run_finalize(execution, None)

    published = result.events[0].payload["response"]
    assert published["sections"] == []
    assert "근거 없는 사례 적용" not in str(published)


@pytest.mark.asyncio
async def test_unbound_published_detail_is_replaced_before_terminal_sse_publication() -> None:
    answerer = _CapturingAnswerer(
        claims=[
            GroundedClaim(
                "문구와 무관한 일반 규칙입니다.",
                "general_rule",
                ("C1",),
                surface="summary",
                surface_index=None,
            )
        ]
    )
    service, executions = _service(answerer)
    context = _context("interim")
    hit = _hit()
    execution = await executions.prepare_or_get(
        owner_scope="anonymous:test",
        prepare_idempotency_key="unbound-detail",
        generation_id=uuid4(),
        expires_at=datetime.now(UTC) + timedelta(minutes=10),
        private_payload={
            "request": QuestionRequest(
                question="전기사업 허가가 필요한가요?"
            ).model_dump(mode="json"),
            "hits": [hit.model_dump(mode="json")],
            "generation_hits": [hit.model_dump(mode="json")],
            "route": "legal_search",
            "clarification_grounding": context.to_payload(),
        },
        frozen_citations=(FrozenCitation(id="C1", quote=hit.content),),
    )

    result = await service.run_finalize(execution, None)

    published = result.events[0].payload["response"]
    assert published["sections"] == []
    assert published["checklist"] == []


@pytest.mark.asyncio
async def test_core_repair_failure_completes_with_a_recoverable_grounding_fallback() -> None:
    """A failed repair must not be presented as an ordinary empty search result."""

    class AlwaysUngroundedCoreAnswerer:
        def __init__(self) -> None:
            self.core_calls = 0
            self.detail_calls = 0

        async def answer_core(
            self, _request: QuestionRequest, _hits: list[SearchHit]
        ) -> CoreDraft:
            self.core_calls += 1
            return CoreDraft(
                summary="근거와 일치하지 않는 요약입니다.",
                citation_ids=["C2"],
                action="partially_answerable",
            )

        async def answer(
            self, _request: QuestionRequest, _hits: list[SearchHit]
        ) -> ClarificationDraftAnswer:
            self.detail_calls += 1
            raise AssertionError("core repair failure must not start detail generation")

    answerer = AlwaysUngroundedCoreAnswerer()
    service, executions = _service(answerer)  # type: ignore[arg-type]
    prepared = await service.prepare(
        PrepareQuestion(
            payload=QuestionRequest(question="전기사업 허가가 필요한가요?"),
            owner_scope="anonymous:test",
            idempotency_key="core-repair-safe-completion",
            user=None,
        )
    )
    claim = await executions.claim_phase(
        prepared.execution.execution_id,
        "anonymous:test",
        expected_version=prepared.execution.version,
        target=ExecutionStatus.CORE_RUNNING,
    )
    core = await service.run_core(claim.execution)
    assert core.target is ExecutionStatus.CORE_REPAIR_REQUIRED
    await executions.finish_phase(
        prepared.execution.execution_id,
        "anonymous:test",
        expected_version=claim.execution.version,
        target=core.target,
        phase="core",
        events=core.events,
    )
    repair_required = await executions.get_owned(
        prepared.execution.execution_id, "anonymous:test"
    )
    finalize_claim = await executions.claim_phase(
        prepared.execution.execution_id,
        "anonymous:test",
        expected_version=repair_required.version,
        target=ExecutionStatus.FINALIZE_RUNNING,
        private_payload={
            "finalize_source_status": repair_required.status.value,
        },
    )
    repair_required = finalize_claim.execution

    finalized = await service.run_finalize(repair_required, None)

    published = finalized.events[0].payload["response"]
    assert answerer.core_calls == 2
    assert answerer.detail_calls == 0
    assert finalized.events[0].payload["outcome"] == "degraded"
    assert published["result_status"] == "grounding_failed"
    assert published["summary"] == (
        "검증된 법률 주장을 만들지 못했습니다. 인용된 공식 원문을 직접 확인해 주세요."
    )
    assert published["sections"] == []
    assert published["checklist"] == []
    assert published["citations"] == []
    assert published["action"] == "unanswerable"


@pytest.mark.asyncio
async def test_successful_core_repair_persists_clarification_transition() -> None:
    """A repaired, grounded core must resume the normal clarification finish path."""

    class RepairingClarificationAnswerer:
        def __init__(self) -> None:
            self.core_calls = 0
            self.detail_calls = 0

        async def answer_core(
            self,
            _request: QuestionRequest,
            _hits: list[SearchHit],
            *,
            clarification: ClarificationGrounding,
        ) -> ClarificationCoreDraft:
            self.core_calls += 1
            claims = (
                _detail_claims()
                if self.core_calls == 1
                else [
                    GroundedClaim(
                        "A verified repair claim.",
                        "general_rule",
                        ("C1",),
                        surface="summary",
                        surface_index=None,
                    )
                ]
            )
            return ClarificationCoreDraft(
                summary="A verified repair claim.",
                citation_ids=["C1"],
                action="partially_answerable",
                grounded_claims=claims,
            )

        async def answer(
            self,
            _request: QuestionRequest,
            _hits: list[SearchHit],
            *,
            clarification: ClarificationGrounding,
        ) -> ClarificationDraftAnswer:
            self.detail_calls += 1
            return _draft(claims=_detail_claims())

    now = datetime(2026, 9, 3, tzinfo=UTC)
    context = _context("interim")
    cases = MemoryClarificationCaseRepository(now=lambda: now)
    record = await _case_record(cases, context)
    outcome = ClarificationOutcome(
        case=record,
        policy="interim",
        question_format=ClarificationQuestionFormat(record.case.remaining_facts()),
        next_status=ClarificationCaseStatus.WAITING_FOR_USER,
    )
    answerer = RepairingClarificationAnswerer()
    service, executions = _service(  # type: ignore[arg-type]
        answerer,
        clarification_cases=cases,
    )
    prepared = await service.prepare(
        PrepareQuestion(
            payload=QuestionRequest(question="전기사업 허가가 필요한가요?"),
            owner_scope="anonymous:test",
            idempotency_key="successful-core-repair-clarification",
            user=None,
            clarification=context,
            clarification_outcome=outcome,
        )
    )
    claim = await executions.claim_phase(
        prepared.execution.execution_id,
        "anonymous:test",
        expected_version=prepared.execution.version,
        target=ExecutionStatus.CORE_RUNNING,
    )
    core = await service.run_core(claim.execution)
    assert core.target is ExecutionStatus.CORE_REPAIR_REQUIRED
    await executions.finish_phase(
        prepared.execution.execution_id,
        "anonymous:test",
        expected_version=claim.execution.version,
        target=core.target,
        phase="core",
        events=core.events,
    )
    repair_required = await executions.get_owned(
        prepared.execution.execution_id, "anonymous:test"
    )

    finalized = await service.run_finalize(repair_required, None)

    persisted = await cases.get_owned(record.case_id, "anonymous:test")
    published = finalized.events[0].payload["response"]
    assert answerer.core_calls == 2
    assert answerer.detail_calls == 1
    assert persisted.version == 1
    assert persisted.status is ClarificationCaseStatus.WAITING_FOR_USER
    assert finalized.events[0].payload["outcome"] == "normal"
    assert published["clarification"]["status"] == "waiting_for_user"
