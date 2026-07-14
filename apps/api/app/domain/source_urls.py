from urllib.parse import urlsplit

ALLOWED_SOURCE_HOSTS = frozenset({"law.go.kr", "www.law.go.kr", "open.law.go.kr"})


def is_allowed_source_url(value: str) -> bool:
    """브라우저에 노출 가능한 국가법령정보 원문 URL만 허용한다."""
    try:
        parsed = urlsplit(value)
        port = parsed.port
    except ValueError:
        return False
    return (
        parsed.scheme == "https"
        and parsed.hostname in ALLOWED_SOURCE_HOSTS
        and port in {None, 443}
        and parsed.username is None
        and parsed.password is None
    )
