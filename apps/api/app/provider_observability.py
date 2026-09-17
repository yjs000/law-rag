from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from hashlib import sha256
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

ProviderOperation = Literal[
    "route",
    "query_embedding",
    "answer_core",
    "answer_detail",
    "clarification",
]
ProviderFailureKind = Literal[
    "provider_http",
    "timeout",
    "connection",
    "invalid_response",
    "schema_validation",
    "cancelled",
    "unknown",
]
ProviderAttemptOutcome = Literal["succeeded", "failed"]

_LOGGER = logging.getLogger("law_rag.provider_attempt")
_LOGGER.setLevel(logging.INFO)
_CORRELATION: ContextVar[str | None] = ContextVar("provider_attempt_correlation", default=None)


class ProviderAttemptEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    correlation: str = Field(min_length=16, max_length=16, pattern=r"^[0-9a-f]{16}$")
    provider: Literal["nvidia"] = "nvidia"
    operation: ProviderOperation
    attempt: int = Field(ge=1)
    max_attempts: int = Field(ge=1)
    outcome: ProviderAttemptOutcome
    failure_kind: ProviderFailureKind | None
    upstream_status: int | None
    elapsed_ms: int = Field(ge=0)
    remaining_ms: int = Field(ge=0)
    retry_scheduled: bool

    @model_validator(mode="after")
    def validate_attempt_contract(self) -> ProviderAttemptEvent:
        if self.attempt > self.max_attempts:
            raise ValueError("attempt must not exceed max_attempts")
        if self.outcome == "succeeded":
            if self.failure_kind is not None or self.upstream_status is not None:
                raise ValueError("successful attempts cannot have failure metadata")
            if self.retry_scheduled:
                raise ValueError("successful attempts cannot schedule a retry")
        elif self.failure_kind is None:
            raise ValueError("failed attempts require failure_kind")
        return self


def _hash_source(source: object) -> str:
    return sha256(str(source).encode("utf-8")).hexdigest()[:16]


@contextmanager
def provider_attempt_scope(source: object | None = None) -> Iterator[None]:
    """Bind one hashed provider correlation to the current async context."""
    if _CORRELATION.get() is not None:
        yield
        return

    token = _CORRELATION.set(_hash_source(uuid4() if source is None else source))
    try:
        yield
    finally:
        _CORRELATION.reset(token)


def _correlation() -> str:
    return _CORRELATION.get() or _hash_source(uuid4())


def classify_provider_failure(error: BaseException) -> tuple[ProviderFailureKind, int | None]:
    if isinstance(error, asyncio.CancelledError):
        return "cancelled", None
    if isinstance(error, TimeoutError) or type(error).__name__ == "APITimeoutError":
        return "timeout", None

    status_code = getattr(error, "status_code", None)
    if isinstance(status_code, int) and not isinstance(status_code, bool):
        return "provider_http", status_code

    if isinstance(error, ConnectionError) or type(error).__name__ == "APIConnectionError":
        return "connection", None
    if isinstance(error, ValidationError):
        return "schema_validation", None
    if isinstance(error, ValueError):
        return "invalid_response", None
    return "unknown", None


def emit_provider_attempt(
    *,
    operation: ProviderOperation,
    attempt: int,
    max_attempts: int,
    outcome: ProviderAttemptOutcome,
    failure_kind: ProviderFailureKind | None,
    upstream_status: int | None,
    elapsed_ms: int,
    remaining_ms: int,
    retry_scheduled: bool,
) -> None:
    event = ProviderAttemptEvent(
        correlation=_correlation(),
        operation=operation,
        attempt=attempt,
        max_attempts=max_attempts,
        outcome=outcome,
        failure_kind=failure_kind,
        upstream_status=upstream_status,
        elapsed_ms=elapsed_ms,
        remaining_ms=remaining_ms,
        retry_scheduled=retry_scheduled,
    )
    _LOGGER.info(json.dumps(event.model_dump(mode="json"), sort_keys=True))
