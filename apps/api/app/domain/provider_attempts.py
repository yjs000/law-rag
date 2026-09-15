from typing import Literal

ProviderAvailabilityFailureKind = Literal["provider_http", "timeout", "connection"]


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
