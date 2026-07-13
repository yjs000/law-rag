from datetime import UTC, date, datetime, timedelta
from uuid import uuid4

from fastapi.testclient import TestClient

import app.main as main_module
from app.adapters.mock_identity import MockIdentityRepository, identity_repository
from app.application.answering import search_only_answer
from app.domain.schemas import ProjectStage, QuestionRequest
from app.main import app

client = TestClient(app)


def setup_function() -> None:
    identity_repository.clear()


def _login(email: str = "user@example.com") -> tuple[str, dict]:
    response = client.post(
        "/v1/auth/mock/google",
        json={"email": email, "display_name": "테스트 사용자"},
    )
    assert response.status_code == 200
    payload = response.json()
    return payload["access_token"], payload["user"]


def _ask(token: str | None = None) -> dict:
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    response = client.post(
        "/v1/questions",
        headers=headers,
        json={
            "question": "근거가 없는 질문입니다",
            "as_of_date": "2026-07-13",
            "project_stage": "planning",
        },
    )
    assert response.status_code == 200
    return response.json()


def test_anonymous_question_is_not_saved_but_authenticated_question_is() -> None:
    _ask()
    token, _ = _login()
    assert client.get(
        "/v1/questions/history", headers={"Authorization": f"Bearer {token}"}
    ).json() == []

    answer = _ask(token)
    history = client.get(
        "/v1/questions/history", headers={"Authorization": f"Bearer {token}"}
    ).json()
    assert len(history) == 1
    assert history[0]["id"] == answer["request_id"]
    assert history[0]["response"] == answer


def test_history_is_private_and_owner_can_delete_it() -> None:
    owner_token, _ = _login("owner@example.com")
    stranger_token, _ = _login("stranger@example.com")
    history_id = _ask(owner_token)["request_id"]
    stranger_headers = {"Authorization": f"Bearer {stranger_token}"}

    assert client.get(
        f"/v1/questions/history/{history_id}", headers=stranger_headers
    ).status_code == 404
    assert client.delete(
        f"/v1/questions/history/{history_id}", headers=stranger_headers
    ).status_code == 404

    owner_headers = {"Authorization": f"Bearer {owner_token}"}
    assert client.delete(
        f"/v1/questions/history/{history_id}", headers=owner_headers
    ).status_code == 204
    assert client.get(
        f"/v1/questions/history/{history_id}", headers=owner_headers
    ).status_code == 404


def test_logout_invalidates_session_and_account_delete_cascades() -> None:
    token, _ = _login()
    history_id = _ask(token)["request_id"]
    headers = {"Authorization": f"Bearer {token}"}
    assert client.get(
        f"/v1/questions/history/{history_id}/checklist", headers=headers
    ).status_code == 200

    assert client.delete("/v1/account", headers=headers).status_code == 204
    assert client.get("/v1/auth/me", headers=headers).status_code == 401
    new_token, _ = _login()
    assert client.get(
        "/v1/questions/history", headers={"Authorization": f"Bearer {new_token}"}
    ).json() == []

    logout = client.post(
        "/v1/auth/logout", headers={"Authorization": f"Bearer {new_token}"}
    )
    assert logout.status_code == 204
    assert client.get(
        "/v1/auth/me", headers={"Authorization": f"Bearer {new_token}"}
    ).status_code == 401


def test_history_expires_exactly_one_year_after_creation() -> None:
    repository = MockIdentityRepository()
    created_at = datetime(2025, 7, 13, 9, tzinfo=UTC)
    _, user = repository.login_google("user@example.com", "사용자", now=created_at)
    request = QuestionRequest(
        question="질문입니다",
        as_of_date=date(2025, 7, 13),
        project_stage=ProjectStage.PLANNING,
    )
    response = search_only_answer(request, [])
    entry = repository.save_question(user.id, request, response, now=created_at)

    assert repository.get_history(
        entry.id, user.id, now=created_at + timedelta(days=365) - timedelta(microseconds=1)
    ) is not None
    assert repository.get_history(
        entry.id, user.id, now=created_at + timedelta(days=365)
    ) is None


def test_leap_day_history_and_export_metadata_expire_at_next_february_end() -> None:
    repository = MockIdentityRepository()
    created_at = datetime(2024, 2, 29, 9, tzinfo=UTC)
    _, user = repository.login_google("leap@example.com", "사용자", now=created_at)
    request = QuestionRequest(question="질문입니다", as_of_date=date(2024, 2, 29))
    response = search_only_answer(request, [])
    entry = repository.save_question(user.id, request, response, now=created_at)
    repository.record_export(user.id, entry.id, "pdf")

    assert entry.expires_at == datetime(2025, 2, 28, 9, tzinfo=UTC)
    assert repository.purge_expired(now=entry.expires_at) == 1
    assert repository._related_data[user.id]["exports"] == []


def test_unknown_or_missing_session_is_rejected() -> None:
    assert client.get("/v1/auth/me").status_code == 401
    assert client.get(
        "/v1/auth/me", headers={"Authorization": f"Bearer {uuid4()}"}
    ).status_code == 401


def test_mock_auth_is_disabled_in_production(monkeypatch) -> None:
    monkeypatch.setattr(main_module.settings, "environment", "production")
    response = client.post(
        "/v1/auth/mock/google",
        json={"email": "user@example.com", "display_name": "사용자"},
    )
    assert response.status_code == 404
