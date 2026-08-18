from __future__ import annotations

import asyncio
from datetime import date
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from starlette.requests import Request

import app.main as main_module
from app.adapters.openai_answerer import DraftAnswer
from app.application.request_budget import RequestBudget
from app.domain.catalog import SourceKind
from app.domain.routing import RouteDecision
from app.domain.schemas import (
    AiFallbackReason,
    AnswerSection,
    ChecklistItem,
    QuestionRequest,
    SearchHit,
)
from app.domain.search_queries import SearchTrace

pytestmark = pytest.mark.usefixtures("ready_corpus_temporal_state")


@pytest.fixture
def client() -> TestClient:
    return TestClient(main_module.app)


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


def _legal_search_decision() -> RouteDecision:
    return RouteDecision(route="legal_search", reason_code="test", tier=1, confidence=1.0)


async def _allow_quota(*args: object, **kwargs: object) -> bool:
    return True


def _request(host: str = "127.0.0.1") -> Request:
    return Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/v1/questions",
            "headers": [],
            "client": (host, 50000),
        }
    )


def test_retrieval_timeout_returns_safe_503(client: TestClient, monkeypatch) -> None:
    async def slow_search(*args: object, **kwargs: object):
        await asyncio.sleep(0.1)
        return [], _trace(0)

    async def last_sync():
        return None

    monkeypatch.setattr(main_module.settings, "retrieval_timeout_seconds", 0.01)
    monkeypatch.setattr(main_module.repository, "search_with_trace", slow_search)
    monkeypatch.setattr(main_module.repository, "last_sync", last_sync)
    monkeypatch.setattr(main_module.repository, "consume_quota", _allow_quota)

    response = client.post(
        "/v1/questions", json=_payload_json(answer_mode="search_only")
    )

    assert response.status_code == 503
    assert response.json()["detail"] == (
        "법령 검색 시간이 초과되었습니다. 잠시 후 다시 시도해 주세요."
    )


def test_generation_timeout_returns_search_fallback(client: TestClient, monkeypatch) -> None:
    hit = _hit()

    async def search(*args: object, **kwargs: object):
        return [hit], _trace(1)

    async def last_sync():
        return None

    class Embedder:
        async def embed(self, texts: list[str]) -> list[list[float]]:
            return [[0.0] * 512]

    class SlowAnswerer:
        async def answer(self, payload: QuestionRequest, hits: list[SearchHit]):
            await asyncio.sleep(0.1)

    monkeypatch.setattr(main_module.settings, "answer_timeout_seconds", 0.01)
    monkeypatch.setattr(main_module, "route_tier1", lambda question: _legal_search_decision())
    monkeypatch.setattr(main_module.repository, "search_with_trace", search)
    monkeypatch.setattr(main_module.repository, "last_sync", last_sync)
    monkeypatch.setattr(main_module.repository, "consume_quota", _allow_quota)
    monkeypatch.setattr(main_module, "_embedder", lambda: Embedder())
    monkeypatch.setattr(main_module, "_answerer", lambda: SlowAnswerer())
    monkeypatch.setattr(main_module.settings, "nvidia_api_key", "test-key")
    monkeypatch.setattr(main_module.settings, "ai_mode", "auto")
    monkeypatch.setattr(main_module, "ai_quota_exhausted", False)

    response = client.post("/v1/questions", json=_payload_json())

    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "search_only"
    assert body["fallback_reason"] == "generation_error"
    assert body["citations"]


def test_routing_timeout_continues_as_legal_search(client: TestClient, monkeypatch) -> None:
    hit = _hit()

    class SlowClassifier:
        async def classify(self, question: str, hint: object):
            await asyncio.sleep(0.1)

    async def search(*args: object, **kwargs: object):
        return [hit], _trace(1)

    async def last_sync():
        return None

    class Embedder:
        async def embed(self, texts: list[str]) -> list[list[float]]:
            return [[0.0] * 512]

    monkeypatch.setattr(main_module.settings, "route_classifier_timeout_seconds", 0.01)
    monkeypatch.setattr(main_module, "_route_classifier", lambda: SlowClassifier())
    monkeypatch.setattr(main_module.repository, "search_with_trace", search)
    monkeypatch.setattr(main_module.repository, "last_sync", last_sync)
    monkeypatch.setattr(main_module.repository, "consume_quota", _allow_quota)
    monkeypatch.setattr(main_module, "_embedder", lambda: Embedder())
    monkeypatch.setattr(main_module, "_answerer", lambda: _StubAnswerer())
    monkeypatch.setattr(main_module.settings, "nvidia_api_key", "test-key")
    monkeypatch.setattr(main_module.settings, "ai_mode", "auto")
    monkeypatch.setattr(main_module, "ai_quota_exhausted", False)

    response = client.post(
        "/v1/questions",
        json=_payload_json(question="전기사업 관련 절차가 궁금합니다"),
    )

    assert response.status_code == 200
    assert response.json()["route"] == "legal_search"


class _StubAnswerer:
    async def answer(self, payload: QuestionRequest, hits: list[SearchHit]) -> DraftAnswer:
        return _fast_draft()


def test_embedding_timeout_falls_back_to_lexical_retrieval(
    client: TestClient, monkeypatch
) -> None:
    hit = _hit()
    captured: dict[str, object] = {}

    async def search(query: str, as_of_date: date, limit: int, vector, profile_key):
        captured["vector"] = vector
        captured["profile_key"] = profile_key
        return [hit], _trace(1)

    async def last_sync():
        return None

    class SlowEmbedder:
        async def embed(self, texts: list[str]) -> list[list[float]]:
            await asyncio.sleep(0.1)
            return [[0.0] * 512]

    monkeypatch.setattr(main_module.settings, "question_embedding_timeout_seconds", 0.01)
    monkeypatch.setattr(main_module, "route_tier1", lambda question: _legal_search_decision())
    monkeypatch.setattr(main_module.repository, "search_with_trace", search)
    monkeypatch.setattr(main_module.repository, "last_sync", last_sync)
    monkeypatch.setattr(main_module.repository, "consume_quota", _allow_quota)
    monkeypatch.setattr(main_module, "_embedder", lambda: SlowEmbedder())
    monkeypatch.setattr(main_module, "_answerer", lambda: _StubAnswerer())
    monkeypatch.setattr(main_module.settings, "nvidia_api_key", "test-key")
    monkeypatch.setattr(main_module.settings, "ai_mode", "auto")
    monkeypatch.setattr(main_module, "ai_quota_exhausted", False)

    response = client.post("/v1/questions", json=_payload_json())

    assert response.status_code == 200
    assert captured["vector"] is None
    assert captured["profile_key"] is None


@pytest.mark.asyncio
async def test_generation_never_starts_when_only_reserve_remains(monkeypatch) -> None:
    hit = _hit()
    generation_called = False

    async def search(*args: object, **kwargs: object):
        return [hit], _trace(1)

    async def last_sync():
        return None

    class Embedder:
        async def embed(self, texts: list[str]) -> list[list[float]]:
            return [[0.0] * 512]

    class Answerer:
        async def answer(self, payload: QuestionRequest, hits: list[SearchHit]) -> DraftAnswer:
            nonlocal generation_called
            generation_called = True
            return _fast_draft()

    monkeypatch.setattr(main_module, "route_tier1", lambda question: _legal_search_decision())
    monkeypatch.setattr(main_module.repository, "search_with_trace", search)
    monkeypatch.setattr(main_module.repository, "last_sync", last_sync)
    monkeypatch.setattr(main_module.repository, "consume_quota", _allow_quota)
    monkeypatch.setattr(main_module, "_embedder", lambda: Embedder())
    monkeypatch.setattr(main_module, "_answerer", lambda: Answerer())
    monkeypatch.setattr(main_module.settings, "nvidia_api_key", "test-key")
    monkeypatch.setattr(main_module.settings, "ai_mode", "auto")
    monkeypatch.setattr(main_module, "ai_quota_exhausted", False)

    payload = QuestionRequest(client_request_id=uuid4(), question="전기사업 허가 절차 문의")
    request = _request()

    # Embedding and retrieval each see plenty of remaining budget; by the time
    # generation checks its own slice, only the response reserve is left.
    clock_values = iter([900.0, 950.0, 998.0])
    budget = RequestBudget(
        deadline=1000.0, reserve_seconds=3.0, clock=lambda: next(clock_values)
    )

    response = await main_module._answer_question(
        payload, request, None, budget, main_module.repository
    )

    assert generation_called is False
    assert response.mode == "search_only"
    assert response.fallback_reason == AiFallbackReason.GENERATION_ERROR
