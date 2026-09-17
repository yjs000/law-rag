import json
import logging

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.runtime_observability import (
    bind_runtime_correlation,
    install_runtime_exception_middleware,
    set_pipeline_stage,
)


def test_runtime_middleware_logs_unhandled_cause_at_last_stage_once(caplog) -> None:
    application = FastAPI()
    install_runtime_exception_middleware(application, mode="raw")

    @application.get("/boom")
    async def boom() -> None:
        bind_runtime_correlation("client-123")
        set_pipeline_stage("persistence")
        try:
            raise RuntimeError("sqlstate=23505 parameters={'email': 'private@example.com'}")
        except RuntimeError as cause:
            raise AttributeError("missing saved_execution") from cause

    with caplog.at_level(logging.ERROR, logger="law_rag.runtime_exception"):
        response = TestClient(application, raise_server_exceptions=False).get("/boom")

    records = [
        json.loads(record.message)
        for record in caplog.records
        if record.name == "law_rag.runtime_exception"
    ]
    assert response.status_code == 500
    assert "missing saved_execution" not in response.text
    assert len(records) == 1
    assert records[0]["correlation"] == "b44ea687b506d5ca"
    assert records[0]["pipeline_stage"] == "persistence"
    assert records[0]["operation"] == "GET /boom"
    assert records[0]["exception_type"] == "AttributeError"
    assert records[0]["cause_chain"][0]["exception_type"] == "RuntimeError"
    assert "private@example.com" in records[0]["cause_chain"][0]["message"]


def test_runtime_middleware_redacts_unhandled_error_without_changing_response(caplog) -> None:
    application = FastAPI()
    install_runtime_exception_middleware(application, mode="redacted")

    @application.get("/secret")
    async def secret() -> None:
        set_pipeline_stage("retrieval")
        raise RuntimeError(
            "authorization=Bearer runtime-secret "
            "question=private question [parameters: {'id': 7}]"
        )

    with caplog.at_level(logging.ERROR, logger="law_rag.runtime_exception"):
        response = TestClient(application, raise_server_exceptions=False).get("/secret")

    event = json.loads(
        next(
            record.message
            for record in caplog.records
            if record.name == "law_rag.runtime_exception"
        )
    )
    encoded = json.dumps(event)
    assert response.status_code == 500
    assert response.text == "Internal Server Error"
    assert event["pipeline_stage"] == "retrieval"
    assert "[REDACTED]" in encoded
    assert "runtime-secret" not in encoded
    assert "private question" not in encoded


def test_main_create_app_installs_runtime_exception_boundary(caplog) -> None:
    import app.main as main_module

    application = main_module.create_app(main_module.dependencies)

    @application.get("/test-runtime-boundary")
    async def fail_from_composed_app() -> None:
        set_pipeline_stage("response_serialization")
        raise TypeError("cannot serialize internal value")

    with caplog.at_level(logging.ERROR, logger="law_rag.runtime_exception"):
        response = TestClient(application, raise_server_exceptions=False).get(
            "/test-runtime-boundary"
        )

    events = [
        json.loads(record.message)
        for record in caplog.records
        if record.name == "law_rag.runtime_exception"
    ]
    assert response.status_code == 500
    assert len(events) == 1
    assert events[0]["pipeline_stage"] == "response_serialization"
    assert events[0]["exception_type"] == "TypeError"


def test_composition_injects_runtime_error_log_mode() -> None:
    import app.main as main_module

    assert main_module._v1_answer_dependencies().error_log_mode == (
        main_module.settings.error_log_mode
    )
    assert main_module._v2_service_dependencies().error_log_mode == (
        main_module.settings.error_log_mode
    )


def test_v1_caught_retrieval_error_logs_redacted_stage(
    monkeypatch, caplog, ready_corpus_temporal_state
) -> None:
    import app.main as main_module
    from app.adapters.memory_repository import MemoryLegalRepository

    repository = MemoryLegalRepository()

    async def fail_search(*_args, **_kwargs):
        raise RuntimeError(
            "postgresql://private-user:private-password@db.internal/law "
            "[parameters: {'email': 'private@example.com'}]"
        )

    monkeypatch.setattr(repository, "search_with_trace", fail_search)
    monkeypatch.setattr(main_module, "repository", repository)
    monkeypatch.setattr(main_module.settings, "search_only_enabled", True)
    with caplog.at_level(logging.ERROR, logger="law_rag.runtime_exception"):
        response = TestClient(main_module.app, raise_server_exceptions=False).post(
            "/v1/questions",
            json={
                "question": "가짜 익명 질문",
                "as_of_date": "2026-07-15",
                "project_stage": "planning",
                "answer_mode": "search_only",
            },
        )

    event = json.loads(
        next(
            record.message
            for record in caplog.records
            if record.name == "law_rag.runtime_exception"
        )
    )
    encoded = json.dumps(event)
    assert response.status_code == 503
    assert response.json() == {"detail": "법령 검색을 일시적으로 사용할 수 없습니다."}
    assert event["pipeline_stage"] == "retrieval"
    assert event["exception_type"] == "RuntimeError"
    assert "[REDACTED]" in encoded
    assert "private-password" not in encoded
    assert "private@example.com" not in encoded
