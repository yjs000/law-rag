from datetime import date, timedelta

from app.domain.privacy import (
    UNRESOLVED_CLIENT_SUBJECT,
    anonymous_rate_limit_subject,
    daily_subject_hash,
)


def test_daily_subject_hash_hides_and_rotates_ip() -> None:
    ip = "203.0.113.7"
    today = date(2026, 7, 13)
    first = daily_subject_hash(ip, "a-long-enough-test-secret", today)
    assert ip not in first
    assert first == daily_subject_hash(ip, "a-long-enough-test-secret", today)
    assert first != daily_subject_hash(ip, "a-long-enough-test-secret", today + timedelta(days=1))


def test_production_subject_uses_vercel_forwarded_ip_instead_of_proxy_peer() -> None:
    subject = anonymous_rate_limit_subject(
        {"x-forwarded-for": "203.0.113.8"},
        "10.0.0.7",
        trust_vercel_proxy=True,
    )

    assert subject == "203.0.113.8"


def test_local_subject_ignores_spoofed_forwarding_header() -> None:
    subject = anonymous_rate_limit_subject(
        {"x-forwarded-for": "203.0.113.99"},
        "127.0.0.1",
        trust_vercel_proxy=False,
    )

    assert subject == "127.0.0.1"


def test_forwarded_chain_and_invalid_ip_fail_closed_to_one_subject() -> None:
    forwarded_chain = anonymous_rate_limit_subject(
        {"x-forwarded-for": "198.51.100.3, 203.0.113.8"},
        "10.0.0.7",
        trust_vercel_proxy=True,
    )
    invalid = anonymous_rate_limit_subject(
        {"x-forwarded-for": "attacker-selected-subject"},
        "10.0.0.8",
        trust_vercel_proxy=True,
    )

    assert forwarded_chain == UNRESOLVED_CLIENT_SUBJECT
    assert invalid == UNRESOLVED_CLIENT_SUBJECT


def test_ipv4_mapped_ipv6_cannot_create_a_second_subject() -> None:
    ipv4 = anonymous_rate_limit_subject(
        {"x-forwarded-for": "203.0.113.8"}, None, trust_vercel_proxy=True
    )
    mapped = anonymous_rate_limit_subject(
        {"x-forwarded-for": "::ffff:203.0.113.8"}, None, trust_vercel_proxy=True
    )

    assert mapped == ipv4
