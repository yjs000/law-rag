from typing import Literal

ProviderAvailabilityFailureKind = Literal["provider_http", "timeout", "connection"]


def provider_upstream_status(error: BaseException) -> int | None:
    """Read the sanitized typed status first, then an upstream HTTP error status."""

    for attribute in ("upstream_status", "status_code"):
        value = getattr(error, attribute, None)
        if isinstance(value, int) and not isinstance(value, bool):
            return value
    return None


class ProviderAttemptsExhausted(RuntimeError):
    def __init__(
        self,
        *,
        failure_kind: ProviderAvailabilityFailureKind,
        upstream_status: int | None,
    ) -> None:
        super().__init__("provider attempts exhausted")
        self.failure_kind = failure_kind
        self.upstream_status = upstream_status
