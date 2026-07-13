import hashlib
import hmac
from datetime import date


def daily_subject_hash(subject: str, secret: str, day: date) -> str:
    daily_key = hmac.new(secret.encode(), day.isoformat().encode(), hashlib.sha256).digest()
    return hmac.new(daily_key, subject.encode(), hashlib.sha256).hexdigest()
