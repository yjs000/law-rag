from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

import app.main as main_module
from app.adapters.postgres_identity import ConsentRequiredError
from app.adapters.supabase_auth import (
    SupabaseAuthError,
    SupabaseAuthUnavailableError,
    SupabaseIdentity,
)
from app.domain.schemas import MockUser, QuestionHistoryEntry

OWNER_AUTH_ID = UUID("11111111-1111-4111-8111-111111111111")
STRANGER_AUTH_ID = UUID("22222222-2222-4222-8222-222222222222")
OWNER_ID = UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
STRANGER_ID = UUID("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb")


class FakeSupabaseAuth:
    def __init__(self) -> None:
        self.identities = {
            "owner-token": self._identity(OWNER_AUTH_ID, "owner@example.com"),
            "stranger-token": self._identity(STRANGER_AUTH_ID, "stranger@example.com"),
        }
        self.deleted: list[UUID] = []

    @staticmethod
    def _identity(auth_user_id: UUID, email: str) -> SupabaseIdentity:
        return SupabaseIdentity(
            auth_user_id=auth_user_id,
            email=email,
            display_name=email.split("@", 1)[0],
            created_at=datetime(2026, 7, 15, tzinfo=UTC),
        )

    async def verify_user(self, token: str) -> SupabaseIdentity:
        if token == "provider-down":
            raise SupabaseAuthUnavailableError
        try:
            return self.identities[token]
        except KeyError as exc:
            raise SupabaseAuthError from exc

    async def delete_user(self, user_id: UUID) -> None:
        self.deleted.append(user_id)
        self.identities = {
            token: identity
            for token, identity in self.identities.items()
            if identity.auth_user_id != user_id
        }


class FakePostgresIdentity:
    def __init__(self) -> None:
        self.users: dict[UUID, MockUser] = {}
        self.consented: set[UUID] = set()
        self.history: dict[UUID, QuestionHistoryEntry] = {}

    async def ensure_profile(
        self,
        identity: SupabaseIdentity,
        terms_version: str | None = None,
        privacy_version: str | None = None,
    ) -> MockUser:
        if identity.auth_user_id not in self.consented:
            if not terms_version or not privacy_version:
                raise ConsentRequiredError
            self.consented.add(identity.auth_user_id)
        user = self.users.get(identity.auth_user_id)
        if user is None:
            user = MockUser(
                id=OWNER_ID if identity.auth_user_id == OWNER_AUTH_ID else STRANGER_ID,
                email=identity.email,
                display_name=identity.display_name,
                created_at=identity.created_at,
            )
            self.users[identity.auth_user_id] = user
        return user

    async def consume_quota(self, *_: object) -> bool:
        return True

    async def save_question(self, user_id, request, response, diagnostics=None) -> None:
        entry = QuestionHistoryEntry(
            id=UUID(response.request_id),
            user_id=user_id,
            request=request,
            response=response,
            created_at=datetime(2026, 7, 15, tzinfo=UTC),
            expires_at=datetime(2027, 7, 15, tzinfo=UTC),
        )
        self.history[entry.id] = entry

    async def list_history(self, user_id: UUID) -> list[QuestionHistoryEntry]:
        return [entry for entry in self.history.values() if entry.user_id == user_id]

    async def get_history(self, history_id: UUID, user_id: UUID):
        entry = self.history.get(history_id)
        return entry if entry and entry.user_id == user_id else None

    async def delete_history(self, history_id: UUID, user_id: UUID) -> bool:
        if await self.get_history(history_id, user_id) is None:
            return False
        del self.history[history_id]
        return True

    async def auth_user_id(self, user_id: UUID) -> UUID:
        return OWNER_AUTH_ID if user_id == OWNER_ID else STRANGER_AUTH_ID

    async def delete_account_data(self, user_id: UUID) -> None:
        auth_ids = [auth_id for auth_id, user in self.users.items() if user.id == user_id]
        for auth_id in auth_ids:
            del self.users[auth_id]
            self.consented.discard(auth_id)
        self.history = {
            history_id: entry
            for history_id, entry in self.history.items()
            if entry.user_id != user_id
        }


@pytest.fixture
def supabase_flow(monkeypatch):
    auth = FakeSupabaseAuth()
    identity = FakePostgresIdentity()
    monkeypatch.setattr(main_module, "supabase_auth", auth)
    monkeypatch.setattr(main_module, "postgres_identity", identity)
    return TestClient(main_module.app), auth, identity


def _headers(token: str, *, consent: bool = False) -> dict[str, str]:
    headers = {"Authorization": f"Bearer {token}"}
    if consent:
        headers.update(
            {
                "X-Terms-Version": "beta-2026-07-15",
                "X-Privacy-Version": "beta-2026-07-15",
            }
        )
    return headers


def test_fake_supabase_signup_requires_exact_complete_consent(supabase_flow) -> None:
    client, _, _ = supabase_flow

    assert client.get("/v1/auth/me", headers=_headers("owner-token")).status_code == 409
    assert (
        client.get(
            "/v1/auth/me",
            headers={
                **_headers("owner-token"),
                "X-Terms-Version": "forged-version",
                "X-Privacy-Version": "beta-2026-07-15",
            },
        ).status_code
        == 409
    )
    assert (
        client.get(
            "/v1/auth/me",
            headers={**_headers("owner-token"), "X-Terms-Version": "beta-2026-07-15"},
        ).status_code
        == 409
    )
    assert (
        client.get("/v1/auth/me", headers=_headers("owner-token", consent=True)).status_code == 200
    )
    assert client.get("/v1/auth/me", headers=_headers("owner-token")).status_code == 200


def test_invalid_expired_and_unavailable_sessions_are_fail_closed(supabase_flow) -> None:
    client, _, _ = supabase_flow

    assert client.get("/v1/auth/me", headers=_headers("expired-token")).status_code == 401
    assert client.post("/v1/auth/logout", headers=_headers("expired-token")).status_code == 401
    assert client.get("/v1/auth/me", headers=_headers("provider-down")).status_code == 503
    assert (
        client.get(
            "/v1/auth/me",
            headers={
                **_headers("expired-token"),
                "X-Terms-Version": "forged-version",
                "X-Privacy-Version": "forged-version",
            },
        ).status_code
        == 401
    )
    for value in ("Bearer", "Bearer   ", "Bearer two tokens", "Basic owner-token"):
        assert client.get("/v1/auth/me", headers={"Authorization": value}).status_code == 401


def test_fake_supabase_history_is_owner_scoped_and_account_delete_cascades(
    supabase_flow,
) -> None:
    client, auth, identity = supabase_flow
    owner_headers = _headers("owner-token", consent=True)
    stranger_headers = _headers("stranger-token", consent=True)
    assert client.get("/v1/auth/me", headers=owner_headers).status_code == 200
    assert client.get("/v1/auth/me", headers=stranger_headers).status_code == 200

    answer = client.post(
        "/v1/questions",
        headers={**_headers("owner-token"), "Content-Type": "application/json"},
        json={
            "question": "가짜 사용자 ID로 소유권을 확인합니다",
            "as_of_date": "2026-07-15",
            "project_stage": "planning",
        },
    )
    assert answer.status_code == 200
    history_id = answer.json()["request_id"]
    assert len(client.get("/v1/questions/history", headers=_headers("owner-token")).json()) == 1
    assert (
        client.get(
            f"/v1/questions/history/{history_id}", headers=_headers("stranger-token")
        ).status_code
        == 404
    )
    assert (
        client.delete(
            f"/v1/questions/history/{history_id}", headers=_headers("stranger-token")
        ).status_code
        == 404
    )

    assert client.delete("/v1/account", headers=_headers("owner-token")).status_code == 204
    assert auth.deleted == [OWNER_AUTH_ID]
    assert OWNER_AUTH_ID not in identity.users
    assert identity.history == {}
    assert client.get("/v1/auth/me", headers=_headers("owner-token")).status_code == 401
    assert client.get("/v1/auth/me", headers=_headers("stranger-token")).status_code == 200
