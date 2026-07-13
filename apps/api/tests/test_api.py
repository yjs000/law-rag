from fastapi.testclient import TestClient

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
    assert any("근거를 찾지 못했습니다" in item for item in payload["limitations"])
