from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.adapters.memory_question_execution import MemoryQuestionExecutionRepository
from app.adapters.openai_answerer import ClarificationCoreDraft, ClarificationDraftAnswer, CoreDraft
from app.application.v2.dependencies import PrepareQuestion
from app.application.v2.grounding import ClarificationGrounding, claims_are_grounded
from app.application.v2.phase_service import V2QuestionExecutionService
from app.domain.clarification import ClarificationCase, FactStatus, GroundedClaim, RequiredFact
from app.domain.grounding import CitationRegistry, FrozenCitation
from app.domain.schemas import AnswerSection, QuestionRequest, SearchHit, SourceKind


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


class _CapturingAnswerer:
    def __init__(self, *, claims: list[GroundedClaim]) -> None:
        self.claims = claims
        self.core_context: ClarificationGrounding | None = None
        self.detail_context: ClarificationGrounding | None = None

    async def answer_core(
        self,
        _request: QuestionRequest,
        _hits: list[SearchHit],
        *,
        clarification: ClarificationGrounding,
    ) -> CoreDraft:
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
        self.detail_context = clarification
        return _draft(claims=self.claims)


def _service(
    answerer: _CapturingAnswerer,
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
        resolve_repository=_resolve_repository,
        active_provider=lambda: SimpleNamespace(
            active=lambda: _active_generation()
        ),
        retrieve_evidence=_retrieve,
        route=_route,
        answerer=lambda: answerer,
        ai_available=lambda: True,
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


@pytest.mark.asyncio
async def test_prepare_and_core_preserve_policy_and_sanitized_fact_state() -> None:
    claims = [GroundedClaim("전혀 다른 표현의 일반 규칙입니다.", "general_rule", ("C1",))]
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


def test_interim_claims_are_structural_and_allow_answered_case_application() -> None:
    context = _context("interim")
    registry = CitationRegistry((FrozenCitation(id="C1", quote="원문과 무관한 문구"),))

    assert claims_are_grounded(
        (
            GroundedClaim("전혀 다른 표현의 일반 규칙입니다.", "general_rule", ("C1",)),
            GroundedClaim("설치 위치에 따라 결과가 달라집니다.", "conditional", ("C1",), ("site",)),
            GroundedClaim(
                "용량 사실에 따른 안내입니다.", "case_application", ("C1",), ("capacity",)
            ),
        ),
        context,
        registry,
    )


@pytest.mark.parametrize(
    ("policy", "capacity_status", "site_status", "claim"),
    [
        (
            "full",
            FactStatus.ANSWERED,
            FactStatus.ANSWERED,
            GroundedClaim(
                "확정 사실에 따른 안내입니다.", "case_application", ("C1",), ("capacity",)
            ),
        ),
        (
            "conditional",
            FactStatus.ANSWERED,
            FactStatus.UNANSWERED,
            GroundedClaim("설치 위치에 따라 결과가 달라집니다.", "conditional", ("C1",), ("site",)),
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
        claims=[GroundedClaim("근거 없는 사례 적용입니다.", "case_application", ("C1",), ("site",))]
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
