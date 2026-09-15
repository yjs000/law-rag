from __future__ import annotations

import asyncio
import json
import logging
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

import app.adapters.nvidia_nim_answerer as answerer_module
from app.adapters.nvidia_nim_answerer import NvidiaNimAnswerer
from app.application.v2.grounding import ClarificationGrounding
from app.domain.catalog import SourceKind
from app.domain.clarification import ClarificationCase
from app.domain.provider_attempts import ProviderAttemptsExhausted
from app.domain.schemas import QuestionRequest, SearchHit


class ScriptedClient:
    def __init__(self, steps: list[object]) -> None:
        self.steps = steps
        self.calls = 0
        self.chat = SimpleNamespace(completions=self)

    async def create(self, **kwargs: object) -> object:
        del kwargs
        self.calls += 1
        step = self.steps[min(self.calls - 1, len(self.steps) - 1)]
        if isinstance(step, BaseException):
            raise step
        return step

    async def close(self) -> None:
        return None


def scripted_answerer(
    steps: list[object], *, max_attempts: int = 3, timeout_seconds: float = 30
) -> tuple[NvidiaNimAnswerer, ScriptedClient]:
    client = ScriptedClient(steps)
    answerer = NvidiaNimAnswerer(
        api_key="test-key",
        base_url="https://integrate.api.nvidia.com/v1",
        model="nvidia/nemotron-3-ultra-550b-a55b",
        timeout_seconds=timeout_seconds,
        max_output_tokens=4096,
        max_attempts=max_attempts,
        client_factory=lambda: client,
    )
    return answerer, client


def provider_http_error(status_code: int, message: str) -> RuntimeError:
    error = RuntimeError(message)
    error.status_code = status_code  # type: ignore[attr-defined]
    return error


def _response(payload: dict[str, object]) -> SimpleNamespace:
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps(payload)))],
    )


def core_response(*, summary: str) -> SimpleNamespace:
    return _response(
        {
            "summary": summary,
            "citation_ids": [],
            "action": "unanswerable",
        }
    )


def detail_response(*, summary: str = "검증된 상세 답변") -> SimpleNamespace:
    return _response(
        {
            "summary": summary,
            "scope": "기준일 현재",
            "sections": [],
            "checklist": [],
            "limitations": [],
            "action": "unanswerable",
        }
    )


def response_with_content(content: str | None) -> SimpleNamespace:
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=content))],
    )


def clarification() -> ClarificationGrounding:
    return ClarificationGrounding(policy="full", case=ClarificationCase(required_facts=()))


def _hit() -> SearchHit:
    return SearchHit(
        provision_id=uuid4(),
        document_id=uuid4(),
        document_title="전기사업법",
        source_kind=SourceKind.LAW,
        version_label="MST 1",
        effective_from="2026-01-01",
        effective_to=None,
        path="제1조",
        content="전기사업에 관한 근거",
        source_url="https://www.law.go.kr/법령/전기사업법/제1조",
    )


@pytest.mark.asyncio
async def test_answer_core_logs_503_timeout_and_success_in_attempt_order(caplog):
    answerer, _ = scripted_answerer(
        [
            provider_http_error(503, "secret response"),
            TimeoutError("secret timeout detail"),
            core_response(summary="검증된 요약"),
        ]
    )
    request = QuestionRequest(
        client_request_id=UUID("5194ce0e-4a06-4104-b7c0-9150d5b05f67"),
        question="로그에 남으면 안 되는 질문",
    )
    with caplog.at_level(logging.INFO, logger="law_rag.provider_attempt"):
        result = await answerer.answer_core(request, [_hit()])
    events = [json.loads(record.message) for record in caplog.records]

    assert result.summary == "검증된 요약"
    assert [(event["attempt"], event["outcome"], event["failure_kind"]) for event in events] == [
        (1, "failed", "provider_http"),
        (2, "failed", "timeout"),
        (3, "succeeded", None),
    ]
    assert [event["retry_scheduled"] for event in events] == [True, True, False]
    assert {event["operation"] for event in events} == {"answer_core"}
    assert {event["provider"] for event in events} == {"nvidia"}
    assert {event["max_attempts"] for event in events} == {3}
    assert all(event["elapsed_ms"] >= 0 and event["remaining_ms"] >= 0 for event in events)
    assert "secret response" not in caplog.text
    assert "secret timeout detail" not in caplog.text
    assert request.question not in caplog.text


@pytest.mark.asyncio
async def test_answer_core_logs_terminal_503_and_raises_sanitized_exhaustion(caplog):
    answerer, client = scripted_answerer(
        [
            provider_http_error(503, "secret response 1"),
            provider_http_error(503, "secret response 2"),
            provider_http_error(503, "secret response 3"),
        ]
    )
    with caplog.at_level(logging.INFO, logger="law_rag.provider_attempt"):
        with pytest.raises(ProviderAttemptsExhausted) as raised:
            await answerer.answer_core(QuestionRequest(question="비공개 질문"), [_hit()])

    events = [json.loads(record.message) for record in caplog.records]
    assert client.calls == 3
    assert len(events) == 3
    assert [event["outcome"] for event in events] == ["failed", "failed", "failed"]
    assert [event["failure_kind"] for event in events] == [
        "provider_http",
        "provider_http",
        "provider_http",
    ]
    assert [event["retry_scheduled"] for event in events] == [True, True, False]
    assert raised.value.failure_kind == "provider_http"
    assert raised.value.upstream_status == 503
    assert raised.value.__cause__ is None
    assert "secret response" not in caplog.text
    assert "비공개 질문" not in caplog.text


@pytest.mark.asyncio
@pytest.mark.parametrize("status_code", [402, 429])
async def test_answer_does_not_retry_402_or_429_and_logs_original_status(status_code, caplog):
    answerer, client = scripted_answerer([provider_http_error(status_code, "secret quota")])
    with caplog.at_level(logging.INFO, logger="law_rag.provider_attempt"):
        with pytest.raises(ProviderAttemptsExhausted):
            await answerer.answer(QuestionRequest(question="비공개 질문"), [_hit()])

    events = [json.loads(record.message) for record in caplog.records]
    assert client.calls == 1
    assert len(events) == 1
    assert events[0]["operation"] == "answer_detail"
    assert events[0]["attempt"] == 1
    assert events[0]["failure_kind"] == "provider_http"
    assert events[0]["upstream_status"] == status_code
    assert events[0]["retry_scheduled"] is False
    assert "secret quota" not in caplog.text


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("content", "expected_exception", "failure_kind"),
    [
        (None, ValueError, "invalid_response"),
        ("not-json", ValidationError, "schema_validation"),
        ("{}", ValidationError, "schema_validation"),
    ],
)
async def test_answer_logs_validation_failures_for_each_attempt_without_exhaustion(
    content, expected_exception, failure_kind, caplog
):
    answerer, client = scripted_answerer([response_with_content(content)], max_attempts=2)
    with caplog.at_level(logging.INFO, logger="law_rag.provider_attempt"):
        with pytest.raises(expected_exception):
            await answerer.answer(QuestionRequest(question="비공개 질문"), [_hit()])

    events = [json.loads(record.message) for record in caplog.records]
    assert client.calls == 2
    assert [event["attempt"] for event in events] == [1, 2]
    assert [event["failure_kind"] for event in events] == [failure_kind, failure_kind]
    assert [event["retry_scheduled"] for event in events] == [True, False]
    assert all(event["operation"] == "answer_detail" for event in events)


@pytest.mark.asyncio
async def test_answer_core_logs_cancellation_once_and_does_not_retry(caplog):
    answerer, client = scripted_answerer([asyncio.CancelledError("secret cancellation")])
    with caplog.at_level(logging.INFO, logger="law_rag.provider_attempt"):
        with pytest.raises(asyncio.CancelledError):
            await answerer.answer_core(QuestionRequest(question="비공개 질문"), [_hit()])

    events = [json.loads(record.message) for record in caplog.records]
    assert client.calls == 1
    assert len(events) == 1
    assert events[0]["operation"] == "answer_core"
    assert events[0]["attempt"] == 1
    assert events[0]["outcome"] == "failed"
    assert events[0]["failure_kind"] == "cancelled"
    assert events[0]["retry_scheduled"] is False
    assert "secret cancellation" not in caplog.text


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("path", "expected_operation"),
    [
        ("answer", "answer_detail"),
        ("answer_core", "answer_core"),
        ("answer_clarification", "clarification"),
        ("answer_core_clarification", "clarification"),
        ("answer_blocked_route", "answer_detail"),
    ],
)
async def test_answer_paths_pass_explicit_provider_operation(path, expected_operation, caplog):
    payload = core_response(summary="검증된 요약") if "core" in path else detail_response()
    answerer, _ = scripted_answerer([payload])
    request = QuestionRequest(question="질문")
    grounding = clarification()

    with caplog.at_level(logging.INFO, logger="law_rag.provider_attempt"):
        if path == "answer":
            await answerer.answer(request, [_hit()])
        elif path == "answer_core":
            await answerer.answer_core(request, [_hit()])
        elif path == "answer_clarification":
            await answerer.answer(request, [_hit()], clarification=grounding)
        elif path == "answer_core_clarification":
            await answerer.answer_core(request, [_hit()], clarification=grounding)
        else:
            await answerer.answer_blocked_route(request, "external_document_required", None)

    events = [json.loads(record.message) for record in caplog.records]
    assert len(events) == 1
    assert events[0]["operation"] == expected_operation
    assert events[0]["outcome"] == "succeeded"
    assert events[0]["retry_scheduled"] is False


@pytest.mark.asyncio
async def test_attempt_timing_is_monotonic_and_remaining_is_clamped(monkeypatch, caplog):
    answerer, _ = scripted_answerer(
        [provider_http_error(503, "secret response")], max_attempts=2, timeout_seconds=1
    )
    clock = iter([100.0, 100.0, 102.0])
    monkeypatch.setattr(
        answerer_module,
        "time",
        SimpleNamespace(monotonic=lambda: next(clock)),
    )

    with caplog.at_level(logging.INFO, logger="law_rag.provider_attempt"):
        with pytest.raises(ProviderAttemptsExhausted):
            await answerer.answer_core(QuestionRequest(question="질문"), [_hit()])

    event = json.loads(caplog.records[-1].message)
    assert event["elapsed_ms"] == 2000
    assert event["remaining_ms"] == 0
    assert event["retry_scheduled"] is False


@pytest.mark.asyncio
async def test_retry_flag_matches_next_attempt_when_threshold_is_crossed(
    monkeypatch, caplog
):
    answerer, client = scripted_answerer(
        [provider_http_error(503, "secret response")],
        max_attempts=2,
        timeout_seconds=3,
    )
    clock = iter([100.0, 100.0, 100.0, 100.001])
    monkeypatch.setattr(
        answerer_module,
        "time",
        SimpleNamespace(monotonic=lambda: next(clock)),
    )

    with caplog.at_level(logging.INFO, logger="law_rag.provider_attempt"):
        with pytest.raises(ProviderAttemptsExhausted):
            await answerer.answer_core(QuestionRequest(question="질문"), [_hit()])

    events = [json.loads(record.message) for record in caplog.records]
    assert client.calls == 1
    assert [(event["attempt"], event["retry_scheduled"]) for event in events] == [
        (1, False)
    ]
    assert "secret response" not in caplog.text


@pytest.mark.asyncio
async def test_retry_event_is_truthful_when_emission_crosses_original_deadline(
    monkeypatch,
):
    answerer, client = scripted_answerer(
        [
            provider_http_error(503, "secret response"),
            core_response(summary="retry completed before logging"),
        ],
        max_attempts=2,
        timeout_seconds=4,
    )
    clock = {"now": 100.0}
    events: list[dict[str, object]] = []
    provider_starts: list[float] = []

    monkeypatch.setattr(
        answerer_module,
        "time",
        SimpleNamespace(monotonic=lambda: clock["now"]),
    )

    original_create = client.create

    async def record_provider_start(**kwargs: object) -> object:
        provider_starts.append(clock["now"])
        return await original_create(**kwargs)

    monkeypatch.setattr(client, "create", record_provider_start)

    def emit_after_logging_delay(**event: object) -> None:
        events.append(event)
        clock["now"] += 4.1

    monkeypatch.setattr(answerer_module, "emit_provider_attempt", emit_after_logging_delay)

    result = await answerer.answer_core(QuestionRequest(question="질문"), [_hit()])

    assert result.summary == "retry completed before logging"
    assert client.calls == 2
    assert provider_starts == [100.0, 100.0]
    assert provider_starts[1] < 104.0
    assert [(event["attempt"], event["retry_scheduled"]) for event in events] == [
        (1, True),
        (2, False),
    ]
