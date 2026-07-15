import pytest
from fastapi import HTTPException, Request

from app import main
from app.adapters.memory_repository import MemoryLegalRepository


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
