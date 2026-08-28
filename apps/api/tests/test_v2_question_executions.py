from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient


def test_v2_prepare_requires_an_idempotency_key() -> None:
    import app.main as main_module

    response = TestClient(main_module.app).post(
        "/v2/question-executions",
        json={"question": "전기사업 허가가 필요한가요?"},
    )

    assert response.status_code == 422


def test_obsolete_v2_single_question_route_is_removed() -> None:
    import app.main as main_module

    response = TestClient(main_module.app).post(
        "/v2/questions",
        json={"question": "전기사업 허가가 필요한가요?"},
    )

    assert response.status_code == 404


def test_prepare_then_core_replays_the_same_authoritative_complete(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import app.main as main_module
    from app.adapters.memory_question_execution import MemoryQuestionExecutionRepository

    async def fake_repository():
        return object()

    async def fake_retrieval(payload, query_embedding, repository):
        return [], None, None

    class Provider:
        async def active(self):
            return SimpleNamespace(generation=SimpleNamespace(id=uuid4()))

    monkeypatch.setattr(
        main_module, "question_execution_repository", MemoryQuestionExecutionRepository()
    )
    monkeypatch.setattr(main_module, "_v2_repository", fake_repository)
    monkeypatch.setattr(main_module, "_retrieve_question_evidence", fake_retrieval)
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
    core = client.post(f"/v2/question-executions/{execution_id}/core")
    replay = client.post(f"/v2/question-executions/{execution_id}/core")

    assert core.headers["content-type"].startswith("text/event-stream")
    assert "event: complete" in core.text
    assert replay.text == core.text
