import asyncio
import json
import logging
from types import SimpleNamespace
from typing import Any

import pytest

from app.adapters.nvidia_nim_clarification import NvidiaNimClarificationInterpreter
from app.adapters.nvidia_nim_embedder import NvidiaNimEmbedder
from app.adapters.nvidia_nim_route_classifier import NvidiaNimQuestionRouter
from app.domain.provider_attempts import ProviderAttemptsExhausted


class _ProviderHttpError(RuntimeError):
    def __init__(self, status_code: int) -> None:
        super().__init__("private provider error")
        self.status_code = status_code


class _Client:
    def __init__(self, response: object | BaseException) -> None:
        self._response = response
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self.create))
        self.embeddings = SimpleNamespace(create=self.create)

    async def create(self, **_: Any) -> object:
        if isinstance(self._response, BaseException):
            raise self._response
        return self._response

    async def close(self) -> None:
        return None


def _route_response() -> SimpleNamespace:
    return SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(
                    content=json.dumps(
                        {
                            "route": "legal_search",
                            "confidence": 0.95,
                            "reason": "법령으로 설명할 수 있습니다.",
                            "missing_fields": [],
                        }
                    )
                )
            )
        ]
    )


def _embedding_response() -> SimpleNamespace:
    return SimpleNamespace(
        data=[SimpleNamespace(index=0, embedding=[1.0, *([0.0] * 2047)])]
    )


def _clarification_response() -> SimpleNamespace:
    return SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(
                    content=json.dumps(
                        {
                            "intent": "provide_facts",
                            "submitted_facts": [],
                            "required_facts": [],
                        }
                    )
                )
            )
        ]
    )


async def invoke_route_success() -> None:
    router = NvidiaNimQuestionRouter(
        api_key="test-key",
        base_url="https://integrate.api.nvidia.com/v1",
        model="nvidia/test-router",
        timeout_seconds=10,
        max_attempts=2,
        client_factory=lambda: _Client(_route_response()),
    )
    await router.route("허가 절차를 알려주세요.")


async def invoke_embedding_success() -> None:
    embedder = NvidiaNimEmbedder(
        api_key="test-key",
        base_url="https://integrate.api.nvidia.com/v1",
        model="nvidia/nemotron-3-embed-1b",
        dimensions=512,
        timeout_seconds=10,
        client_factory=lambda: _Client(_embedding_response()),
    )
    await embedder.embed(["허가 절차"])


async def invoke_clarification_success() -> None:
    interpreter = NvidiaNimClarificationInterpreter(
        api_key="test-key",
        base_url="https://integrate.api.nvidia.com/v1",
        model="nvidia/test-clarification",
        timeout_seconds=10,
        client_factory=lambda: _Client(_clarification_response()),
    )
    await interpreter.judge_initial("허가 절차")


async def invoke_route_failure() -> None:
    router = NvidiaNimQuestionRouter(
        api_key="test-key",
        base_url="https://integrate.api.nvidia.com/v1",
        model="nvidia/test-router",
        timeout_seconds=10,
        max_attempts=2,
        client_factory=lambda: _Client(_ProviderHttpError(402)),
    )
    await router.route("비공개 질문")


async def invoke_embedding_failure() -> None:
    embedder = NvidiaNimEmbedder(
        api_key="test-key",
        base_url="https://integrate.api.nvidia.com/v1",
        model="nvidia/nemotron-3-embed-1b",
        dimensions=512,
        timeout_seconds=10,
        client_factory=lambda: _Client(_ProviderHttpError(503)),
    )
    await embedder.embed(["비공개 질문"])


async def invoke_clarification_failure() -> None:
    interpreter = NvidiaNimClarificationInterpreter(
        api_key="test-key",
        base_url="https://integrate.api.nvidia.com/v1",
        model="nvidia/test-clarification",
        timeout_seconds=10,
        client_factory=lambda: _Client(_ProviderHttpError(503)),
    )
    await interpreter.judge_initial("비공개 질문")


@pytest.mark.parametrize(
    ("invoke", "operation", "max_attempts"),
    [
        (invoke_route_success, "route", 2),
        (invoke_embedding_success, "query_embedding", 1),
        (invoke_clarification_success, "clarification", 1),
    ],
)
def test_nvidia_operation_success_emits_one_closed_event(caplog, invoke, operation, max_attempts):
    with caplog.at_level(logging.INFO, logger="law_rag.provider_attempt"):
        asyncio.run(invoke())

    assert len(caplog.records) == 1
    event = json.loads(caplog.records[-1].message)
    assert event["operation"] == operation
    assert event["outcome"] == "succeeded"
    assert event["attempt"] == 1
    assert event["max_attempts"] == max_attempts
    assert event["failure_kind"] is None
    assert event["retry_scheduled"] is False


@pytest.mark.parametrize(
    ("invoke", "operation", "max_attempts", "status_code"),
    [
        (invoke_route_failure, "route", 2, 402),
        (invoke_embedding_failure, "query_embedding", 1, 503),
        (invoke_clarification_failure, "clarification", 1, 503),
    ],
)
def test_nvidia_operation_availability_failure_emits_one_closed_event(
    caplog, invoke, operation, max_attempts, status_code
):
    with caplog.at_level(logging.INFO, logger="law_rag.provider_attempt"):
        with pytest.raises(ProviderAttemptsExhausted) as raised:
            asyncio.run(invoke())

    assert (raised.value.failure_kind, raised.value.upstream_status) == (
        "provider_http",
        status_code,
    )
    assert len(caplog.records) == 1
    event = json.loads(caplog.records[-1].message)
    assert event["operation"] == operation
    assert event["max_attempts"] == max_attempts
    assert event["outcome"] == "failed"
    assert event["failure_kind"] == "provider_http"
    assert event["upstream_status"] == status_code
    assert event["retry_scheduled"] is False
    assert "private provider error" not in caplog.text
    assert "비공개 질문" not in caplog.text
