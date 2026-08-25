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
    assert "유사" not in " ".join(message["content"] for message in messages)
    assert "hint" not in " ".join(message["content"] for message in messages).lower()


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
