import hashlib
import hmac
from collections.abc import Mapping
from datetime import date
from ipaddress import IPv6Address, ip_address

UNRESOLVED_CLIENT_SUBJECT = "unresolved-client"


def _canonical_ip(value: str | None) -> str | None:
    if not value:
        return None
    candidate = value.strip()
    # Vercel emits one public address. Accepting a forwarded chain would make
    # an attacker-controlled first entry a rate-limit bypass after a proxy misconfiguration.
    if not candidate or len(candidate) > 64 or "," in candidate or "%" in candidate:
        return None
    try:
        address = ip_address(candidate)
    except ValueError:
        return None
    if isinstance(address, IPv6Address) and address.ipv4_mapped is not None:
        address = address.ipv4_mapped
    return address.compressed


def anonymous_rate_limit_subject(
    headers: Mapping[str, str], client_host: str | None, *, trust_vercel_proxy: bool
) -> str:
    """Return a canonical, non-persisted subject for anonymous quota hashing.

    Vercel overwrites ``x-forwarded-for`` at its edge to prevent client spoofing. The
    header is therefore trusted only for the production deployment. Local and test
    servers use the socket peer and deliberately ignore user-supplied forwarding headers.
    """
    if trust_vercel_proxy:
        return _canonical_ip(headers.get("x-forwarded-for")) or UNRESOLVED_CLIENT_SUBJECT
    return _canonical_ip(client_host) or UNRESOLVED_CLIENT_SUBJECT


def daily_subject_hash(subject: str, secret: str, day: date) -> str:
    daily_key = hmac.new(secret.encode(), day.isoformat().encode(), hashlib.sha256).digest()
    return hmac.new(daily_key, subject.encode(), hashlib.sha256).hexdigest()
