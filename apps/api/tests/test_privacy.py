from datetime import date, timedelta

from app.domain.privacy import daily_subject_hash


def test_daily_subject_hash_hides_and_rotates_ip() -> None:
    ip = "203.0.113.7"
    today = date(2026, 7, 13)
    first = daily_subject_hash(ip, "a-long-enough-test-secret", today)
    assert ip not in first
    assert first == daily_subject_hash(ip, "a-long-enough-test-secret", today)
    assert first != daily_subject_hash(ip, "a-long-enough-test-secret", today + timedelta(days=1))
