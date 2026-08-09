from __future__ import annotations

import json
from datetime import date
from types import SimpleNamespace
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.adapters.nvidia_nim_answerer import NvidiaNimAnswerer
from app.adapters.openai_answerer import build_messages, build_messages_v2
from app.domain.catalog import SourceKind
from app.domain.schemas import QuestionRequest, SearchHit


def _answerer() -> NvidiaNimAnswerer:
    return NvidiaNimAnswerer(
        api_key="test-key",
        base_url="https://integrate.api.nvidia.com/v1",
        model="nvidia/nemotron-3-ultra-550b-a55b",
        timeout_seconds=30,
        max_output_tokens=4096,
    )


def _hit() -> SearchHit:
    return SearchHit(
        provision_id=uuid4(),
        document_id=uuid4(),
        document_title="전기사업법",
        source_kind=SourceKind.LAW,
        version_label="MST 1",
        effective_from=date(2026, 1, 1),
        effective_to=None,
        path="제1조",
        content="전기사업에 관한 근거",
        source_url="https://www.law.go.kr/법령/전기사업법/제1조",
    )


@pytest.mark.asyncio
async def test_nvidia_nim_uses_guided_schema_and_validates_answer() -> None:
    answerer = _answerer()
    captured: dict[str, object] = {}
    payload = {
        "summary": "전기사업에 관한 근거입니다.",
        "scope": "기준일 현재 검색 범위",
        "sections": [
            {
                "claim": "전기사업에 관한 근거",
                "explanation": "원문 확인",
                "citation_ids": ["C1"],
            }
        ],
        "checklist": [
            {"label": "원문 확인", "status": "check", "citation_ids": ["C1"]}
        ],
        "limitations": [],
        "action": "fully_answerable",
    }

    async def create(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps(payload)))]
        )

    answerer.client = SimpleNamespace(
        chat=SimpleNamespace(completions=SimpleNamespace(create=create))
    )
    draft = await answerer.answer(QuestionRequest(question="전기사업 근거"), [_hit()])

    assert draft.sections[0].citation_ids == ["C1"]
    assert captured["model"] == "nvidia/nemotron-3-ultra-550b-a55b"
    assert captured["max_tokens"] == 4096
    assert captured["extra_body"]["chat_template_kwargs"] == {"enable_thinking": False}
    assert captured["extra_body"]["guided_json"]["type"] == "object"


@pytest.mark.asyncio
@pytest.mark.parametrize("content", [None, "not-json", "{}"])
async def test_nvidia_nim_rejects_missing_or_invalid_structured_output(content) -> None:
    answerer = _answerer()

    async def create(**kwargs):
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=content))]
        )

    answerer.client = SimpleNamespace(
        chat=SimpleNamespace(completions=SimpleNamespace(create=create))
    )
    expected = ValueError if content is None else ValidationError
    with pytest.raises(expected):
        await answerer.answer(QuestionRequest(question="전기사업 근거"), [_hit()])


@pytest.mark.asyncio
async def test_nvidia_nim_retries_transient_failures_and_succeeds() -> None:
    answerer = _answerer()
    payload = {
        "summary": "전기사업에 관한 근거입니다.",
        "scope": "기준일 현재 검색 범위",
        "sections": [
            {"claim": "전기사업에 관한 근거", "explanation": "원문 확인", "citation_ids": ["C1"]}
        ],
        "checklist": [{"label": "원문 확인", "status": "check", "citation_ids": ["C1"]}],
        "limitations": [],
        "action": "fully_answerable",
    }
    calls = 0

    async def create(**kwargs):
        nonlocal calls
        calls += 1
        if calls < 3:
            error = Exception("Service Unavailable")
            error.status_code = 503  # type: ignore[attr-defined]
            raise error
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps(payload)))]
        )

    answerer.client = SimpleNamespace(
        chat=SimpleNamespace(completions=SimpleNamespace(create=create))
    )
    draft = await answerer.answer(QuestionRequest(question="전기사업 근거"), [_hit()])

    assert draft.sections[0].citation_ids == ["C1"]
    assert calls == 3


@pytest.mark.asyncio
async def test_nvidia_nim_stops_after_max_attempts_and_raises_last_error() -> None:
    answerer = _answerer()
    calls = 0

    async def create(**kwargs):
        nonlocal calls
        calls += 1
        error = Exception(f"Service Unavailable #{calls}")
        error.status_code = 503  # type: ignore[attr-defined]
        raise error

    answerer.client = SimpleNamespace(
        chat=SimpleNamespace(completions=SimpleNamespace(create=create))
    )
    with pytest.raises(Exception, match="Service Unavailable #3"):
        await answerer.answer(QuestionRequest(question="전기사업 근거"), [_hit()])

    assert calls == 3


@pytest.mark.asyncio
@pytest.mark.parametrize("status_code", [402, 429])
async def test_nvidia_nim_does_not_retry_billing_or_quota_errors(status_code: int) -> None:
    answerer = _answerer()
    calls = 0

    async def create(**kwargs):
        nonlocal calls
        calls += 1
        error = Exception("quota exceeded")
        error.status_code = status_code  # type: ignore[attr-defined]
        raise error

    answerer.client = SimpleNamespace(
        chat=SimpleNamespace(completions=SimpleNamespace(create=create))
    )
    with pytest.raises(Exception, match="quota exceeded"):
        await answerer.answer(QuestionRequest(question="전기사업 근거"), [_hit()])

    assert calls == 1


@pytest.mark.asyncio
async def test_nvidia_nim_stops_retrying_once_the_overall_deadline_is_gone(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    answerer = NvidiaNimAnswerer(
        api_key="test-key",
        base_url="https://integrate.api.nvidia.com/v1",
        model="nvidia/nemotron-3-ultra-550b-a55b",
        timeout_seconds=10,
        max_output_tokens=4096,
    )
    calls = 0
    clock = {"now": 0.0}
    monkeypatch.setattr(
        "app.adapters.nvidia_nim_answerer.time.monotonic", lambda: clock["now"]
    )

    async def create(**kwargs):
        nonlocal calls
        calls += 1
        clock["now"] += 9  # each attempt eats most of the 10s budget
        error = Exception("Service Unavailable")
        error.status_code = 503  # type: ignore[attr-defined]
        raise error

    answerer.client = SimpleNamespace(
        chat=SimpleNamespace(completions=SimpleNamespace(create=create))
    )
    with pytest.raises(Exception, match="Service Unavailable"):
        await answerer.answer(QuestionRequest(question="전기사업 근거"), [_hit()])

    # Budget is 10s and each attempt burns 9s, so a second attempt (18s) would
    # blow past the deadline - only one attempt should have been made.
    assert calls == 1


def test_nvidia_nim_rejects_unapproved_base_url() -> None:
    with pytest.raises(ValueError, match="unsupported NVIDIA"):
        NvidiaNimAnswerer(
            api_key="test-key",
            base_url="https://attacker.example/v1",
            model="nvidia/nemotron-3-ultra-550b-a55b",
            timeout_seconds=30,
            max_output_tokens=4096,
        )


@pytest.mark.asyncio
async def test_nvidia_nim_defaults_to_v1_message_builder() -> None:
    answerer = _answerer()
    captured: dict[str, object] = {}
    payload = {
        "summary": "전기사업에 관한 근거입니다.",
        "scope": "기준일 현재 검색 범위",
        "sections": [
            {"claim": "전기사업에 관한 근거", "explanation": "원문 확인", "citation_ids": ["C1"]}
        ],
        "checklist": [{"label": "원문 확인", "status": "check", "citation_ids": ["C1"]}],
        "limitations": [],
        "action": "fully_answerable",
    }

    async def create(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps(payload)))]
        )

    answerer.client = SimpleNamespace(
        chat=SimpleNamespace(completions=SimpleNamespace(create=create))
    )
    request = QuestionRequest(question="전기사업 근거")
    hits = [_hit()]
    await answerer.answer(request, hits)

    assert captured["messages"] == build_messages(request, hits)


@pytest.mark.asyncio
async def test_nvidia_nim_uses_injected_message_builder() -> None:
    answerer = NvidiaNimAnswerer(
        api_key="test-key",
        base_url="https://integrate.api.nvidia.com/v1",
        model="nvidia/nemotron-3-ultra-550b-a55b",
        timeout_seconds=30,
        max_output_tokens=4096,
        message_builder=build_messages_v2,
    )
    captured: dict[str, object] = {}
    payload = {
        "summary": "전기사업에 관한 근거입니다.",
        "scope": "기준일 현재 검색 범위",
        "sections": [
            {"claim": "전기사업에 관한 근거", "explanation": "원문 확인", "citation_ids": ["C1"]}
        ],
        "checklist": [{"label": "원문 확인", "status": "check", "citation_ids": ["C1"]}],
        "limitations": [],
        "action": "fully_answerable",
    }

    async def create(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps(payload)))]
        )

    answerer.client = SimpleNamespace(
        chat=SimpleNamespace(completions=SimpleNamespace(create=create))
    )
    request = QuestionRequest(question="전기사업 근거")
    hits = [_hit()]
    await answerer.answer(request, hits)

    assert captured["messages"] == build_messages_v2(request, hits)
    assert captured["messages"] != build_messages(request, hits)
