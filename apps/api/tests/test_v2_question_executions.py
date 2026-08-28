from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient


async def _allow_supported_date(*args) -> None:
    return None


async def _legal_search_route(*args):
    return SimpleNamespace(route="legal_search", missing_fields=())


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


def test_obsolete_v2_single_question_route_is_removed() -> None:
    import app.main as main_module

    response = TestClient(main_module.app).post(
        "/v2/questions",
        json={"question": "전기사업 허가가 필요한가요?"},
    )

    assert response.status_code == 404


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
