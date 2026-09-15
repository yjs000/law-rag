import asyncio
import json
import logging
from datetime import date
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

import app.main as main_module
from app.adapters.nvidia_nim_route_classifier import NvidiaNimQuestionRouter
from app.adapters.openai_answerer import DraftAnswer
from app.domain.catalog import SourceKind
from app.domain.provider_attempts import ProviderAttemptsExhausted
from app.domain.routing import QuestionRouter, RouteJudgment
from app.domain.schemas import (
    AnswerSection,
    ChecklistItem,
    CorpusTemporalState,
    QuestionRequest,
    SearchHit,
)
from app.domain.search_queries import SearchTrace

pytestmark = pytest.mark.usefixtures("ready_corpus_temporal_state")


def test_production_adapter_implements_single_question_router() -> None:
    assert issubclass(NvidiaNimQuestionRouter, QuestionRouter)


def test_nvidia_router_uses_a_fresh_client_in_each_event_loop() -> None:
    payload = json.dumps(
        {
            "route": "legal_search",
            "confidence": 0.95,
            "reason": "법령으로 설명할 수 있습니다.",
            "missing_fields": [],
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

    router = NvidiaNimQuestionRouter(
        api_key="test-key",
        base_url="https://integrate.api.nvidia.com/v1",
        model="nvidia/test-router",
        timeout_seconds=10,
        client_factory=LoopBoundClient,
    )

    first = asyncio.run(router.route("허가 절차를 알려주세요."))
    second = asyncio.run(router.route("허가 절차를 알려주세요."))

    assert first.route == second.route == "legal_search"


def test_nvidia_router_retries_transient_failure_with_a_fresh_client() -> None:
    payload = json.dumps(
        {
            "route": "legal_search",
            "confidence": 0.95,
            "reason": "법령으로 설명할 수 있습니다.",
            "missing_fields": [],
        }
    )
    clients_created = 0

    class Client:
        def __init__(self, fail: bool) -> None:
            self.fail = fail
            self.chat = SimpleNamespace(completions=self)

        async def create(self, **kwargs):
            if self.fail:
                raise RuntimeError("transient provider failure")
            return SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(content=payload))]
            )

        async def close(self) -> None:
            return None

    def client_factory() -> Client:
        nonlocal clients_created
        clients_created += 1
        return Client(fail=clients_created == 1)

    router = NvidiaNimQuestionRouter(
        api_key="test-key",
        base_url="https://integrate.api.nvidia.com/v1",
        model="nvidia/test-router",
        timeout_seconds=10,
        max_attempts=2,
        client_factory=client_factory,
    )

    decision = asyncio.run(router.route("허가 절차를 알려주세요."))

    assert decision.route == "legal_search"
    assert clients_created == 2


def test_nvidia_router_logs_each_exhausted_attempt_as_closed_safe_events(
    caplog: pytest.LogCaptureFixture,
) -> None:
    class ProviderFailure(RuntimeError):
        status_code = 503

    class Client:
        def __init__(self) -> None:
            self.chat = SimpleNamespace(completions=self)

        async def create(self, **kwargs):
            raise ProviderFailure("secret provider response")

        async def close(self) -> None:
            return None

    router = NvidiaNimQuestionRouter(
        api_key="test-key",
        base_url="https://integrate.api.nvidia.com/v1",
        model="nvidia/test-router",
        timeout_seconds=10,
        max_attempts=2,
        client_factory=Client,
    )

    with caplog.at_level(logging.INFO, logger="law_rag.provider_attempt"):
        with pytest.raises(ProviderAttemptsExhausted) as raised:
            asyncio.run(router.route("민감한 질문 원문"))

    assert (raised.value.failure_kind, raised.value.upstream_status) == ("provider_http", 503)
    events = [json.loads(record.message) for record in caplog.records]
    assert len(events) == 2
    assert [
        {
            "provider": event["provider"],
            "operation": event["operation"],
            "attempt": event["attempt"],
            "max_attempts": event["max_attempts"],
            "outcome": event["outcome"],
            "failure_kind": event["failure_kind"],
            "upstream_status": event["upstream_status"],
            "retry_scheduled": event["retry_scheduled"],
        }
        for event in events
    ] == [
        {
            "provider": "nvidia",
            "operation": "route",
            "attempt": 1,
            "max_attempts": 2,
            "outcome": "failed",
            "failure_kind": "provider_http",
            "upstream_status": 503,
            "retry_scheduled": True,
        },
        {
            "provider": "nvidia",
            "operation": "route",
            "attempt": 2,
            "max_attempts": 2,
            "outcome": "failed",
            "failure_kind": "provider_http",
            "upstream_status": 503,
            "retry_scheduled": False,
        },
    ]
    assert all(len(event["correlation"]) == 16 for event in events)
    assert all(event["elapsed_ms"] >= 0 and event["remaining_ms"] >= 0 for event in events)
    assert "secret provider response" not in caplog.text
    assert "민감한 질문 원문" not in caplog.text


@pytest.mark.asyncio
async def test_nvidia_router_uses_one_question_prompt_without_embedding_hint() -> None:
    router = NvidiaNimQuestionRouter(
        api_key="test-key",
        base_url="https://integrate.api.nvidia.com/v1",
        model="nvidia/test-router",
        timeout_seconds=10,
    )
    captured: dict[str, object] = {}

    async def create(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(
                        content=json.dumps(
                            {
                                "route": "legal_search",
                                "confidence": 0.8,
                                "reason": "법령으로 설명할 수 있습니다.",
                                "missing_fields": [],
                            }
                        )
                    )
                )
            ]
        )

    router.client = SimpleNamespace(
        chat=SimpleNamespace(completions=SimpleNamespace(create=create))
    )

    judgment = await router.route("허가 절차를 알려주세요.")

    assert judgment.route == "legal_search"
    assert judgment.confidence == 0.8
    messages = captured["messages"]
    assert len(messages) == 2
    assert "허가 절차를 알려주세요." in messages[1]["content"]
    assert "특정 부지·설비·사업" in messages[1]["content"]
    assert "토지 지목·용도지역·농지·산지·설비용량·판매용·자가소비" in messages[1]["content"]
    assert "설치할 수 있는지" in messages[1]["content"]
    assert "허가·신고·절차의 조건부 목록" in messages[1]["content"]
    assert "누락됐다는 이유만으로 clarification_required" in messages[1]["content"]
    assert "어느 경로가 적용되는지" in messages[1]["content"]
    assert "결정 사실의 실제 값" in messages[1]["content"]
    assert "결정축을 질문에서 직접 지목" in messages[1]["content"]
    assert "특정 설비에 적용될 경로" in messages[1]["content"]
    assert "하나라도 빠졌다면" in messages[1]["content"]
    assert "clarification_required를 우선" in messages[1]["content"]
    assert "상충하면 이 규칙이 legal_search 일반" in messages[1]["content"]
    assert "설명 규칙보다 우선" in messages[1]["content"]
    assert "허가·신고의 종류와 일반 구분 기준" in messages[1]["content"]
    assert "용량과 사용 방식에 따라 달라지는 자기 설비의 절차" in messages[1]["content"]
    assert "route 판단과 별개로 missing_fields를 먼저 추출" in messages[1]["content"]
    assert "1. missing_fields를 먼저 추출" in messages[1]["content"]
    assert "숫자·단위가 없으면 '설비용량'" in messages[1]["content"]
    assert "판매용·자가소비용 선택이 없으면 '전기 사용 방식'" in messages[1]["content"]
    assert "일반적인 자료 종류를 묻는 질문은" in messages[1]["content"]
    assert "특정 계약서·정산서의 실제 내용을 읽어야" in messages[1]["content"]
    assert "유사" not in " ".join(message["content"] for message in messages)
    assert "hint" not in " ".join(message["content"] for message in messages).lower()


@pytest.mark.asyncio
async def test_nvidia_router_ignores_unvalidated_provider_missing_facts() -> None:
    router = NvidiaNimQuestionRouter(
        api_key="test-key",
        base_url="https://integrate.api.nvidia.com/v1",
        model="nvidia/test-router",
        timeout_seconds=10,
    )

    async def create(**_kwargs):
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(
                        content=json.dumps(
                            {
                                "route": "legal_search",
                                "confidence": 0.9,
                                "reason": "조건부 일반 설명이 가능합니다.",
                                "missing_fields": ["설비용량"],
                            }
                        )
                    )
                )
            ]
        )

    router.client = SimpleNamespace(
        chat=SimpleNamespace(completions=SimpleNamespace(create=create))
    )

    judgment = await router.route("결정 사실의 실제 값이 없는 질문")

    assert judgment.route == "legal_search"
    assert judgment.missing_fields == ()


@pytest.mark.asyncio
async def test_nvidia_router_deterministically_finds_named_axes_without_values() -> None:
    router = NvidiaNimQuestionRouter(
        api_key="test-key",
        base_url="https://integrate.api.nvidia.com/v1",
        model="nvidia/test-router",
        timeout_seconds=10,
    )

    async def create(**_kwargs):
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(
                        content=json.dumps(
                            {
                                "route": "legal_search",
                                "confidence": 0.95,
                                "reason": "일반 설명이 가능합니다.",
                                "missing_fields": [],
                            }
                        )
                    )
                )
            ]
        )

    router.client = SimpleNamespace(
        chat=SimpleNamespace(completions=SimpleNamespace(create=create))
    )

    judgment = await router.route(
        "소규모 설비는 용량과 전기 사용 방식에 따라 절차가 어떻게 달라지나요?"
    )

    assert judgment.route == "clarification_required"
    assert judgment.missing_fields == ("설비용량", "전기 사용 방식")

@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("question", "expected_route", "expected_missing"),
    [
        (
            "제가 가진 땅에 태양광 설치가 가능한지 확인하고 싶습니다.",
            "clarification_required",
            ("토지 지목", "용도지역"),
        ),
        (
            "가족 땅에 태양광 설치가 가능한지 확인하고 싶습니다.",
            "clarification_required",
            ("토지 지목", "용도지역"),
        ),
        (
            "제가 가진 땅에 태양광 설치가 가능한지 궁금합니다. "
            "지목은 전이고 용도지역은 계획관리지역입니다.",
            "legal_search",
            (),
        ),
        (
            "제가 가진 땅에 태양광 설치가 가능한지 궁금합니다. "
            "농지나 산지이고 용도지역은 계획관리지역 또는 생산관리지역입니다.",
            "clarification_required",
            ("토지 지목", "용도지역"),
        ),
        (
            "제가 가진 땅에 태양광 설치가 가능한지 궁금합니다. "
            "지목은 전 또는 답이고 용도지역은 계획관리지역입니다.",
            "clarification_required",
            ("토지 지목",),
        ),
    ],
)
async def test_nvidia_router_scopes_land_facts_to_specific_site_feasibility(
    question: str,
    expected_route: str,
    expected_missing: tuple[str, ...],
) -> None:
    router = NvidiaNimQuestionRouter(
        api_key="test-key",
        base_url="https://integrate.api.nvidia.com/v1",
        model="nvidia/test-router",
        timeout_seconds=10,
    )

    async def create(**_kwargs):
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(
                        content=json.dumps(
                            {
                                "route": "legal_search",
                                "confidence": 0.95,
                                "reason": "일반 설명이 가능합니다.",
                                "missing_fields": [],
                            }
                        )
                    )
                )
            ]
        )

    router.client = SimpleNamespace(
        chat=SimpleNamespace(completions=SimpleNamespace(create=create))
    )

    judgment = await router.route(question)

    assert judgment.route == expected_route
    assert judgment.missing_fields == expected_missing


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "question",
    [
        "어떤 허가나 신고가 필요한지 어떻게 구분하나요?",
        "용량별 허가·신고 기준을 알려주세요.",
        "소규모 설비의 용량별 허가·신고 기준을 알려주세요.",
        "태양광 설비는 용량에 따라 허가나 신고가 어떻게 달라지나요?",
        "태양광을 설치할 수 있는 토지의 일반 조건은 무엇인가요?",
        "태양광을 땅에 설치할 수 있는 일반 조건은 무엇인가요?",
        "전기 사용 방식별 절차를 알려주세요.",
        "공사 종류별 신고 기준을 알려주세요.",
        "제 설비는 용량 3000kW, 전압 저압, 전기 사용 방식은 자가소비용이고 "
        "공사 종류는 신규 설치입니다.",
    ],
)
async def test_nvidia_router_keeps_general_permit_taxonomy_searchable(question: str) -> None:
    router = NvidiaNimQuestionRouter(
        api_key="test-key",
        base_url="https://integrate.api.nvidia.com/v1",
        model="nvidia/test-router",
        timeout_seconds=10,
    )

    async def create(**_kwargs):
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(
                        content=json.dumps(
                            {
                                "route": "legal_search",
                                "confidence": 0.95,
                                "reason": "일반 설명이 가능합니다.",
                                "missing_fields": [],
                            }
                        )
                    )
                )
            ]
        )

    router.client = SimpleNamespace(
        chat=SimpleNamespace(completions=SimpleNamespace(create=create))
    )

    judgment = await router.route(question)

    assert judgment.route == "legal_search"
    assert judgment.missing_fields == ()


@pytest.mark.asyncio
async def test_nvidia_router_searches_for_general_record_comparison_guidance() -> None:
    router = NvidiaNimQuestionRouter(
        api_key="test-key",
        base_url="https://integrate.api.nvidia.com/v1",
        model="nvidia/test-router",
        timeout_seconds=10,
    )

    async def create(**_kwargs):
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(
                        content=json.dumps(
                            {
                                "route": "external_document_required",
                                "confidence": 0.9,
                                "reason": "정산 자료 대조가 필요합니다.",
                                "missing_fields": [],
                            }
                        )
                    )
                )
            ]
        )

    router.client = SimpleNamespace(
        chat=SimpleNamespace(completions=SimpleNamespace(create=create))
    )

    judgment = await router.route("정산금이 적을 때 발전량과 공제액을 어떤 자료와 대조해야 하나요?")

    assert judgment.route == "legal_search"
    assert judgment.missing_fields == ()


@pytest.mark.asyncio
async def test_nvidia_router_keeps_supplied_document_analysis_external() -> None:
    router = NvidiaNimQuestionRouter(
        api_key="test-key",
        base_url="https://integrate.api.nvidia.com/v1",
        model="nvidia/test-router",
        timeout_seconds=10,
    )

    async def create(**_kwargs):
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(
                        content=json.dumps(
                            {
                                "route": "external_document_required",
                                "confidence": 0.9,
                                "reason": "첨부 계약서 확인이 필요합니다.",
                                "missing_fields": [],
                            }
                        )
                    )
                )
            ]
        )

    router.client = SimpleNamespace(
        chat=SimpleNamespace(completions=SimpleNamespace(create=create))
    )

    judgment = await router.route(
        "첨부한 계약서의 공제액이 맞는지 확인하려면 어떤 자료와 대조해야 하나요?"
    )
    assert judgment.route == "external_document_required"


def _payload_json(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "question": "전기사업 허가 요건을 알려주세요",
        "as_of_date": "2026-07-13",
        "answer_mode": "terra",
    }
    payload.update(overrides)
    return payload


def _hit() -> SearchHit:
    return SearchHit(
        provision_id=uuid4(),
        document_id=uuid4(),
        document_title="전기사업법",
        source_kind=SourceKind.LAW,
        version_label="MST 1",
        effective_from=date(2025, 1, 1),
        effective_to=None,
        path="제1조",
        content="전기사업에 관한 근거",
        source_url="https://www.law.go.kr",
    )


def _trace(candidate_count: int) -> SearchTrace:
    return SearchTrace(
        strategy="keyword",
        normalized_query="전기사업",
        terms=("전기사업",),
        executed_query="전기사업",
        relaxed=False,
        reference_title=None,
        reference_path=None,
        candidate_count=candidate_count,
    )


def _fast_draft() -> DraftAnswer:
    return DraftAnswer(
        summary="요약",
        scope="범위",
        sections=[AnswerSection(claim="주장", explanation="설명", citation_ids=["C1"])],
        checklist=[ChecklistItem(label="확인", status="check", citation_ids=["C1"])],
        limitations=[],
        action="fully_answerable",
    )


def _unavailable_draft() -> DraftAnswer:
    return DraftAnswer(
        summary="라우팅을 일시적으로 처리할 수 없습니다. 잠시 후 다시 시도해 주세요.",
        scope="라우팅 분류 일시 중단",
        sections=[],
        checklist=[],
        limitations=[],
        action="unanswerable",
    )


class _UnavailableAnswerer:
    async def answer_blocked_route(
        self, payload: QuestionRequest, route: str, reason: str | None
    ) -> DraftAnswer:
        return _unavailable_draft()


class _FailingRouter:
    async def route(self, question: str) -> RouteJudgment:
        raise RuntimeError("provider body must not escape")


class _ProviderTimeoutRouter:
    async def route(self, question: str) -> RouteJudgment:
        raise TimeoutError("provider timeout body must not become a route timeout")


class _SlowRouter:
    async def route(self, question: str) -> RouteJudgment:
        await asyncio.sleep(0.1)
        raise AssertionError("router should be cancelled by the stage budget")


def _configure_ai(monkeypatch) -> None:
    monkeypatch.setattr(main_module.settings, "nvidia_api_key", "test-key")
    monkeypatch.setattr(main_module.settings, "ai_mode", "auto")
    monkeypatch.setattr(main_module, "ai_quota_exhausted", False)
    monkeypatch.setattr(main_module.settings, "search_only_enabled", False)


def test_router_provider_error_returns_safe_no_search_ai_response(monkeypatch) -> None:
    _configure_ai(monkeypatch)
    embedding_calls: list[object] = []
    retrieval_calls: list[object] = []
    corpus_calls: list[object] = []

    class Embedder:
        async def embed(self, texts):
            embedding_calls.append(texts)
            raise AssertionError("embedding must not run")

    async def search(*args, **kwargs):
        retrieval_calls.append((args, kwargs))
        raise AssertionError("retrieval must not run")

    async def load_state(repository):
        corpus_calls.append(repository)
        return CorpusTemporalState(
            ready=True,
            supported_as_of_from=date(1900, 1, 1),
            supported_as_of_through=date(2099, 12, 31),
            corpus_snapshot_id="corpus-sha256:" + "a" * 64,
            eligible_provision_count=1,
        )

    monkeypatch.setattr(main_module, "_question_router", lambda: _FailingRouter())
    monkeypatch.setattr(main_module, "_load_corpus_temporal_state", load_state)
    monkeypatch.setattr(main_module, "_embedder", lambda: Embedder())
    monkeypatch.setattr(main_module.repository, "search_with_trace", search)
    monkeypatch.setattr(main_module, "_answerer", lambda: _UnavailableAnswerer())

    response = TestClient(main_module.app).post("/v1/questions", json=_payload_json())

    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "ai"
    assert body["route"] == "routing_unavailable"
    assert body["action"] == "unanswerable"
    assert body["sections"] == []
    assert body["checklist"] == []
    assert body["citations"] == []
    assert embedding_calls == []
    assert retrieval_calls == []
    assert corpus_calls == []
    assert "provider body must not escape" not in response.text
    assert not main_module.settings.search_only_enabled


def test_router_timeout_returns_safe_no_search_ai_response(monkeypatch) -> None:
    _configure_ai(monkeypatch)
    embedding_calls: list[object] = []
    retrieval_calls: list[object] = []

    class Embedder:
        async def embed(self, texts):
            embedding_calls.append(texts)
            raise AssertionError("embedding must not run")

    async def search(*args, **kwargs):
        retrieval_calls.append((args, kwargs))
        raise AssertionError("retrieval must not run")

    monkeypatch.setattr(main_module.settings, "route_classifier_timeout_seconds", 0.01)
    monkeypatch.setattr(main_module, "_question_router", lambda: _SlowRouter())
    monkeypatch.setattr(main_module, "_embedder", lambda: Embedder())
    monkeypatch.setattr(main_module.repository, "search_with_trace", search)
    monkeypatch.setattr(main_module, "_answerer", lambda: _UnavailableAnswerer())

    response = TestClient(main_module.app).post("/v1/questions", json=_payload_json())

    assert response.status_code == 200
    assert response.json()["route"] == "routing_unavailable"
    assert embedding_calls == []
    assert retrieval_calls == []
    assert not main_module.settings.search_only_enabled


def test_provider_timeout_is_reported_as_provider_error(monkeypatch, caplog) -> None:
    _configure_ai(monkeypatch)

    monkeypatch.setattr(main_module, "_question_router", lambda: _ProviderTimeoutRouter())
    monkeypatch.setattr(main_module, "_answerer", lambda: _UnavailableAnswerer())

    with caplog.at_level(logging.INFO, logger="law_rag.route_outcome"):
        response = TestClient(main_module.app).post("/v1/questions", json=_payload_json())

    assert response.status_code == 200
    assert response.json()["route"] == "routing_unavailable"
    route_events = [
        record.message for record in caplog.records if record.name == "law_rag.route_outcome"
    ]
    assert any('"reason_code": "routing_provider_error"' in event for event in route_events)
    assert all("provider timeout body" not in event for event in route_events)


def test_legal_search_runs_generation_and_validation_after_retrieval(monkeypatch, caplog) -> None:
    _configure_ai(monkeypatch)
    hit = _hit()
    calls: list[str] = []

    class Router:
        async def route(self, question: str) -> RouteJudgment:
            return RouteJudgment(
                route="legal_search", confidence=1.0, reason="legal", missing_fields=()
            )

    class Embedder:
        async def embed(self, texts):
            calls.append("embedding")
            return [[0.0] * 512]

    async def search(*args, **kwargs):
        calls.append("retrieval")
        return [hit], _trace(1)

    class Answerer:
        async def answer(self, payload, hits):
            calls.append("answer_generation")
            return _fast_draft()

    monkeypatch.setattr(main_module, "_question_router", lambda: Router())
    monkeypatch.setattr(main_module, "_embedder", lambda: Embedder())
    monkeypatch.setattr(main_module.repository, "search_with_trace", search)
    monkeypatch.setattr(main_module, "_answerer", lambda: Answerer())

    with caplog.at_level(logging.INFO, logger="law_rag.question_stage_timing"):
        response = TestClient(main_module.app).post("/v1/questions", json=_payload_json())

    assert response.status_code == 200
    assert response.json()["route"] == "legal_search"
    assert calls == ["embedding", "retrieval", "answer_generation"]
    events = [
        record.message
        for record in caplog.records
        if record.name == "law_rag.question_stage_timing"
    ]
    assert any('"stage": "answer_generation"' in event for event in events)
    assert any('"stage": "answer_validation"' in event for event in events)
    answer_generation_index = next(
        index for index, event in enumerate(events) if '"stage": "answer_generation"' in event
    )
    answer_validation_index = next(
        index for index, event in enumerate(events) if '"stage": "answer_validation"' in event
    )
    assert answer_generation_index < answer_validation_index


def test_malformed_unavailable_draft_uses_deterministic_empty_fallback(monkeypatch) -> None:
    _configure_ai(monkeypatch)

    class MalformedAnswerer:
        async def answer_blocked_route(self, payload, route, reason):
            draft = _unavailable_draft()
            draft.sections = [
                AnswerSection(claim="인용 없는 주장", explanation="위험", citation_ids=[])
            ]
            return draft

    monkeypatch.setattr(main_module, "_question_router", lambda: _FailingRouter())
    monkeypatch.setattr(main_module, "_answerer", lambda: MalformedAnswerer())

    response = TestClient(main_module.app).post("/v1/questions", json=_payload_json())

    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "ai"
    assert body["route"] == "routing_unavailable"
    assert body["action"] == "unanswerable"
    assert body["sections"] == []
    assert body["checklist"] == []
    assert body["citations"] == []
