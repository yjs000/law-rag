from __future__ import annotations

import sys
from collections.abc import Callable
from time import perf_counter
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from httpx import Response

from app.adapters.mock_identity import identity_repository
from app.main import app

pytestmark = pytest.mark.usefixtures("ready_corpus_temporal_state")

MAX_RESPONSE_SECONDS = 1.0


def assert_under_one_second(label: str, call: Callable[[], Response]) -> Response:
    started_at = perf_counter()
    response = call()
    elapsed = perf_counter() - started_at
    assert elapsed < MAX_RESPONSE_SECONDS, f"{label} took {elapsed:.3f}s"
    return response


def setup_function() -> None:
    identity_repository.clear()


def _login(client: TestClient, email: str) -> tuple[str, dict[str, object]]:
    response = client.post(
        "/v1/auth/mock/google",
        json={"email": email, "display_name": "지연 테스트 사용자"},
    )
    assert response.status_code == 200
    payload = response.json()
    return payload["access_token"], payload["user"]


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _seed_question(client: TestClient, token: str) -> dict[str, object]:
    response = client.post(
        "/v1/questions",
        headers=_headers(token),
        json={"question": "전기사업 허가 근거", "answer_mode": "search_only"},
    )
    assert response.status_code == 200
    return response.json()


def test_every_non_model_endpoint_responds_within_one_second() -> None:
    client = TestClient(app)
    token, _ = _login(client, "latency-owner@example.com")
    seeded = _seed_question(client, token)
    headers = _headers(token)
    history_id = str(seeded["request_id"])
    conversation_id = str(seeded["conversation_id"])
    today = "2026-08-09"

    calls: list[tuple[str, Callable[[], Response], set[int]]] = [
        ("GET /health", lambda: client.get("/health"), {200}),
        (
            "POST /v1/questions/{id}/cancel",
            lambda: client.post(f"/v1/questions/{uuid4()}/cancel"),
            {404},
        ),
        (
            "POST /v1/auth/mock/google",
            lambda: client.post(
                "/v1/auth/mock/google",
                json={"email": "measured-login@example.com", "display_name": "측정 사용자"},
            ),
            {200},
        ),
        ("GET /v1/auth/me", lambda: client.get("/v1/auth/me", headers=headers), {200}),
        (
            "GET /v1/questions/history",
            lambda: client.get("/v1/questions/history", headers=headers),
            {200},
        ),
        (
            "GET /v1/conversations",
            lambda: client.get("/v1/conversations", headers=headers),
            {200},
        ),
        (
            "GET /v1/conversations/{id}/turns",
            lambda: client.get(
                f"/v1/conversations/{conversation_id}/turns", headers=headers
            ),
            {200},
        ),
        (
            "GET /v1/questions/history/{id}",
            lambda: client.get(f"/v1/questions/history/{history_id}", headers=headers),
            {200},
        ),
        (
            "GET /v1/questions/history/{id}/checklist",
            lambda: client.get(
                f"/v1/questions/history/{history_id}/checklist", headers=headers
            ),
            {200},
        ),
        (
            "GET /v1/provisions/{id}",
            lambda: client.get(f"/v1/provisions/{uuid4()}", params={"as_of_date": today}),
            {404},
        ),
        (
            "GET /v1/documents/{id}/changes",
            lambda: client.get(
                f"/v1/documents/{uuid4()}/changes",
                params={"from_date": "2026-01-01", "to_date": today},
            ),
            {200},
        ),
        ("GET /v1/corpus/status", lambda: client.get("/v1/corpus/status"), {200}),
    ]

    for label, call, expected_statuses in calls:
        response = assert_under_one_second(label, call)
        assert response.status_code in expected_statuses, label

    delete_token, _ = _login(client, "delete-latency@example.com")
    assert_under_one_second(
        "DELETE /v1/account",
        lambda: client.delete("/v1/account", headers=_headers(delete_token)),
    )
    logout_token, _ = _login(client, "logout-latency@example.com")
    assert_under_one_second(
        "POST /v1/auth/logout",
        lambda: client.post("/v1/auth/logout", headers=_headers(logout_token)),
    )
    delete_history_seed = _seed_question(client, token)
    assert_under_one_second(
        "DELETE /v1/questions/history/{id}",
        lambda: client.delete(
            f"/v1/questions/history/{delete_history_seed['request_id']}", headers=headers
        ),
    )
    assert_under_one_second(
        "DELETE /v1/conversations/{id}",
        lambda: client.delete(f"/v1/conversations/{conversation_id}", headers=headers),
    )


def test_latency_gate_rejects_an_endpoint_over_one_second(monkeypatch: pytest.MonkeyPatch) -> None:
    ticks = iter((10.0, 11.001))
    monkeypatch.setattr(sys.modules[__name__], "perf_counter", lambda: next(ticks))

    with pytest.raises(AssertionError, match="GET /health took 1.001s"):
        assert_under_one_second("GET /health", lambda: Response(200))
