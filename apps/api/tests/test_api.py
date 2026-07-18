import pytest
from fastapi.testclient import TestClient

import app.main as main_module
from app.adapters.memory_repository import MemoryLegalRepository
from app.main import app


def test_health_exposes_no_secrets() -> None:
    response = TestClient(app).get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_question_without_corpus_returns_safe_search_only_response() -> None:
    response = TestClient(app).post(
        "/v1/questions",
        json={
            "question": "근거가 없는 질문입니다",
            "as_of_date": "2026-07-13",
            "project_stage": "planning",
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["mode"] == "search_only"
    assert payload["citations"] == []
    assert payload["result_status"] == "no_results"
    assert payload["no_results_reason"] == "no_matching_evidence"
    assert any("근거를 찾지 못했습니다" in item for item in payload["limitations"])


def test_anonymous_question_search_failure_returns_safe_temporary_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = MemoryLegalRepository()

    async def fail_search(*args, **kwargs):
        raise RuntimeError("database host and credentials must stay private")

    monkeypatch.setattr(repository, "search_with_trace", fail_search)
    monkeypatch.setattr(main_module, "repository", repository)
    response = TestClient(app, raise_server_exceptions=False).post(
        "/v1/questions",
        json={
            "question": "가짜 익명 질문",
            "as_of_date": "2026-07-15",
            "project_stage": "planning",
            "answer_mode": "search_only",
        },
    )

    assert response.status_code == 503
    assert response.json() == {"detail": "법령 검색을 일시적으로 사용할 수 없습니다."}
    assert "database host" not in response.text


def test_direct_search_failure_returns_the_same_safe_temporary_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = MemoryLegalRepository()

    async def fail_search(*args, **kwargs):
        raise RuntimeError("database host and credentials must stay private")

    monkeypatch.setattr(repository, "search", fail_search)
    monkeypatch.setattr(main_module, "repository", repository)
    response = TestClient(app, raise_server_exceptions=False).post(
        "/v1/search",
        json={"query": "가짜 익명 검색", "as_of_date": "2026-07-15"},
    )

    assert response.status_code == 503
    assert response.json() == {"detail": "법령 검색을 일시적으로 사용할 수 없습니다."}
    assert "database host" not in response.text
