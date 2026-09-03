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
from app.domain.schemas import AnswerSection, QuestionRequest, SearchHit


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
                    event_type="phase_complete", payload={"next_action": "generate_detail"}
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
                    {"label": "원문을 확인하세요.", "status": "check", "citation_ids": ["C1"]}
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
    assert result.events[0].payload["outcome"] == "degraded"


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
        main_module, "question_execution_repository", MemoryQuestionExecutionRepository()
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
        main_module, "question_execution_repository", MemoryQuestionExecutionRepository()
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
        main_module, "question_execution_repository", MemoryQuestionExecutionRepository()
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
        main_module, "question_execution_repository", MemoryQuestionExecutionRepository()
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
