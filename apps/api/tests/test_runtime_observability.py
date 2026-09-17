import json
import logging

from app.runtime_observability import (
    configure_runtime_logging,
    current_pipeline_stage,
    emit_runtime_exception,
    runtime_observation_scope,
    serialize_exception,
    set_pipeline_stage,
)


def _nested_error() -> RuntimeError:
    try:
        raise ValueError(
            "authorization=Bearer secret-token "
            "postgresql://admin:db-password@db.example/law "
            "question=민감한 질문 [parameters: {'email': 'person@example.com'}]"
        )
    except ValueError as cause:
        try:
            raise RuntimeError("provider failed with nvapi-secret-value") from cause
        except RuntimeError as error:
            return error


def test_redacted_exception_keeps_diagnostics_without_private_values() -> None:
    payload = serialize_exception(_nested_error(), mode="redacted")

    encoded = json.dumps(payload, ensure_ascii=False)
    assert payload["exception_type"] == "RuntimeError"
    assert "test_runtime_observability.py" in payload["stack_trace"]
    assert payload["cause_chain"][0]["exception_type"] == "ValueError"
    assert "[REDACTED]" in encoded
    for private_value in (
        "secret-token",
        "admin",
        "db-password",
        "민감한 질문",
        "person@example.com",
        "nvapi-secret-value",
    ):
        assert private_value not in encoded


def test_redacted_exception_removes_json_and_query_content_fields() -> None:
    error = RuntimeError(
        '{"prompt":"private prompt", "api_key":"nvapi-json-secret"} '
        '?question=private-query&token=session-secret'
    )

    encoded = json.dumps(serialize_exception(error, mode="redacted"))

    assert "[REDACTED]" in encoded
    assert "private prompt" not in encoded
    assert "private-query" not in encoded
    assert "session-secret" not in encoded


def test_raw_exception_preserves_original_message_stack_and_cause() -> None:
    payload = serialize_exception(_nested_error(), mode="raw")

    assert "nvapi-secret-value" in payload["message"]
    assert "raise RuntimeError" in payload["stack_trace"]
    assert "db-password" in payload["cause_chain"][0]["message"]
    assert "민감한 질문" in payload["cause_chain"][0]["message"]


def test_runtime_scope_tracks_stage_and_emits_same_exception_once(caplog) -> None:
    error = AttributeError("missing legal_repository")

    with caplog.at_level(logging.ERROR, logger="law_rag.runtime_exception"):
        with runtime_observation_scope("request-123", initial_stage="request_validation"):
            assert current_pipeline_stage() == "request_validation"
            set_pipeline_stage("retrieval")
            emit_runtime_exception(error, operation="load_corpus", mode="raw")
            emit_runtime_exception(error, operation="load_corpus", mode="raw")

    records = [
        json.loads(record.message)
        for record in caplog.records
        if record.name == "law_rag.runtime_exception"
    ]
    assert len(records) == 1
    assert records[0]["event_type"] == "runtime_exception"
    assert records[0]["correlation"] == "4c18d52386a765eb"
    assert records[0]["pipeline_stage"] == "retrieval"
    assert records[0]["operation"] == "load_corpus"
    assert records[0]["exception_type"] == "AttributeError"
    assert current_pipeline_stage() == "request_validation"


def test_runtime_scope_isolates_nested_stage_and_correlation(caplog) -> None:
    with caplog.at_level(logging.ERROR, logger="law_rag.runtime_exception"):
        with runtime_observation_scope("outer", initial_stage="routing"):
            set_pipeline_stage("answer_generation")
            with runtime_observation_scope("inner", initial_stage="persistence"):
                emit_runtime_exception(
                    TypeError("bad record"), operation="save", mode="raw"
                )

    payload = json.loads(caplog.records[-1].message)
    assert payload["correlation"] == "560e3e12b1e0dafa"
    assert payload["pipeline_stage"] == "answer_generation"


def test_configure_runtime_logging_adds_one_fallback_handler_when_chain_is_empty() -> None:
    logger = logging.getLogger("law_rag")
    old_handlers = list(logger.handlers)
    old_propagate = logger.propagate
    root = logging.getLogger()
    old_root_handlers = list(root.handlers)
    try:
        logger.handlers.clear()
        root.handlers.clear()

        configure_runtime_logging("raw")
        configure_runtime_logging("raw")

        assert len(logger.handlers) == 1
        assert isinstance(logger.handlers[0], logging.StreamHandler)
    finally:
        logger.handlers[:] = old_handlers
        logger.propagate = old_propagate
        root.handlers[:] = old_root_handlers


def test_configure_runtime_logging_reuses_existing_handler_chain() -> None:
    logger = logging.getLogger("law_rag")
    old_handlers = list(logger.handlers)
    root = logging.getLogger()
    old_root_handlers = list(root.handlers)
    existing = logging.StreamHandler()
    try:
        logger.handlers.clear()
        root.handlers[:] = [existing]

        configure_runtime_logging("redacted")

        assert logger.handlers == []
        assert root.handlers == [existing]
    finally:
        logger.handlers[:] = old_handlers
        root.handlers[:] = old_root_handlers
