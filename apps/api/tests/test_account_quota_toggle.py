from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

import pytest
from fastapi import HTTPException

from app import main
from app.domain.schemas import MockUser

pytestmark = pytest.mark.usefixtures("ready_corpus_temporal_state")

USER = MockUser(
    id=UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"),
    email="owner@example.com",
    display_name="owner",
    created_at=datetime(2026, 7, 15, tzinfo=UTC),
)


class DenyingPostgresIdentity:
    """consume_quota always denies, so a passing test proves the caller never invoked it."""

    def __init__(self) -> None:
        self.calls = 0

    async def consume_quota(self, *_: object) -> bool:
        self.calls += 1
        return False


async def test_account_quota_disabled_by_default_never_blocks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    identity = DenyingPostgresIdentity()
    monkeypatch.setattr(main, "postgres_identity", identity)

    for _ in range(5):
        await main._check_quota("ai", user=USER)
        await main._check_quota("search", user=USER)

    assert identity.calls == 0


async def test_account_quota_enabled_enforces_limit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    identity = DenyingPostgresIdentity()
    monkeypatch.setattr(main, "postgres_identity", identity)
    monkeypatch.setattr(main.settings, "account_quota_enabled", True)

    with pytest.raises(HTTPException) as excinfo:
        await main._check_quota("ai", user=USER)

    assert excinfo.value.status_code == 429
    assert identity.calls == 1


def test_account_quota_disabled_by_default() -> None:
    assert main.settings.account_quota_enabled is False
