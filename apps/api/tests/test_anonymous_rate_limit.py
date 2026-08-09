from datetime import date

from app.adapters.memory_repository import MemoryLegalRepository


async def test_quota_resets_on_next_day() -> None:
    repository = MemoryLegalRepository()
    subject = "fake-subject-hash"

    assert await repository.consume_quota(subject, date(2026, 7, 15), "search", 1)
    assert not await repository.consume_quota(subject, date(2026, 7, 15), "search", 1)
    assert await repository.consume_quota(subject, date(2026, 7, 16), "search", 1)
