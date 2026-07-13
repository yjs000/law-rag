from __future__ import annotations

import secrets
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID, uuid4

from app.domain.schemas import MockUser, QuestionHistoryEntry, QuestionRequest, QuestionResponse


@dataclass(frozen=True)
class MockSession:
    token: str
    user_id: UUID


class MockIdentityRepository:
    """개발·테스트에서만 사용하는 프로세스 메모리 인증/이력 저장소."""

    def __init__(self) -> None:
        self._users: dict[UUID, MockUser] = {}
        self._users_by_email: dict[str, UUID] = {}
        self._sessions: dict[str, MockSession] = {}
        self._history: dict[UUID, QuestionHistoryEntry] = {}
        self._related_data: dict[UUID, dict[str, list[object]]] = {}

    def login_google(
        self, email: str, display_name: str, *, now: datetime | None = None
    ) -> tuple[str, MockUser]:
        normalized_email = email.strip().casefold()
        user_id = self._users_by_email.get(normalized_email)
        if user_id is None:
            user = MockUser(
                id=uuid4(),
                email=normalized_email,
                display_name=display_name.strip(),
                created_at=now or datetime.now(UTC),
            )
            self._users[user.id] = user
            self._users_by_email[normalized_email] = user.id
            self._related_data[user.id] = {
                "exports": [],
                "feedback": [],
            }
        else:
            user = self._users[user_id]
        token = secrets.token_urlsafe(32)
        self._sessions[token] = MockSession(token=token, user_id=user.id)
        return token, user

    def user_for_token(self, token: str | None) -> MockUser | None:
        if not token:
            return None
        session = self._sessions.get(token)
        return self._users.get(session.user_id) if session else None

    def logout(self, token: str) -> None:
        self._sessions.pop(token, None)

    def save_question(
        self,
        user_id: UUID,
        request: QuestionRequest,
        response: QuestionResponse,
        *,
        now: datetime | None = None,
    ) -> QuestionHistoryEntry:
        created_at = now or datetime.now(UTC)
        entry = QuestionHistoryEntry(
            id=UUID(response.request_id),
            user_id=user_id,
            request=request,
            response=response,
            created_at=created_at,
            expires_at=_one_year_after(created_at),
        )
        self._history[entry.id] = entry
        return entry

    def list_history(
        self, user_id: UUID, *, now: datetime | None = None
    ) -> list[QuestionHistoryEntry]:
        self.purge_expired(now=now)
        return sorted(
            (entry for entry in self._history.values() if entry.user_id == user_id),
            key=lambda entry: entry.created_at,
            reverse=True,
        )

    def get_history(
        self, history_id: UUID, user_id: UUID, *, now: datetime | None = None
    ) -> QuestionHistoryEntry | None:
        self.purge_expired(now=now)
        entry = self._history.get(history_id)
        return entry if entry and entry.user_id == user_id else None

    def delete_history(self, history_id: UUID, user_id: UUID) -> bool:
        entry = self._history.get(history_id)
        if entry is None or entry.user_id != user_id:
            return False
        del self._history[history_id]
        return True

    def record_export(self, user_id: UUID, history_id: UUID, export_format: str) -> None:
        self._related_data.setdefault(user_id, {"exports": [], "feedback": []})[
            "exports"
        ].append((history_id, export_format))

    def delete_account(self, user_id: UUID) -> None:
        user = self._users.pop(user_id, None)
        if user:
            self._users_by_email.pop(user.email, None)
        self._sessions = {
            token: session
            for token, session in self._sessions.items()
            if session.user_id != user_id
        }
        self._history = {
            history_id: entry
            for history_id, entry in self._history.items()
            if entry.user_id != user_id
        }
        self._related_data.pop(user_id, None)

    def purge_expired(self, *, now: datetime | None = None) -> int:
        boundary = now or datetime.now(UTC)
        expired = [
            history_id
            for history_id, entry in self._history.items()
            if entry.expires_at <= boundary
        ]
        for history_id in expired:
            del self._history[history_id]
        expired_set = set(expired)
        for related in self._related_data.values():
            related["exports"] = [
                item for item in related["exports"] if item[0] not in expired_set
            ]
        return len(expired)

    def clear(self) -> None:
        self._users.clear()
        self._users_by_email.clear()
        self._sessions.clear()
        self._history.clear()
        self._related_data.clear()


identity_repository = MockIdentityRepository()


def _one_year_after(value: datetime) -> datetime:
    try:
        return value.replace(year=value.year + 1)
    except ValueError:
        # 윤년 2월 29일은 다음 해 2월 말에 만료한다.
        return value.replace(year=value.year + 1, day=28)
