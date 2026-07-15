from datetime import date

import pytest
from fastapi import HTTPException, Request
from pydantic import ValidationError

from app import main
from app.adapters.memory_repository import MemoryLegalRepository
from app.settings import Settings


def _vercel_request(ip: str) -> Request:
    return Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/v1/questions",
            "headers": [(b"x-forwarded-for", ip.encode("ascii"))],
            "client": ("10.0.0.7", 443),
            "server": ("api.example.test", 443),
            "scheme": "https",
            "query_string": b"",
        }
    )


async def test_ai_quota_is_three_per_client_ip_and_separate_from_search(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(main.settings, "environment", "production")
    monkeypatch.setattr(main, "repository", MemoryLegalRepository())
    first_ip = _vercel_request("203.0.113.8")

    for _ in range(3):
        await main._check_quota(first_ip, "ai", 3)

    with pytest.raises(HTTPException) as exc_info:
        await main._check_quota(first_ip, "ai", 3)
    assert exc_info.value.status_code == 429

    # A different public IP has its own allowance, and search keeps its separate counter.
    await main._check_quota(_vercel_request("203.0.113.9"), "ai", 3)
    await main._check_quota(first_ip, "search", 30)


async def test_spoofed_forwarded_chain_cannot_rotate_quota_subject(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(main.settings, "environment", "production")
    monkeypatch.setattr(main, "repository", MemoryLegalRepository())

    for spoofed_ip in ("198.51.100.1", "198.51.100.2", "198.51.100.3"):
        await main._check_quota(
            _vercel_request(f"{spoofed_ip}, 203.0.113.8"), "ai", 3
        )

    with pytest.raises(HTTPException) as exc_info:
        await main._check_quota(
            _vercel_request("198.51.100.4, 203.0.113.8"), "ai", 3
        )
    assert exc_info.value.status_code == 429


async def test_invalid_and_missing_forwarded_ips_share_fail_closed_quota(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(main.settings, "environment", "production")
    monkeypatch.setattr(main, "repository", MemoryLegalRepository())

    for invalid_ip in ("not-an-ip", "198.51.100.1, 203.0.113.8", ""):
        await main._check_quota(_vercel_request(invalid_ip), "search", 3)

    with pytest.raises(HTTPException) as exc_info:
        await main._check_quota(_vercel_request("still-not-an-ip"), "search", 3)

    assert exc_info.value.status_code == 429


async def test_quota_resets_on_next_day() -> None:
    repository = MemoryLegalRepository()
    subject = "fake-subject-hash"

    assert await repository.consume_quota(subject, date(2026, 7, 15), "search", 1)
    assert not await repository.consume_quota(subject, date(2026, 7, 15), "search", 1)
    assert await repository.consume_quota(subject, date(2026, 7, 16), "search", 1)


@pytest.mark.parametrize(
    "field",
    (
        "ai_daily_limit",
        "search_daily_limit",
        "authenticated_ai_daily_limit",
        "authenticated_search_daily_limit",
    ),
)
def test_daily_limits_must_be_positive(field: str) -> None:
    with pytest.raises(ValidationError):
        Settings(**{field: 0})
