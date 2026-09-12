import asyncio
from datetime import UTC, date, datetime, timedelta
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from starlette.requests import Request

from app.adapters.openai_answerer import CoreDraft, DraftAnswer
from app.application.question_phase_coordinator import PhaseResult
from app.domain.answer_events import AnswerEvent
from app.domain.catalog import SourceKind
from app.domain.grounding import FrozenCitation
from app.domain.question_execution import ExecutionStatus
from app.domain.schemas import AnswerSection, Citation, QuestionRequest, QuestionResponse, SearchHit


async def _allow_supported_date(*args) -> None:
    return None


async def _legal_search_route(*args):
    return SimpleNamespace(route="legal_search", missing_fields=())


def _v2_hit() -> SearchHit:
    return SearchHit(
        provision_id=uuid4(),
        document_id=uuid4(),
        document_title="전기사업법",
        source_kind=SourceKind.LAW,
        version_label="MST 1",
        effective_from=date(2026, 1, 1),
        effective_to=None,
        path="제1조",
        content="전기사업자는 허가를 받아야 합니다.",
        source_url="https://www.law.go.kr/법령/전기사업법/제1조",
    )


@pytest.mark.asyncio
async def test_v2_retrieval_normalizes_lay_sales_term_before_vector_search(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import app.api.v2.executions as executions_module

    captured: dict[str, object] = {}

    async def search_index(index, query, as_of_date, limit):
        captured.update({"index": index, "query": query, "as_of_date": as_of_date, "limit": limit})
        return []

    fake_main = SimpleNamespace(llamaindex_search_index=search_index)
    monkeypatch.setattr(executions_module, "main_module", lambda: fake_main)
    repository = SimpleNamespace(last_sync=lambda: asyncio.sleep(0, result=None))
    payload = QuestionRequest(question="전기 판매 정산금을 확인하고 싶습니다")

    hits, _corpus_as_of = await executions_module._retrieve_pinned_v2_evidence(
        payload, SimpleNamespace(index="frozen-index"), repository
    )

    assert hits == []
    assert captured == {
        "index": "frozen-index",
        "query": "전력거래 정산금을 확인하고 싶습니다",
        "as_of_date": payload.as_of_date,
        "limit": 10,
    }


def test_v2_prepare_requires_an_idempotency_key() -> None:
    import app.main as main_module

    response = TestClient(main_module.app).post(
        "/v2/question-executions",
        json={"question": "전기사업 허가가 필요한가요?"},
    )

    assert response.status_code == 422


def test_v2_prepare_cors_allows_the_idempotency_key() -> None:
    import app.main as main_module

    response = TestClient(main_module.app).options(
        "/v2/question-executions",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "Idempotency-Key,Content-Type",
        },
    )

    assert response.status_code == 200
    assert "idempotency-key" in response.headers["access-control-allow-headers"].lower()


def test_v2_phase_cors_allows_the_execution_capability() -> None:
    import app.main as main_module

    response = TestClient(main_module.app).options(
        "/v2/question-executions/00000000-0000-0000-0000-000000000001/core",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "X-Execution-Capability",
        },
    )

    assert response.status_code == 200
    assert "x-execution-capability" in response.headers["access-control-allow-headers"].lower()


@pytest.mark.asyncio
async def test_v2_phase_finishes_before_returning_serverless_stream(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import app.api.v2.sse as sse_module

    release = asyncio.Event()

    class Service:
        async def begin_core(self, request):
            return object()

        async def await_phase(self, run):
            await release.wait()
            return (
                AnswerEvent(
                    event_type="phase_complete",
                    payload={"next_action": "generate_detail"},
                ),
            )

    fake_main = SimpleNamespace(
        v2_question_execution_service=Service(),
        _capability_hash=lambda value: value,
        _question_owner=lambda request, user: "anonymous:test",
    )

    async def anonymous(_authorization):
        return None

    monkeypatch.setattr(sse_module, "main_module", lambda: fake_main)
    monkeypatch.setattr(sse_module, "_optional_user", anonymous)

    response_task = asyncio.create_task(
        sse_module._stream_execution_phase(
            uuid4(),
            Request({"type": "http", "headers": []}),
            "core",
            "capability",
        )
    )
    await asyncio.sleep(0)

    assert not response_task.done()
    release.set()
    response = await response_task
    assert response.media_type == "text/event-stream"


def test_obsolete_v2_single_question_route_is_removed() -> None:
    import app.main as main_module

    response = TestClient(main_module.app).post(
        "/v2/questions",
        json={"question": "전기사업 허가가 필요한가요?"},
    )

    assert response.status_code == 404


def test_v2_prepare_passes_anonymous_case_capability_only_to_clarification_workflow(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A case capability authorizes the workflow but never reaches a public payload."""

    import app.main as main_module

    case_id = uuid4()
    captured: dict[str, object] = {}

    class Workflow:
        async def run_turn(self, request, owner):
            captured["request"] = request
            captured["owner"] = owner
            return SimpleNamespace(case=None, next_status=None)

    class Service:
        async def prepare(self, request):
            captured["prepare"] = request
            return SimpleNamespace(execution=SimpleNamespace(execution_id=uuid4()))

        def prepared_response(self, _prepared):
            return {
                "execution_id": "execution-1",
                "status": "prepared",
                "next_action": "generate_core",
            }

    monkeypatch.setattr(main_module, "clarification_workflow", Workflow())
    monkeypatch.setattr(main_module, "v2_question_execution_service", Service())

    response = TestClient(main_module.app).post(
        "/v2/question-executions",
        headers={"Idempotency-Key": "clarification-key"},
        json={
            "question": "발전 설비는 100kW입니다.",
            "clarification_case_id": str(case_id),
            "clarification_capability": "private-case-capability",
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "execution_id": "execution-1",
        "status": "prepared",
        "next_action": "generate_core",
    }
    assert captured["request"].case_id == case_id
    assert captured["owner"].capability_hash == main_module._capability_hash(
        "private-case-capability"
    )
    assert captured["prepare"].payload.clarification_capability == "private-case-capability"
    assert "private-case-capability" not in response.text


def test_v2_prepare_persists_one_routing_unavailable_decision_after_optional_router_timeout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """One failed classifier decision is frozen instead of retried during prepare."""
    import app.main as main_module
    from app.adapters.memory_question_execution import MemoryQuestionExecutionRepository

    executions = MemoryQuestionExecutionRepository()
    router_calls = 0

    class Workflow:
        async def run_turn(self, _request, _owner):
            return SimpleNamespace(case=None, next_status=None)

    class Provider:
        async def active(self):
            return SimpleNamespace(generation=SimpleNamespace(id=uuid4()))

    async def fake_repository():
        return object()

    async def provider_timeout(*_args):
        nonlocal router_calls
        router_calls += 1
        raise TimeoutError("NVIDIA route classifier timed out")

    monkeypatch.setattr(main_module, "question_execution_repository", executions)
    monkeypatch.setattr(main_module, "_v2_repository", fake_repository)
    monkeypatch.setattr(main_module, "_require_supported_as_of_date", _allow_supported_date)
    monkeypatch.setattr(
        main_module, "_llamaindex_resources", lambda: (Provider(), object(), object())
    )
    monkeypatch.setattr(main_module, "clarification_workflow", Workflow())
    monkeypatch.setattr(main_module, "_v2_question_router", lambda: object())
    monkeypatch.setattr(main_module, "route_question", provider_timeout)

    response = TestClient(main_module.app, raise_server_exceptions=False).post(
        "/v2/question-executions",
        headers={"Idempotency-Key": "route-timeout"},
        json={"question": "전기사업 허가가 필요한가요?", "answer_mode": "terra"},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "prepared"
    assert router_calls == 1
    execution = executions._records[UUID(response.json()["execution_id"])]
    assert execution.private_payload["route"] == "routing_unavailable"


@pytest.mark.parametrize(
    ("snapshot_id", "generation_id"),
    (("wrong-snapshot", None), ("snapshot-1", uuid4())),
)
def test_v2_prepare_rejects_evaluation_corpus_or_generation_mismatch_before_retrieval(
    monkeypatch: pytest.MonkeyPatch,
    snapshot_id: str,
    generation_id,
) -> None:
    import app.main as main_module
    from app.adapters.memory_question_execution import MemoryQuestionExecutionRepository

    active_generation_id = uuid4()
    retrieval_called = False

    class Workflow:
        async def run_turn(self, _request, _owner):
            return SimpleNamespace(case=None, next_status=None)

    class Repository:
        async def corpus_temporal_state(self, _today):
            return SimpleNamespace(ready=True, corpus_snapshot_id="snapshot-1")

    class Provider:
        async def active(self):
            return SimpleNamespace(
                generation=SimpleNamespace(id=active_generation_id), index=object()
            )

    async def fake_repository():
        return Repository()

    async def fixed_route(*_args):
        return SimpleNamespace(route="legal_search", missing_fields=())

    async def fail_retrieval(*_args):
        nonlocal retrieval_called
        retrieval_called = True
        return [], None

    monkeypatch.setattr(
        main_module, "question_execution_repository", MemoryQuestionExecutionRepository()
    )
    monkeypatch.setattr(main_module, "_v2_repository", fake_repository)
    monkeypatch.setattr(main_module, "_require_supported_as_of_date", _allow_supported_date)
    monkeypatch.setattr(
        main_module, "_llamaindex_resources", lambda: (Provider(), object(), object())
    )
    monkeypatch.setattr(main_module, "clarification_workflow", Workflow())
    monkeypatch.setattr(main_module, "route_question", fixed_route)
    monkeypatch.setattr(main_module, "_retrieve_pinned_v2_evidence", fail_retrieval)

    response = TestClient(main_module.app, raise_server_exceptions=False).post(
        "/v2/question-executions",
        headers={
            "Idempotency-Key": "evaluation-binding-mismatch",
            "X-Evaluation-Corpus-Snapshot": snapshot_id,
            "X-Evaluation-Generation-Id": str(generation_id or active_generation_id),
        },
        json={"question": "전기사업 허가가 필요한가요?", "answer_mode": "terra"},
    )

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "evaluation_corpus_binding_mismatch"
    assert retrieval_called is False

def test_v2_prepare_replay_revalidates_evaluation_binding(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import app.main as main_module
    from app.adapters.memory_question_execution import MemoryQuestionExecutionRepository

    active_generation_id = uuid4()
    retrieval_calls = 0

    class Workflow:
        async def run_turn(self, _request, _owner):
            return SimpleNamespace(case=None, next_status=None)

    class Repository:
        async def corpus_temporal_state(self, _today):
            return SimpleNamespace(ready=True, corpus_snapshot_id="snapshot-1")

    class Provider:
        async def active(self):
            return SimpleNamespace(
                generation=SimpleNamespace(id=active_generation_id), index=object()
            )

    async def fake_repository():
        return Repository()

    async def fixed_route(*_args):
        return SimpleNamespace(route="legal_search", missing_fields=())

    async def fake_retrieval(*_args):
        nonlocal retrieval_calls
        retrieval_calls += 1
        return [], None

    monkeypatch.setattr(
        main_module, "question_execution_repository", MemoryQuestionExecutionRepository()
    )
    monkeypatch.setattr(main_module, "_v2_repository", fake_repository)
    monkeypatch.setattr(main_module, "_require_supported_as_of_date", _allow_supported_date)
    monkeypatch.setattr(
        main_module, "_llamaindex_resources", lambda: (Provider(), object(), object())
    )
    monkeypatch.setattr(main_module, "clarification_workflow", Workflow())
    monkeypatch.setattr(main_module, "route_question", fixed_route)
    monkeypatch.setattr(main_module, "_retrieve_pinned_v2_evidence", fake_retrieval)
    client = TestClient(main_module.app, raise_server_exceptions=False)
    payload = {"question": "전기사업 허가가 필요한가요?", "answer_mode": "terra"}
    headers = {
        "Idempotency-Key": "evaluation-binding-replay",
        "X-Evaluation-Corpus-Snapshot": "snapshot-1",
        "X-Evaluation-Generation-Id": str(active_generation_id),
    }

    first = client.post("/v2/question-executions", headers=headers, json=payload)
    retrieval_calls_after_first = retrieval_calls
    replay = client.post(
        "/v2/question-executions",
        headers={**headers, "X-Evaluation-Generation-Id": str(uuid4())},
        json=payload,
    )
    unbound_replay = client.post(
        "/v2/question-executions",
        headers={"Idempotency-Key": "evaluation-binding-replay"},
        json=payload,
    )

    assert first.status_code == 200
    assert first.json()["evaluation_retrieved_evidence_ids"] == []
    assert replay.status_code == 409
    assert replay.json()["detail"]["code"] == "evaluation_corpus_binding_mismatch"
    assert unbound_replay.status_code == 409
    assert unbound_replay.json()["detail"]["code"] == (
        "evaluation_corpus_binding_mismatch"
    )
    assert retrieval_calls == retrieval_calls_after_first


@pytest.mark.asyncio
async def test_v2_prepare_uses_v2_router_seam_instead_of_v1_router(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import app.main as main_module
    from app.api.v2.executions import _prepare_clarification_turn

    v2_router = object()

    def fail_v1_router() -> object:
        raise AssertionError("V1 router must not be used by V2 prepare")

    async def route_question(question: str, router: object) -> SimpleNamespace:
        assert question == "private question"
        assert router is v2_router
        return SimpleNamespace(route="legal_search", missing_fields=())

    monkeypatch.setattr(main_module, "_question_router", fail_v1_router)
    monkeypatch.setattr(main_module, "_v2_question_router", lambda: v2_router)
    monkeypatch.setattr(main_module, "route_question", route_question)
    monkeypatch.setattr(main_module, "clarification_workflow", object())

    _, _, decision = await _prepare_clarification_turn(
        main_module,
        QuestionRequest(question="private question"),
        "anonymous:test",
        None,
    )

    assert decision is not None
    assert decision.route == "legal_search"


def test_v2_prepare_enforces_the_v2_phase_deadline(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import app.api.v2.executions as executions_module
    import app.main as main_module

    async def slow_prepare(*_args: object) -> None:
        await asyncio.sleep(0.05)

    monkeypatch.setattr(executions_module, "_prepare_clarification_turn", slow_prepare)
    monkeypatch.setattr(main_module.settings, "v2_phase_timeout_seconds", 0.01)

    response = TestClient(main_module.app, raise_server_exceptions=False).post(
        "/v2/question-executions",
        headers={"Idempotency-Key": "prepare-deadline"},
        json={"question": "private question", "answer_mode": "terra"},
    )

    assert response.status_code == 504
    assert response.json()["detail"] == "v2_prepare_timeout"


def test_v2_prepare_hides_foreign_clarification_cases_as_not_found(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Foreign, expired, and invalid case ids share one non-enumerable response."""

    import app.main as main_module
    from app.ports.clarification_case import ClarificationCaseNotFound

    class Workflow:
        async def run_turn(self, _request, _owner):
            raise ClarificationCaseNotFound()

    monkeypatch.setattr(main_module, "clarification_workflow", Workflow())

    response = TestClient(main_module.app).post(
        "/v2/question-executions",
        headers={"Idempotency-Key": "foreign-case"},
        json={
            "question": "이어서 답변해 주세요.",
            "clarification_case_id": str(UUID("00000000-0000-0000-0000-000000000001")),
            "clarification_capability": "foreign-capability",
        },
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "보완 질문을 찾을 수 없습니다."}


@pytest.mark.asyncio
async def test_v2_core_persists_only_verified_summary_and_finalize_generates_detail(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import app.main as main_module
    from app.adapters.memory_question_execution import MemoryQuestionExecutionRepository

    request = QuestionRequest(question="전기사업 허가가 필요한가요?", answer_mode="terra")
    hit = _v2_hit()
    repository = MemoryQuestionExecutionRepository()
    execution = await repository.prepare_or_get(
        owner_scope="anonymous:test",
        prepare_idempotency_key="test-key",
        generation_id=uuid4(),
        expires_at=datetime.now(UTC) + timedelta(minutes=10),
        private_payload={
            "request": request.model_dump(mode="json"),
            "hits": [hit.model_dump(mode="json")],
            "route": "legal_search",
        },
        frozen_citations=(FrozenCitation(id="C1", quote=hit.content),),
    )

    class Answerer:
        detail_calls = 0

        async def answer_core(self, *_args):
            return CoreDraft(
                summary="전기사업자는 허가를 받아야 합니다.",
                citation_ids=["C1"],
                action="fully_answerable",
            )

        async def answer(self, *_args):
            self.detail_calls += 1
            return DraftAnswer(
                summary="상세 생성 요약은 core 요약으로 바뀌어야 합니다.",
                scope="기준일 현재",
                sections=[
                    AnswerSection(
                        claim="허가를 확인하세요.",
                        explanation="원문에 허가 요건이 있습니다.",
                        citation_ids=["C1"],
                    )
                ],
                checklist=[
                    {
                        "label": "원문을 확인하세요.",
                        "status": "check",
                        "citation_ids": ["C1"],
                    }
                ],
                action="fully_answerable",
            )

    answerer = Answerer()
    monkeypatch.setattr(main_module, "_answerer", lambda: answerer)
    monkeypatch.setattr(main_module, "_ai_available", lambda: True)

    core = await main_module._run_v2_core(execution)

    assert core.response is None
    assert core.private_payload is not None
    assert core.private_payload["verified_core"] == {
        "summary": "전기사업자는 허가를 받아야 합니다.",
        "citation_ids": ["C1"],
        "action": "fully_answerable",
    }
    assert "sections" not in core.private_payload["verified_core"]

    finalized = await main_module._run_v2_finalize(
        SimpleNamespace(
            private_payload={**execution.private_payload, **core.private_payload},
            frozen_citations=execution.frozen_citations,
            status=main_module.ExecutionStatus.CORE_ANSWERED,
        ),
        None,
    )

    assert answerer.detail_calls == 1
    assert finalized.response is not None
    assert finalized.response["summary"] == "전기사업자는 허가를 받아야 합니다."
    assert finalized.response["sections"]


@pytest.mark.asyncio
async def test_v2_finalize_reports_degraded_when_detail_generation_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import app.main as main_module

    request = QuestionRequest(question="전기사업 허가가 필요한가요?", answer_mode="terra")
    hit = _v2_hit()

    async def unavailable_detail(_execution):
        raise RuntimeError("provider unavailable")

    monkeypatch.setattr(main_module, "_v2_response_from_frozen_evidence", unavailable_detail)
    result = await main_module._run_v2_finalize(
        SimpleNamespace(
            private_payload={
                "request": request.model_dump(mode="json"),
                "hits": [hit.model_dump(mode="json")],
                "verified_core": {
                    "summary": "전기사업자는 허가를 받아야 합니다.",
                    "citation_ids": ["C1"],
                    "action": "fully_answerable",
                },
                "verified_core_citations": [
                    {
                        "id": "C1",
                        "provision_id": str(hit.provision_id),
                        "document_title": hit.document_title,
                        "version_label": hit.version_label,
                        "path": hit.path,
                        "quote": hit.content,
                        "source_url": hit.source_url,
                        "source_kind": hit.source_kind.value,
                    }
                ],
            },
            frozen_citations=(FrozenCitation(id="C1", quote=hit.content),),
            status=main_module.ExecutionStatus.CORE_ANSWERED,
        ),
        None,
    )

    assert result.response is not None
    assert result.response["summary"] == "전기사업자는 허가를 받아야 합니다."
    assert result.response["checklist"] == [
        {
            "label": "C1 원문에서 적용 주체, 요건 및 예외를 확인하세요.",
            "status": "check",
            "citation_ids": ["C1"],
        }
    ]
    assert [citation["id"] for citation in result.response["citations"]] == ["C1"]
    assert result.events[0].payload["outcome"] == "degraded"


@pytest.mark.asyncio
@pytest.mark.parametrize("core_action", ["fully_answerable", "partially_answerable"])
async def test_v2_finalize_does_not_reapply_uncited_core_after_grounding_fallback(
    monkeypatch: pytest.MonkeyPatch, core_action: str
) -> None:
    import app.main as main_module

    request = QuestionRequest(question="전기사업 허가가 필요한가요?", answer_mode="terra")
    hit = _v2_hit()

    async def ungrounded_detail(_execution):
        return _grounded_detail_response(hit, action=core_action).model_copy(
            update={"citations": [], "sections": [], "checklist": []}
        )

    monkeypatch.setattr(main_module, "_v2_response_from_frozen_evidence", ungrounded_detail)
    result = await main_module._run_v2_finalize(
        SimpleNamespace(
            private_payload={
                "request": request.model_dump(mode="json"),
                "hits": [hit.model_dump(mode="json")],
                "route": "legal_search",
                "verified_core": {
                    "summary": hit.content,
                    "citation_ids": ["C1"],
                    "action": core_action,
                },
                "verified_core_citations": [],
            },
            frozen_citations=(FrozenCitation(id="C1", quote=hit.content),),
            status=main_module.ExecutionStatus.CORE_ANSWERED,
        ),
        None,
    )

    assert result.response is not None
    assert result.response["action"] == "unanswerable"
    assert result.response["result_status"] == "grounding_failed"
    assert result.response["summary"] == (
        "검증된 법률 주장을 만들지 못했습니다. 인용된 공식 원문을 직접 확인해 주세요."
    )
    assert result.response["sections"] == []
    assert result.response["checklist"] == []
    assert result.response["citations"] == []


def _grounded_detail_response(hit: SearchHit, *, action: str = "partially_answerable"):
    return QuestionResponse(
        request_id=str(uuid4()),
        mode="ai",
        summary=hit.content,
        scope="기준일 현재",
        sections=[
            AnswerSection(
                claim=hit.content,
                explanation=hit.content,
                citation_ids=["C1"],
            )
        ],
        checklist=[{"label": hit.content, "status": "conditional", "citation_ids": ["C1"]}],
        citations=[
            Citation(
                id="C1",
                provision_id=hit.provision_id,
                document_title=hit.document_title,
                version_label=hit.version_label,
                path=hit.path,
                quote=hit.content,
                source_url=hit.source_url,
                source_kind=hit.source_kind,
            )
        ],
        limitations=["개별 적용 여부는 추가 확인이 필요합니다."],
        requested_answer_mode="terra",
        action=action,
        route="legal_search",
    )


@pytest.mark.asyncio
async def test_v2_finalize_normalizes_partial_limitations(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import app.main as main_module

    request = QuestionRequest(question="전기사업 허가가 필요한가요?", answer_mode="terra")
    hit = _v2_hit()
    detail = _grounded_detail_response(hit)

    async def grounded_partial(_execution):
        return detail

    monkeypatch.setattr(main_module, "_v2_response_from_frozen_evidence", grounded_partial)
    result = await main_module._run_v2_finalize(
        SimpleNamespace(
            private_payload={
                "request": request.model_dump(mode="json"),
                "hits": [hit.model_dump(mode="json")],
                "route": "legal_search",
                "verified_core": {
                    "summary": hit.content,
                    "citation_ids": ["C1"],
                    "action": "partially_answerable",
                },
                "verified_core_citations": [],
            },
            frozen_citations=(FrozenCitation(id="C1", quote=hit.content),),
            status=main_module.ExecutionStatus.CORE_ANSWERED,
        ),
        None,
    )

    assert result.response is not None
    assert result.response["limitations"] == [
        "검색된 근거와 제공된 사실만으로 확인 가능한 범위의 답변입니다.",
        "이 서비스는 법률 자문을 대체하지 않습니다.",
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize("core_citation_ids", [[], ["C1"]])
async def test_v2_finalize_preserves_unanswerable_core_over_grounded_partial_detail(
    monkeypatch: pytest.MonkeyPatch,
    core_citation_ids: list[str],
) -> None:
    import app.main as main_module

    request = QuestionRequest(question="전기사업 허가가 필요한가요?", answer_mode="terra")
    hit = _v2_hit()
    detail = _grounded_detail_response(hit)

    async def grounded_partial(_execution):
        return detail

    monkeypatch.setattr(main_module, "_v2_response_from_frozen_evidence", grounded_partial)
    result = await main_module._run_v2_finalize(
        SimpleNamespace(
            private_payload={
                "request": request.model_dump(mode="json"),
                "hits": [hit.model_dump(mode="json")],
                "verified_core": {
                    "summary": "제공된 근거로 답할 수 없습니다.",
                    "citation_ids": core_citation_ids,
                    "action": "unanswerable",
                },
                "verified_core_citations": [],
            },
            frozen_citations=(FrozenCitation(id="C1", quote=hit.content),),
            status=main_module.ExecutionStatus.CORE_ANSWERED,
        ),
        None,
    )

    assert result.response is not None
    assert result.response["summary"] == (
        "검증된 법률 주장을 만들지 못했습니다. 인용된 공식 원문을 직접 확인해 주세요."
    )
    assert result.response["action"] == "unanswerable"
    assert result.response["sections"] == []
    assert result.response["checklist"] == []
    assert result.response["citations"] == []
    assert result.private_payload is None


@pytest.mark.asyncio
async def test_v2_finalize_preserves_routing_unavailable_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import app.main as main_module
    from app.application.answering import route_guidance_fallback

    request = QuestionRequest(question="전기사업 허가가 필요한가요?", answer_mode="terra")
    routed_response = route_guidance_fallback(request, "routing_unavailable")

    async def routing_unavailable(_execution):
        return routed_response

    monkeypatch.setattr(
        main_module, "_v2_response_from_frozen_evidence", routing_unavailable
    )
    result = await main_module._run_v2_finalize(
        SimpleNamespace(
            private_payload={
                "request": request.model_dump(mode="json"),
                "hits": [],
                "route": "routing_unavailable",
                "verified_core": {
                    "summary": routed_response.summary,
                    "citation_ids": [],
                    "action": "unanswerable",
                },
                "verified_core_citations": [],
            },
            frozen_citations=(),
            status=main_module.ExecutionStatus.CORE_ANSWERED,
        ),
        None,
    )

    assert result.response is not None
    assert result.response["route"] == "routing_unavailable"
    assert result.response["action"] == "unanswerable"
    assert result.response["citations"] == []


@pytest.mark.asyncio
async def test_v2_finalize_preserves_safe_clarification_fields(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import app.main as main_module
    from app.application.answering import route_guidance_fallback

    request = QuestionRequest(question="전기사업 허가가 필요한가요?", answer_mode="terra")
    routed_response = route_guidance_fallback(
        request,
        "clarification_required",
        missing_fields=("설비용량", "전기사업법이 적용됩니다"),
    )

    async def clarification_route(_execution):
        return routed_response

    monkeypatch.setattr(main_module, "_v2_response_from_frozen_evidence", clarification_route)
    result = await main_module._run_v2_finalize(
        SimpleNamespace(
            private_payload={
                "request": request.model_dump(mode="json"),
                "hits": [],
                "route": "clarification_required",
                "missing_fields": ["설비용량", "전기사업법이 적용됩니다"],
                "verified_core": {
                    "summary": routed_response.summary,
                    "citation_ids": [],
                    "action": "clarification_required",
                },
                "verified_core_citations": [],
            },
            frozen_citations=(),
            status=main_module.ExecutionStatus.CORE_ANSWERED,
        ),
        None,
    )

    assert result.response is not None
    assert result.response["route"] == "clarification_required"
    assert result.response["summary"].endswith("추가 정보:\n- 설비용량: [ ]")
    assert "전기사업법이 적용됩니다" not in result.response["summary"]


@pytest.mark.asyncio
async def test_v2_finalize_clears_detail_surfaces_for_clarification_core(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import app.main as main_module

    request = QuestionRequest(question="전기사업 허가가 필요한가요?", answer_mode="terra")
    hit = _v2_hit()
    detail = _grounded_detail_response(hit)

    async def grounded_partial(_execution):
        return detail

    monkeypatch.setattr(main_module, "_v2_response_from_frozen_evidence", grounded_partial)
    result = await main_module._run_v2_finalize(
        SimpleNamespace(
            private_payload={
                "request": request.model_dump(mode="json"),
                "hits": [hit.model_dump(mode="json")],
                "verified_core": {
                    "summary": (
                        "정확한 절차를 확인하려면 추가 정보가 필요합니다.\n"
                        "다음 메시지에는 아래 내용을 전체 복사한 뒤 [ ]를 채워 "
                        "한 번에 보내주세요.\n"
                        "추가 정보만 따로 보내지 마세요.\n\n"
                        "질문: 전기사업 허가가 필요한가요?\n추가 정보:\n- 설비용량: [ ]"
                    ),
                    "citation_ids": [],
                    "action": "clarification_required",
                    "missing_information": ["설비용량", "전기사업법이 적용됩니다"],
                },
                "verified_core_citations": [],
            },
            frozen_citations=(FrozenCitation(id="C1", quote=hit.content),),
            status=main_module.ExecutionStatus.CORE_ANSWERED,
        ),
        None,
    )

    assert result.response is not None
    assert result.response["action"] == "clarification_required"
    assert result.response["summary"].endswith("추가 정보:\n- 설비용량: [ ]")
    assert "전기사업법이 적용됩니다" not in result.response["summary"]
    assert result.response["sections"] == []
    assert result.response["checklist"] == []
    assert result.response["citations"] == []

@pytest.mark.asyncio
async def test_v2_finalize_rejects_semantically_unrelated_partial_detail(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import app.main as main_module

    request = QuestionRequest(question="전기사업 허가가 필요한가요?", answer_mode="terra")
    hit = _v2_hit()
    detail = _grounded_detail_response(hit)
    unrelated = "환경부 승인을 받으면 사업할 수 있습니다."
    detail.summary = unrelated
    detail.sections[0].claim = unrelated
    detail.sections[0].explanation = unrelated
    detail.checklist[0].label = "관할 기관에 신청서를 내면 됩니다."

    async def unrelated_partial(_execution):
        return detail

    monkeypatch.setattr(main_module, "_v2_response_from_frozen_evidence", unrelated_partial)
    result = await main_module._run_v2_finalize(
        SimpleNamespace(
            private_payload={
                "request": request.model_dump(mode="json"),
                "hits": [hit.model_dump(mode="json")],
                "verified_core": {
                    "summary": "제공된 근거로 답할 수 없습니다.",
                    "citation_ids": ["C1"],
                    "action": "unanswerable",
                },
                "verified_core_citations": [],
            },
            frozen_citations=(FrozenCitation(id="C1", quote=hit.content),),
            status=main_module.ExecutionStatus.CORE_ANSWERED,
        ),
        None,
    )

    assert result.response is not None
    assert result.response["summary"] == (
        "검증된 법률 주장을 만들지 못했습니다. 인용된 공식 원문을 직접 확인해 주세요."
    )
    assert result.response["action"] == "unanswerable"
    assert result.response["sections"] == []
    assert result.response["checklist"] == []
    assert result.response["citations"] == []
    assert result.private_payload is None

@pytest.mark.asyncio
@pytest.mark.parametrize("detail_action", ["fully_answerable", "unanswerable"])
async def test_v2_finalize_does_not_promote_other_detail_actions_over_unanswerable_core(
    monkeypatch: pytest.MonkeyPatch,
    detail_action: str,
) -> None:
    import app.main as main_module

    request = QuestionRequest(question="전기사업 허가가 필요한가요?", answer_mode="terra")
    hit = _v2_hit()
    detail = _grounded_detail_response(hit, action=detail_action)

    async def grounded_detail(_execution):
        return detail

    monkeypatch.setattr(main_module, "_v2_response_from_frozen_evidence", grounded_detail)
    result = await main_module._run_v2_finalize(
        SimpleNamespace(
            private_payload={
                "request": request.model_dump(mode="json"),
                "hits": [hit.model_dump(mode="json")],
                "verified_core": {
                    "summary": "제공된 근거로 답할 수 없습니다.",
                    "citation_ids": [],
                    "action": "unanswerable",
                },
                "verified_core_citations": [],
            },
            frozen_citations=(FrozenCitation(id="C1", quote=hit.content),),
            status=main_module.ExecutionStatus.CORE_ANSWERED,
        ),
        None,
    )

    assert result.response is not None
    assert result.response["summary"] == (
        "검증된 법률 주장을 만들지 못했습니다. 인용된 공식 원문을 직접 확인해 주세요."
    )
    assert result.response["action"] == "unanswerable"
    assert result.response["sections"] == []
    assert result.response["checklist"] == []
    assert result.response["citations"] == []
    assert result.private_payload is None


def test_prepare_core_finalize_replays_authoritative_phase_events(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import app.main as main_module
    from app.adapters.memory_question_execution import MemoryQuestionExecutionRepository

    async def fake_repository():
        return object()

    async def fake_retrieval(payload, active, repository):
        return [], None

    class Provider:
        async def active(self):
            return SimpleNamespace(generation=SimpleNamespace(id=uuid4()))

    monkeypatch.setattr(
        main_module,
        "question_execution_repository",
        MemoryQuestionExecutionRepository(),
    )
    monkeypatch.setattr(main_module, "_v2_repository", fake_repository)
    monkeypatch.setattr(main_module, "_require_supported_as_of_date", _allow_supported_date)
    monkeypatch.setattr(main_module, "_retrieve_pinned_v2_evidence", fake_retrieval)
    monkeypatch.setattr(
        main_module, "_llamaindex_resources", lambda: (Provider(), object(), object())
    )
    client = TestClient(main_module.app)

    prepared = client.post(
        "/v2/question-executions",
        headers={"Idempotency-Key": "prepare-key"},
        json={"question": "전기사업 허가가 필요한가요?", "answer_mode": "search_only"},
    )
    assert prepared.status_code == 200
    assert prepared.json()["next_action"] == "generate_core"

    execution_id = prepared.json()["execution_id"]
    capability_headers = {"X-Execution-Capability": prepared.json()["execution_capability"]}
    core = client.post(f"/v2/question-executions/{execution_id}/core", headers=capability_headers)
    core_replay = client.post(
        f"/v2/question-executions/{execution_id}/core", headers=capability_headers
    )
    finalized = client.post(
        f"/v2/question-executions/{execution_id}/finalize", headers=capability_headers
    )
    finalize_replay = client.post(
        f"/v2/question-executions/{execution_id}/finalize", headers=capability_headers
    )

    assert core.headers["content-type"].startswith("text/event-stream")
    assert "event: summary" in core.text
    assert '"next_action": "generate_detail"' in core.text
    assert core_replay.text == core.text
    assert "event: complete" in finalized.text
    assert finalize_replay.text == finalized.text


def test_v2_phase_routes_invoke_main_compatibility_producers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """HTTP phase routes keep the documented main-module monkeypatch seams."""

    import app.main as main_module
    from app.adapters.memory_question_execution import MemoryQuestionExecutionRepository

    async def fake_repository():
        return object()

    async def fake_retrieval(payload, active, repository):
        return [], None

    class Provider:
        async def active(self):
            return SimpleNamespace(generation=SimpleNamespace(id=uuid4()))

    invoked: list[str] = []

    async def fake_core(execution):
        invoked.append("core")
        return PhaseResult(
            target=ExecutionStatus.CORE_ANSWERED,
            events=(
                AnswerEvent(event_type="summary", payload={"summary": "확인된 요약"}),
                AnswerEvent(
                    event_type="phase_complete",
                    payload={
                        "status": ExecutionStatus.CORE_ANSWERED.value,
                        "next_action": "generate_detail",
                    },
                ),
            ),
        )

    async def fake_finalize(execution, user):
        invoked.append("finalize")
        return PhaseResult(
            target=ExecutionStatus.COMPLETED,
            response={"request_id": "seam", "mode": "search_only"},
            events=(
                AnswerEvent.complete(
                    {
                        "response": {"request_id": "seam", "mode": "search_only"},
                        "outcome": "normal",
                    }
                ),
            ),
        )

    monkeypatch.setattr(
        main_module,
        "question_execution_repository",
        MemoryQuestionExecutionRepository(),
    )
    monkeypatch.setattr(main_module, "_v2_repository", fake_repository)
    monkeypatch.setattr(main_module, "_require_supported_as_of_date", _allow_supported_date)
    monkeypatch.setattr(main_module, "_retrieve_pinned_v2_evidence", fake_retrieval)
    monkeypatch.setattr(
        main_module, "_llamaindex_resources", lambda: (Provider(), object(), object())
    )
    monkeypatch.setattr(main_module, "_run_v2_core", fake_core)
    monkeypatch.setattr(main_module, "_run_v2_finalize", fake_finalize)
    client = TestClient(main_module.app)

    prepared = client.post(
        "/v2/question-executions",
        headers={"Idempotency-Key": "phase-seams"},
        json={"question": "전기사업 허가가 필요한가요?", "answer_mode": "search_only"},
    )
    execution_id = prepared.json()["execution_id"]
    headers = {"X-Execution-Capability": prepared.json()["execution_capability"]}

    core = client.post(f"/v2/question-executions/{execution_id}/core", headers=headers)
    finalized = client.post(f"/v2/question-executions/{execution_id}/finalize", headers=headers)

    assert core.status_code == finalized.status_code == 200
    assert invoked == ["core", "finalize"]


def test_prepare_replay_does_not_retrieve_again_and_anonymous_phase_requires_capability(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import app.main as main_module
    from app.adapters.memory_question_execution import MemoryQuestionExecutionRepository

    calls = 0

    async def fake_repository():
        return object()

    async def fake_retrieval(payload, active, repository):
        nonlocal calls
        calls += 1
        return [], None

    class Provider:
        async def active(self):
            return SimpleNamespace(generation=SimpleNamespace(id=uuid4()))

    monkeypatch.setattr(
        main_module,
        "question_execution_repository",
        MemoryQuestionExecutionRepository(),
    )
    monkeypatch.setattr(main_module, "_v2_repository", fake_repository)
    monkeypatch.setattr(main_module, "_require_supported_as_of_date", _allow_supported_date)
    monkeypatch.setattr(main_module, "_retrieve_pinned_v2_evidence", fake_retrieval)
    monkeypatch.setattr(
        main_module, "_llamaindex_resources", lambda: (Provider(), object(), object())
    )
    client = TestClient(main_module.app)
    request = {"question": "전기사업 허가가 필요한가요?", "answer_mode": "search_only"}

    first = client.post(
        "/v2/question-executions", headers={"Idempotency-Key": "once"}, json=request
    )
    replay = client.post(
        "/v2/question-executions", headers={"Idempotency-Key": "once"}, json=request
    )
    forbidden = client.post(f"/v2/question-executions/{first.json()['execution_id']}/core")

    assert first.status_code == replay.status_code == 200
    assert first.json()["execution_id"] == replay.json()["execution_id"]
    assert first.json()["execution_capability"] == replay.json()["execution_capability"]
    assert calls == 1
    assert forbidden.status_code == 404


def test_provider_capacity_rejection_is_an_http_503_before_the_phase_stream(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import app.main as main_module
    from app.adapters.memory_question_execution import MemoryQuestionExecutionRepository

    async def fake_repository():
        return object()

    async def fake_retrieval(payload, active, repository):
        return [], None

    class Provider:
        async def active(self):
            return SimpleNamespace(generation=SimpleNamespace(id=uuid4()))

    async def busy_admission(*args, **kwargs):
        from fastapi import HTTPException

        raise HTTPException(status_code=503, detail="system_busy")

    monkeypatch.setattr(
        main_module,
        "question_execution_repository",
        MemoryQuestionExecutionRepository(),
    )
    monkeypatch.setattr(main_module, "_admit_v2_provider_phase", busy_admission)
    monkeypatch.setattr(main_module, "_ai_available", lambda: True)
    monkeypatch.setattr(main_module, "_v2_repository", fake_repository)
    monkeypatch.setattr(main_module, "_require_supported_as_of_date", _allow_supported_date)
    monkeypatch.setattr(
        main_module,
        "route_question",
        _legal_search_route,
    )
    monkeypatch.setattr(main_module, "_retrieve_pinned_v2_evidence", fake_retrieval)
    monkeypatch.setattr(
        main_module, "_llamaindex_resources", lambda: (Provider(), object(), object())
    )
    client = TestClient(main_module.app)
    prepared = client.post(
        "/v2/question-executions",
        headers={"Idempotency-Key": "busy"},
        json={"question": "전기사업 허가가 필요한가요?", "answer_mode": "terra"},
    )

    response = client.post(
        f"/v2/question-executions/{prepared.json()['execution_id']}/core",
        headers={"X-Execution-Capability": prepared.json()["execution_capability"]},
    )

    assert response.status_code == 503
    assert response.json()["detail"] == "system_busy"
