from __future__ import annotations

import asyncio
from datetime import date
from uuid import uuid4

import pytest
from fastapi import HTTPException
from starlette.requests import Request

import app.main as main_module
from app.domain.catalog import SourceKind
from app.domain.schemas import QuestionRequest, SearchHit
from app.domain.search_queries import SearchTrace


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


async def _allow_quota(*args, **kwargs) -> bool:
    return True


@pytest.mark.asyncio
async def test_active_search_is_cancelled_and_registry_is_cleaned(monkeypatch) -> None:
    entered = asyncio.Event()
    cancelled = asyncio.Event()

    async def search(*args, **kwargs):
        entered.set()
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            cancelled.set()
            raise

    monkeypatch.setattr(main_module.repository, "search_with_trace", search)
    monkeypatch.setattr(main_module.repository, "consume_quota", _allow_quota)
    payload = QuestionRequest(
        client_request_id=uuid4(), question="전기사업 검색", answer_mode="search_only"
    )
    request = _request()

    running = asyncio.create_task(main_module.question(payload, request))
    await entered.wait()
    with pytest.raises(HTTPException) as other_owner:
        await main_module.cancel_question(payload.client_request_id, _request("127.0.0.2"))
    assert other_owner.value.status_code == 404
    response = await main_module.cancel_question(payload.client_request_id, request)

    assert response == {"cancelled": True}
    with pytest.raises(HTTPException) as exc_info:
        await running
    assert exc_info.value.status_code == 499
    assert cancelled.is_set()
    assert await main_module.question_tasks.active_count() == 0


@pytest.mark.asyncio
async def test_active_generation_is_cancelled(monkeypatch) -> None:
    entered = asyncio.Event()
    cancelled = asyncio.Event()
    hit = SearchHit(
        provision_id=uuid4(),
        document_id=uuid4(),
        document_title="전기사업법",
        source_kind=SourceKind.LAW,
        version_label="MST 1",
        effective_from=date(2026, 1, 1),
        effective_to=None,
        path="제1조",
        content="전기사업에 관한 근거",
        source_url="https://www.law.go.kr",
    )

    async def search(*args, **kwargs):
        return [hit], _trace(1)

    async def last_sync():
        return None

    class Embedder:
        async def embed(self, texts):
            return [[0.0] * 512]

    class Answerer:
        def __init__(self, **kwargs):
            pass

        async def answer(self, payload, hits):
            entered.set()
            try:
                await asyncio.Event().wait()
            except asyncio.CancelledError:
                cancelled.set()
                raise

    monkeypatch.setattr(main_module.repository, "search_with_trace", search)
    monkeypatch.setattr(main_module.repository, "last_sync", last_sync)
    monkeypatch.setattr(main_module.repository, "consume_quota", _allow_quota)
    monkeypatch.setattr(main_module, "_embedder", lambda: Embedder())
    monkeypatch.setattr(main_module, "OpenAIAnswerer", Answerer)
    monkeypatch.setattr(main_module.settings, "openai_api_key", "test-key")
    monkeypatch.setattr(main_module.settings, "ai_mode", "auto")
    monkeypatch.setattr(main_module, "ai_quota_exhausted", False)
    payload = QuestionRequest(client_request_id=uuid4(), question="전기사업 근거")
    request = _request()

    running = asyncio.create_task(main_module.question(payload, request))
    await entered.wait()
    await main_module.cancel_question(payload.client_request_id, request)

    with pytest.raises(HTTPException) as exc_info:
        await running
    assert exc_info.value.status_code == 499
    assert cancelled.is_set()
    assert await main_module.question_tasks.active_count() == 0


@pytest.mark.asyncio
async def test_unknown_and_completed_request_ids_cannot_be_cancelled(monkeypatch) -> None:
    async def search(*args, **kwargs):
        return [], _trace(0)

    async def last_sync():
        return None

    monkeypatch.setattr(main_module.repository, "search_with_trace", search)
    monkeypatch.setattr(main_module.repository, "last_sync", last_sync)
    monkeypatch.setattr(main_module.repository, "consume_quota", _allow_quota)
    request = _request()

    with pytest.raises(HTTPException) as unknown:
        await main_module.cancel_question(uuid4(), request)
    assert unknown.value.status_code == 404

    payload = QuestionRequest(
        client_request_id=uuid4(), question="완료되는 검색", answer_mode="search_only"
    )
    response = await main_module.question(payload, request)
    assert response.request_id == str(payload.client_request_id)

    with pytest.raises(HTTPException) as completed:
        await main_module.cancel_question(payload.client_request_id, request)
    assert completed.value.status_code == 404
    assert await main_module.question_tasks.active_count() == 0
