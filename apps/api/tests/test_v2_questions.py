import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    import app.main as main_module

    monkeypatch.setattr(main_module, "llamaindex_repository", object())

    async def fake_ready() -> bool:
        return True

    async def fake_supported_as_of_date(requested_date, repository) -> None:
        return None

    monkeypatch.setattr(main_module, "_v2_index_ready", fake_ready)
    monkeypatch.setattr(main_module, "_require_supported_as_of_date", fake_supported_as_of_date)
    return TestClient(main_module.app)


def test_v2_questions_returns_503_when_not_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    import app.main as main_module

    monkeypatch.setattr(main_module, "llamaindex_repository", None)
    client = TestClient(main_module.app)
    response = client.post(
        "/v2/questions",
        json={
            "client_request_id": "11111111-1111-1111-1111-111111111111",
            "question": "태양광 설비 인허가 요건이 뭐야",
            "as_of_date": "2026-01-01",
            "project_stage": "planning",
            "answer_mode": "search_only",
        },
    )
    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "v2_search_not_ready"


def test_v2_questions_returns_503_when_index_is_not_ready(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import app.main as main_module

    monkeypatch.setattr(main_module, "llamaindex_repository", object())

    async def fake_not_ready() -> bool:
        return False

    monkeypatch.setattr(main_module, "_v2_index_ready", fake_not_ready)
    client = TestClient(main_module.app)
    response = client.post(
        "/v2/questions",
        json={
            "client_request_id": "11111111-1111-1111-1111-111111111111",
            "question": "태양광 설비 인허가 요건이 뭐야",
            "as_of_date": "2026-01-01",
            "project_stage": "planning",
            "answer_mode": "search_only",
        },
    )
    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "v2_search_not_ready"


def test_v2_questions_uses_llamaindex_repository_for_evidence(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    import app.main as main_module
    from app.domain.schemas import QuestionResponse

    captured_repository = {}

    async def fake_answer_question(payload, request, user, budget, repository):
        captured_repository["repository"] = repository
        return QuestionResponse(
            request_id=str(payload.client_request_id),
            mode="search_only",
            summary="ok",
            scope="",
            sections=[],
            checklist=[],
            citations=[],
            limitations=[],
            fallback_reason=None,
        )

    monkeypatch.setattr(main_module, "_answer_question", fake_answer_question)

    response = client.post(
        "/v2/questions",
        json={
            "client_request_id": "11111111-1111-1111-1111-111111111111",
            "question": "태양광 설비 인허가 요건이 뭐야",
            "as_of_date": "2026-01-01",
            "project_stage": "planning",
            "answer_mode": "search_only",
        },
    )
    assert response.status_code == 200
    assert captured_repository["repository"] is main_module.llamaindex_repository
