import asyncio
import json
import logging
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from starlette.requests import Request

from app.adapters.memory_question_execution import MemoryQuestionExecutionRepository
from app.application.question_phase_coordinator import PhaseResult, QuestionPhaseCoordinator
from app.domain.question_execution import ExecutionStatus
from app.domain.schemas import QuestionRequest
from app.provider_observability import ProviderOperation, emit_provider_attempt


def _request() -> Request:
    return Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/v1/questions",
            "headers": [],
            "client": ("127.0.0.1", 50000),
        }
    )


def _emit(operation: ProviderOperation) -> None:
    emit_provider_attempt(
        operation=operation,
        model="nvidia/nemotron-3.5-lightning-30b-a3b",
        timeout_ms=8_000,
        attempt=1,
        max_attempts=1,
        outcome="succeeded",
        failure_kind=None,
        upstream_status=None,
        elapsed_ms=1,
        remaining_ms=1,
        retry_scheduled=False,
    )


def _events(caplog: pytest.LogCaptureFixture) -> list[dict[str, object]]:
    events = [json.loads(record.message) for record in caplog.records]
    return [event for event in events if event.get("event_type") == "provider_attempt"]


@pytest.mark.asyncio
async def test_v1_answer_callback_scopes_concurrent_requests_by_client_id(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """A v1 callback's route, embedding, and answer logs stay request-correlated."""

    import app.api.v1.questions as questions_module

    class Tasks:
        async def register(self, *_args: object) -> bool:
            return True

        async def unregister(self, *_args: object) -> None:
            return None

    class Main:
        settings = SimpleNamespace(
            question_request_timeout_seconds=5,
            response_reserve_seconds=0,
        )
        question_tasks = Tasks()

        @staticmethod
        def _question_owner(*_args: object) -> str:
            return "anonymous:test"

        async def _answer_question(self, *_args: object) -> object:
            _emit("route")
            await asyncio.sleep(0)
            _emit("query_embedding")
            await asyncio.sleep(0)
            _emit("answer_detail")
            return SimpleNamespace(fallback_reason=None)

    async def no_user(*_args: object) -> None:
        return None

    monkeypatch.setattr(questions_module, "main_module", lambda: Main())
    monkeypatch.setattr(questions_module, "_optional_user", no_user)
    first = QuestionRequest(
        client_request_id=UUID("00000000-0000-0000-0000-000000000001"),
        question="first private question",
    )
    second = QuestionRequest(
        client_request_id=UUID("00000000-0000-0000-0000-000000000002"),
        question="second private question",
    )

    with caplog.at_level(logging.INFO, logger="law_rag.provider_attempt"):
        await asyncio.gather(
            questions_module._handle_question(first, _request(), object()),
            questions_module._handle_question(second, _request(), object()),
        )

    events = _events(caplog)
    expected = {"7ac1b8d7010bb6cd", "90d5b0a26955772e"}
    assert len(events) == 6
    assert {event["correlation"] for event in events} == expected
    for operation in ("route", "query_embedding", "answer_detail"):
        correlations = {event["correlation"] for event in events if event["operation"] == operation}
        assert correlations == expected
    provider_text = json.dumps(events)
    assert str(first.client_request_id) not in provider_text
    assert str(second.client_request_id) not in provider_text


@pytest.mark.asyncio
async def test_v2_prepare_scopes_route_clarification_and_retrieval_by_client_id(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """Prepare keeps its pre-phase NVIDIA work under one client request hash."""

    import app.api.v2.executions as executions_module

    execution_id = UUID("00000000-0000-0000-0000-000000000010")

    class Service:
        async def prepare(self, _command: object) -> object:
            _emit("query_embedding")
            return SimpleNamespace(execution=SimpleNamespace(execution_id=execution_id))

        @staticmethod
        def prepared_response(_prepared: object) -> dict[str, object]:
            return {"execution_id": str(execution_id)}

    fake_main = SimpleNamespace(
        settings=SimpleNamespace(v2_phase_timeout_seconds=5),
        _question_owner=lambda *_args: "anonymous:test",
        v2_question_execution_service=Service(),
    )

    async def no_user(*_args: object) -> None:
        return None

    async def prepare_clarification(*_args: object) -> tuple[None, None, object]:
        _emit("route")
        await asyncio.sleep(0)
        _emit("clarification")
        return None, None, SimpleNamespace(route="clarification_required")

    monkeypatch.setattr(executions_module, "main_module", lambda: fake_main)
    monkeypatch.setattr(executions_module, "_optional_user", no_user)
    monkeypatch.setattr(executions_module, "_prepare_clarification_turn", prepare_clarification)
    payload = QuestionRequest(
        client_request_id=UUID("00000000-0000-0000-0000-000000000003"),
        question="private question",
    )

    with caplog.at_level(logging.INFO, logger="law_rag.provider_attempt"):
        response = await executions_module.prepare_question_execution(
            payload, _request(), "correlation-prepare"
        )

    events = _events(caplog)
    assert response == {"execution_id": str(execution_id)}
    assert [event["operation"] for event in events] == [
        "route",
        "clarification",
        "query_embedding",
    ]
    assert {event["correlation"] for event in events} == {"c67f2fc391b67892"}
    assert str(payload.client_request_id) not in json.dumps(events)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("request_payload", "expected_client_correlation"),
    [
        ({"client_request_id": "00000000-0000-0000-0000-000000000003"}, "c67f2fc391b67892"),
        ({}, None),
        ({"client_request_id": ""}, None),
        ({"client_request_id": 3}, None),
    ],
)
async def test_coordinator_scopes_producer_to_private_client_id_or_execution_fallback(
    request_payload: dict[str, object],
    expected_client_correlation: str | None,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The producer receives a client hash when valid, otherwise its execution hash."""

    started_at = datetime(2026, 9, 15, tzinfo=UTC)
    repository = MemoryQuestionExecutionRepository(now=lambda: started_at)
    execution = await repository.prepare_or_get(
        owner_scope="anonymous:test",
        prepare_idempotency_key="provider-correlation",
        generation_id=uuid4(),
        expires_at=started_at + timedelta(minutes=10),
        private_payload={"request": request_payload},
    )

    async def core(_record: object) -> PhaseResult:
        _emit("answer_core")
        return PhaseResult(target=ExecutionStatus.CORE_ANSWERED, events=())

    async def finalize(_record: object) -> PhaseResult:
        raise AssertionError("finalize must not run")

    coordinator = QuestionPhaseCoordinator(repository, core=core, finalize=finalize)
    with caplog.at_level(logging.INFO, logger="law_rag.provider_attempt"):
        await coordinator.run(
            execution.execution_id,
            "anonymous:test",
            phase="core",
            capability_hash=None,
        )

    events = _events(caplog)
    expected = (
        expected_client_correlation
        or sha256(str(execution.execution_id).encode("utf-8")).hexdigest()[:16]
    )
    assert [event["correlation"] for event in events] == [expected]
    assert str(execution.execution_id) not in caplog.text
    assert "00000000-0000-0000-0000-000000000003" not in caplog.text
