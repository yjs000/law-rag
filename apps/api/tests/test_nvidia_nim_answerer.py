from __future__ import annotations

import asyncio
import json
from datetime import date
from types import SimpleNamespace
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.adapters.nvidia_nim_answerer import NvidiaNimAnswerer
from app.adapters.openai_answerer import (
    CoreDraft,
    build_blocked_route_messages,
    build_core_messages,
    build_messages,
    build_messages_v2,
)
from app.domain.catalog import SourceKind
from app.domain.provider_attempts import ProviderAttemptsExhausted
from app.domain.schemas import QuestionRequest, SearchHit


def _answerer() -> NvidiaNimAnswerer:
    return NvidiaNimAnswerer(
        api_key="test-key",
        base_url="https://integrate.api.nvidia.com/v1",
        model="nvidia/nemotron-3-ultra-550b-a55b",
        timeout_seconds=30,
        max_output_tokens=4096,
    )


def _client(create):
    completions = SimpleNamespace(create=create)
    return SimpleNamespace(chat=SimpleNamespace(completions=completions))


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

def test_nvidia_answerer_uses_a_fresh_client_in_each_event_loop() -> None:
    payload = json.dumps(
        {
            "summary": "전기사업에 관한 근거입니다.",
            "citation_ids": ["C1"],
            "action": "fully_answerable",
        }
    )

    class LoopBoundClient:
        def __init__(self) -> None:
            self.loop = asyncio.get_running_loop()
            self.chat = SimpleNamespace(completions=self)

        async def create(self, **kwargs):
            assert asyncio.get_running_loop() is self.loop
            return SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(content=payload))]
            )

        async def close(self) -> None:
            return None

    answerer = NvidiaNimAnswerer(
        api_key="test-key",
        base_url="https://integrate.api.nvidia.com/v1",
        model="nvidia/nemotron-3-ultra-550b-a55b",
        timeout_seconds=30,
        max_output_tokens=4096,
        client_factory=LoopBoundClient,
    )
    request = QuestionRequest(question="전기사업 근거")
    hits = [_hit()]

    first = asyncio.run(answerer.answer_core(request, hits))
    second = asyncio.run(answerer.answer_core(request, hits))

    assert first.summary == second.summary == "전기사업에 관한 근거입니다."


@pytest.mark.asyncio
@pytest.mark.parametrize("action", ["fully_answerable", "unanswerable"])
async def test_nvidia_core_plain_summary_preserves_citations_and_scope(action: str) -> None:
    original = (
        "전기사업을 하려는 자는 허가를 받아야 한다.\n"
        "시설을 설치하려는 자는 서류를 내야 합니다. "
        "법령에는 “적용 범위입니다. 사업을 하려는 자는 허가를 받아야 한다.”라고 적혀 있습니다. "
        "사업을 하려는 자는 예외가 없으면, 허가를 받아야 한다. "
        "변경하려는 자는 신고해야 하며 서류도 내야 한다. "
        "사업을 하려는 자는 예외 사유가 없어도 허가를 받고 신고해야 한다.\n"
        "사업을 하려는 자는 허가를 받아야 하되 신고도 해야 한다.\n"
        "> 사업을 하려는 자는 허가를 받아야 한다.\n"
        "담당 기관에 확인하세요."
    )
    expected = original.replace(
        "전기사업을 하려는 자는 허가를 받아야 한다.",
        "전기사업을 하려면 허가를 받아야 합니다.",
    ).replace(
        "시설을 설치하려는 자는 서류를 내야 합니다.",
        "시설을 설치하려면 서류를 내야 합니다.",
    )
    answerer = _answerer()
    citation_ids = ["C1"] if action == "fully_answerable" else []

    async def create(**kwargs):
        payload = {"summary": original, "citation_ids": citation_ids, "action": action}
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps(payload)))]
        )

    answerer.client = _client(create)
    draft = await answerer.answer_core(QuestionRequest(question="전기사업 근거"), [_hit()])

    assert draft.summary == (expected if action == "fully_answerable" else original)
    assert draft.citation_ids == citation_ids
    assert draft.action == action


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
async def test_nvidia_nim_core_generation_uses_summary_only_contract() -> None:
    answerer = _answerer()
    captured: dict[str, object] = {}
    payload = {
        "summary": "전기사업에 관한 근거입니다.",
        "citation_ids": ["C1"],
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

    core = await answerer.answer_core(request, hits)

    assert core == CoreDraft.model_validate(payload)
    assert captured["messages"] == build_core_messages(request, hits)
    assert set(captured["extra_body"]["guided_json"]["properties"]) == {
        "summary",
        "citation_ids",
        "action",
        "decision_limitations",
        "missing_information",
    }
    assert "decision_limitations" not in core.model_dump(mode="json")


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
    answerer.client = _client(create)
    with pytest.raises(ProviderAttemptsExhausted, match="^provider attempts exhausted$") as raised:
        await answerer.answer(QuestionRequest(question="전기사업 근거"), [_hit()])
    assert calls == 3
    assert (raised.value.failure_kind, raised.value.upstream_status) == ("provider_http", 503)


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [402, 429])
async def test_nvidia_nim_does_not_retry_billing_or_quota_errors(status: int) -> None:
    answerer = _answerer()
    calls = 0
    async def create(**kwargs):
        nonlocal calls
        calls += 1
        error = Exception("quota exceeded")
        error.status_code = status  # type: ignore[attr-defined]
        raise error
    answerer.client = _client(create)
    with pytest.raises(ProviderAttemptsExhausted, match="^provider attempts exhausted$") as raised:
        await answerer.answer(QuestionRequest(question="전기사업 근거"), [_hit()])
    assert calls == 1
    assert (raised.value.failure_kind, raised.value.upstream_status) == ("provider_http", status)


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
    answerer.client = _client(create)
    with pytest.raises(ProviderAttemptsExhausted, match="^provider attempts exhausted$") as raised:
        await answerer.answer(QuestionRequest(question="전기사업 근거"), [_hit()])

    # Budget is 10s and each attempt burns 9s, so a second attempt (18s) would
    # blow past the deadline - only one attempt should have been made.
    assert calls == 1
    assert (raised.value.failure_kind, raised.value.upstream_status) == ("provider_http", 503)


@pytest.mark.asyncio
async def test_nvidia_nim_enforces_overall_deadline_when_provider_ignores_request_timeout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    answerer = NvidiaNimAnswerer(
        api_key="test-key",
        base_url="https://integrate.api.nvidia.com/v1",
        model="nvidia/nemotron-3-ultra-550b-a55b",
        timeout_seconds=0.01,
        max_output_tokens=4096,
        max_attempts=1,
    )

    async def stuck_attempt(*args, **kwargs):
        await asyncio.sleep(0.05)
        return CoreDraft(summary="too late", citation_ids=[], action="unanswerable")

    monkeypatch.setattr(answerer, "_attempt", stuck_attempt)

    with pytest.raises(ProviderAttemptsExhausted, match="^provider attempts exhausted$") as raised:
        await answerer.answer_core(QuestionRequest(question="전기사업 근거"), [_hit()])

    assert (raised.value.failure_kind, raised.value.upstream_status) == ("timeout", None)


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


@pytest.mark.asyncio
async def test_answer_blocked_route_uses_dedicated_prompt_without_evidence() -> None:
    answerer = _answerer()
    captured: dict[str, object] = {}
    payload = {
        "summary": "이 시스템은 실시간 가격 정보에 연결되어 있지 않아 답할 수 없습니다.",
        "scope": "검색 미실행",
        "sections": [],
        "checklist": [],
        "limitations": [],
        "action": "unanswerable",
    }

    async def create(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps(payload)))]
        )

    answerer.client = SimpleNamespace(
        chat=SimpleNamespace(completions=SimpleNamespace(create=create))
    )
    request = QuestionRequest(question="지금 시세로 전기를 팔면 얼마나 받을 수 있나요?")
    draft = await answerer.answer_blocked_route(request, "realtime_required", None)

    assert draft.action == "unanswerable"
    assert captured["messages"] == build_blocked_route_messages(
        request, "realtime_required", None
    )
    assert "근거:" not in captured["messages"][0]["content"]


def test_build_blocked_route_messages_rejects_unsupported_route() -> None:
    request = QuestionRequest(question="아무 질문")

    with pytest.raises(ValueError, match="legal_search"):
        build_blocked_route_messages(request, "legal_search", None)


@pytest.mark.asyncio
async def test_answer_blocked_route_passes_reason_as_untrusted_hint() -> None:
    answerer = _answerer()
    payload = {
        "summary": "부족한 사실을 확인해야 합니다.",
        "scope": "검색 미실행",
        "sections": [],
        "checklist": [],
        "limitations": [],
        "action": "clarification_required",
        "missing_information": ["설비용량"],
    }

    async def create(**kwargs):
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps(payload)))]
        )

    answerer.client = SimpleNamespace(
        chat=SimpleNamespace(completions=SimpleNamespace(create=create))
    )
    request = QuestionRequest(question="이거 애매한 질문인데 확인해줄래요?")
    draft = await answerer.answer_blocked_route(
        request, "clarification_required", "설비용량에 따라 절차가 갈린다"
    )

    assert draft.action == "clarification_required"
    assert draft.missing_information == ["설비용량"]


@pytest.mark.asyncio
async def test_answer_blocked_route_retries_transient_failures() -> None:
    answerer = _answerer()
    payload = {
        "summary": "이 시스템은 해당 문서에 연결되어 있지 않아 답할 수 없습니다.",
        "scope": "검색 미실행",
        "sections": [],
        "checklist": [],
        "limitations": [],
        "action": "unanswerable",
    }
    calls = 0

    async def create(**kwargs):
        nonlocal calls
        calls += 1
        if calls < 2:
            error = Exception("Service Unavailable")
            error.status_code = 503  # type: ignore[attr-defined]
            raise error
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps(payload)))]
        )

    answerer.client = SimpleNamespace(
        chat=SimpleNamespace(completions=SimpleNamespace(create=create))
    )
    draft = await answerer.answer_blocked_route(
        QuestionRequest(question="정산서를 보니 금액이 안 맞는데 어떻게 확인하나요?"),
        "external_document_required",
        None,
    )

    assert draft.action == "unanswerable"
    assert calls == 2
