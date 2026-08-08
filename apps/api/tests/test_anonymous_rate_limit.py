from datetime import date

import pytest
from pydantic import ValidationError

from app import main
from app.adapters.memory_repository import MemoryLegalRepository
from app.settings import Settings

pytestmark = pytest.mark.usefixtures("ready_corpus_temporal_state")


async def test_anonymous_requests_have_no_daily_quota(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(main.settings, "environment", "production")
    monkeypatch.setattr(main, "repository", MemoryLegalRepository())

    # Anonymous callers are never gated: no user, no postgres_identity involvement,
    # so _check_quota is a no-op regardless of call volume.
    for _ in range(10):
        await main._check_quota("ai")
    for _ in range(10):
        await main._check_quota("search")


async def test_quota_resets_on_next_day() -> None:
    repository = MemoryLegalRepository()
    subject = "fake-subject-hash"

    assert await repository.consume_quota(subject, date(2026, 7, 15), "search", 1)
    assert not await repository.consume_quota(subject, date(2026, 7, 15), "search", 1)
    assert await repository.consume_quota(subject, date(2026, 7, 16), "search", 1)


@pytest.mark.parametrize(
    "field",
    (
        "authenticated_ai_daily_limit",
        "authenticated_search_daily_limit",
    ),
)
def test_daily_limits_must_be_positive(field: str) -> None:
    with pytest.raises(ValidationError):
        Settings(**{field: 0})
