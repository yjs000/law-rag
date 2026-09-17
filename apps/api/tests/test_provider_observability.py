import asyncio
import json
import logging
from uuid import UUID

import pytest
from pydantic import BaseModel, ValidationError

from app.domain.provider_attempts import ProviderAttemptsExhausted
from app.provider_observability import (
    ProviderAttemptEvent,
    classify_provider_failure,
    emit_provider_attempt,
    provider_attempt_scope,
)


def test_attempt_event_hashes_correlation_and_emits_only_closed_fields(caplog):
    source = UUID("5194ce0e-4a06-4104-b7c0-9150d5b05f67")
    with caplog.at_level(logging.INFO, logger="law_rag.provider_attempt"):
        with provider_attempt_scope(source):
            emit_provider_attempt(
                operation="answer_core", attempt=1, max_attempts=3,
                outcome="failed", failure_kind="provider_http",
                upstream_status=503, elapsed_ms=3021, remaining_ms=36979,
                retry_scheduled=True,
            )
    payload = json.loads(caplog.records[-1].message)
    assert payload == {
        "attempt": 1,
        "correlation": "7d8d49c21f606642",
        "elapsed_ms": 3021,
        "failure_kind": "provider_http",
        "max_attempts": 3,
        "operation": "answer_core",
        "outcome": "failed",
        "provider": "nvidia",
        "remaining_ms": 36979,
        "retry_scheduled": True,
        "upstream_status": 503,
    }
    assert str(source) not in caplog.text


def test_attempt_logger_emits_info_without_test_level_override(caplog):
    with provider_attempt_scope("production-source"):
        emit_provider_attempt(
            operation="route", attempt=1, max_attempts=1,
            outcome="succeeded", failure_kind=None,
            upstream_status=None, elapsed_ms=1, remaining_ms=9,
            retry_scheduled=False,
        )

    assert len(caplog.records) == 1
    assert caplog.records[0].levelno == logging.INFO


def test_attempt_event_rejects_extra_and_inconsistent_success_fields():
    with pytest.raises(ValidationError):
        ProviderAttemptEvent.model_validate({
            "correlation": "a" * 16, "provider": "nvidia",
            "operation": "route", "attempt": 1, "max_attempts": 1,
            "outcome": "succeeded", "failure_kind": None,
            "upstream_status": None, "elapsed_ms": 1, "remaining_ms": 9,
            "retry_scheduled": False, "question": "금지된 원문",
        })


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (TimeoutError(), ("timeout", None)),
        (type("APIConnectionError", (RuntimeError,), {})(), ("connection", None)),
        (type("HttpFailure", (RuntimeError,), {"status_code": 503})(), ("provider_http", 503)),
        (ValueError(), ("invalid_response", None)),
        (asyncio.CancelledError(), ("cancelled", None)),
        (RuntimeError(), ("unknown", None)),
    ],
)
def test_failure_classifier_uses_type_and_status_only(error, expected):
    assert classify_provider_failure(error) == expected


def _event_payload(**overrides):
    payload = {
        "correlation": "a" * 16,
        "provider": "nvidia",
        "operation": "route",
        "attempt": 1,
        "max_attempts": 1,
        "outcome": "failed",
        "failure_kind": "provider_http",
        "upstream_status": 503,
        "elapsed_ms": 1,
        "remaining_ms": 9,
        "retry_scheduled": False,
    }
    payload.update(overrides)
    return payload


@pytest.mark.parametrize(
    "overrides",
    [
        {"attempt": 0},
        {"max_attempts": 0},
        {"attempt": 2},
        {"elapsed_ms": -1},
        {"remaining_ms": -1},
        {"outcome": "succeeded", "failure_kind": "provider_http"},
        {"outcome": "succeeded", "upstream_status": 503},
        {"outcome": "succeeded", "retry_scheduled": True},
    ],
)
def test_attempt_event_rejects_invalid_bounds_and_success_metadata(overrides):
    with pytest.raises(ValidationError):
        ProviderAttemptEvent.model_validate(_event_payload(**overrides))


def test_provider_attempt_scope_reuses_nested_correlation_and_resets(caplog):
    with caplog.at_level(logging.INFO, logger="law_rag.provider_attempt"):
        with provider_attempt_scope("outer-source"):
            emit_provider_attempt(
                operation="route", attempt=1, max_attempts=1,
                outcome="succeeded", failure_kind=None,
                upstream_status=None, elapsed_ms=1, remaining_ms=2,
                retry_scheduled=False,
            )
            with provider_attempt_scope("inner-source"):
                emit_provider_attempt(
                    operation="route", attempt=1, max_attempts=1,
                    outcome="succeeded", failure_kind=None,
                    upstream_status=None, elapsed_ms=1, remaining_ms=2,
                    retry_scheduled=False,
                )
            emit_provider_attempt(
                operation="route", attempt=1, max_attempts=1,
                outcome="succeeded", failure_kind=None,
                upstream_status=None, elapsed_ms=1, remaining_ms=2,
                retry_scheduled=False,
            )
        with provider_attempt_scope("new-source"):
            emit_provider_attempt(
                operation="route", attempt=1, max_attempts=1,
                outcome="succeeded", failure_kind=None,
                upstream_status=None, elapsed_ms=1, remaining_ms=2,
                retry_scheduled=False,
            )

    correlations = [json.loads(record.message)["correlation"] for record in caplog.records]
    assert correlations[0] == correlations[1] == correlations[2]
    assert correlations[3] != correlations[0]
    assert "outer-source" not in caplog.text
    assert "inner-source" not in caplog.text


async def _emit_for_source(source):
    with provider_attempt_scope(source):
        emit_provider_attempt(
            operation="route", attempt=1, max_attempts=1,
            outcome="succeeded", failure_kind=None,
            upstream_status=None, elapsed_ms=1, remaining_ms=2,
            retry_scheduled=False,
        )
        await asyncio.sleep(0)
        emit_provider_attempt(
            operation="route", attempt=1, max_attempts=1,
            outcome="succeeded", failure_kind=None,
            upstream_status=None, elapsed_ms=1, remaining_ms=2,
            retry_scheduled=False,
        )


async def test_provider_attempt_scope_isolated_between_async_tasks(caplog):
    with caplog.at_level(logging.INFO, logger="law_rag.provider_attempt"):
        await asyncio.gather(_emit_for_source("task-one"), _emit_for_source("task-two"))

    correlations = [json.loads(record.message)["correlation"] for record in caplog.records]
    assert correlations[0] == correlations[2]
    assert correlations[1] == correlations[3]
    assert correlations[0] != correlations[1]


def test_failure_classifier_prioritizes_cancel_timeout_status_and_schema():
    cancelled = type("CancelledWithStatus", (asyncio.CancelledError,), {"status_code": 503})()
    timed_out = type("TimeoutWithStatus", (TimeoutError,), {"status_code": 503})()
    http_connection = type("APIConnectionError", (RuntimeError,), {"status_code": 503})()

    class Schema(BaseModel):
        value: int

    with pytest.raises(ValidationError) as raised:
        Schema.model_validate({"value": "not-an-int"})

    assert classify_provider_failure(cancelled) == ("cancelled", None)
    assert classify_provider_failure(timed_out) == ("timeout", None)
    assert classify_provider_failure(http_connection) == ("provider_http", 503)
    assert classify_provider_failure(raised.value) == ("schema_validation", None)


def test_provider_attempts_exhausted_has_only_sanitized_typed_metadata():
    error = ProviderAttemptsExhausted(failure_kind="provider_http", upstream_status=503)

    assert isinstance(error, RuntimeError)
    assert str(error) == "provider attempts exhausted"
    assert error.failure_kind == "provider_http"
    assert error.upstream_status == 503
