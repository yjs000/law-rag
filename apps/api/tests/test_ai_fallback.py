from datetime import date
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

import app.main as main_module
from app.domain.catalog import SourceKind
from app.domain.schemas import SearchHit
from app.domain.search_queries import SearchTrace


def _with_trace(search):
    async def traced(*args, **kwargs):
        hits = await search(*args, **kwargs)
        return hits, SearchTrace(
            strategy="keyword",
            normalized_query="test",
            terms=("test",),
            executed_query="test",
            relaxed=False,
            reference_title=None,
            reference_path=None,
            candidate_count=len(hits),
        )

    return traced


class FailingAnswerer:
    models: list[str] = []
    error: Exception = RuntimeError("runtime failure")

    def __init__(self, *, api_key: str, model: str) -> None:
        self.models.append(model)

    async def answer(self, payload, hits):
        raise self.error


class QuotaFailure(Exception):
    status_code = 429


class BillingFailure(Exception):
    status_code = 402


@pytest.mark.parametrize(
    ("error", "expected_reason"),
    [
        (RuntimeError("runtime"), "generation_error"),
        (PermissionError("authorization"), "generation_error"),
        (LookupError("model unavailable"), "generation_error"),
        (QuotaFailure("quota"), "billing_or_quota_error"),
    ],
)
def test_all_generation_failures_fall_back_without_another_model(
    monkeypatch, error, expected_reason
) -> None:
    hit = SearchHit(
        provision_id=uuid4(),
        document_id=uuid4(),
        document_title="전기사업법",
        source_kind=SourceKind.LAW,
        version_label="MST 1",
        effective_from=date(2025, 1, 1),
        effective_to=None,
        path="제1조",
        content="에너지 관련 근거",
        source_url="https://www.law.go.kr",
        score=1,
    )

    async def search(*args, **kwargs):
        return [hit]

    async def last_sync():
        return None

    async def consume_quota(*args, **kwargs):
        return True

    class NoopEmbedder:
        async def embed(self, texts):
            return [[0.0] * 512]

    FailingAnswerer.models = []
    FailingAnswerer.error = error
    monkeypatch.setattr(main_module.repository, "search_with_trace", _with_trace(search))
    monkeypatch.setattr(main_module.repository, "last_sync", last_sync)
    monkeypatch.setattr(main_module.repository, "consume_quota", consume_quota)
    monkeypatch.setattr(main_module, "OpenAIAnswerer", FailingAnswerer)
    monkeypatch.setattr(main_module, "_embedder", lambda: NoopEmbedder())
    monkeypatch.setattr(main_module.settings, "openai_api_key", "test-key")
    monkeypatch.setattr(main_module, "ai_quota_exhausted", False)

    response = TestClient(main_module.app).post(
        "/v1/questions",
        json={
            "question": "에너지 근거를 알려주세요",
            "as_of_date": "2026-07-13",
            "project_stage": "planning",
        },
    )
    assert response.status_code == 200
    assert response.json()["mode"] == "search_only"
    assert response.json()["requested_answer_mode"] == "terra"
    assert response.json()["fallback_reason"] == expected_reason
    assert FailingAnswerer.models == ["gpt-5.6-terra"]


@pytest.mark.parametrize("error", [BillingFailure("billing"), QuotaFailure("quota")])
def test_billing_or_quota_failure_disables_terra_for_later_requests(
    monkeypatch, error
) -> None:
    hit = SearchHit(
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
        score=1,
    )

    async def search(*args, **kwargs):
        return [hit]

    async def last_sync():
        return None

    async def consume_quota(*args, **kwargs):
        return True

    async def corpus_items():
        return []

    class NoopEmbedder:
        async def embed(self, texts):
            return [[0.0] * 512]

    FailingAnswerer.models = []
    FailingAnswerer.error = error
    monkeypatch.setattr(main_module.repository, "search_with_trace", _with_trace(search))
    monkeypatch.setattr(main_module.repository, "last_sync", last_sync)
    monkeypatch.setattr(main_module.repository, "consume_quota", consume_quota)
    monkeypatch.setattr(main_module.repository, "corpus_items", corpus_items)
    monkeypatch.setattr(main_module, "OpenAIAnswerer", FailingAnswerer)
    monkeypatch.setattr(main_module, "_embedder", lambda: NoopEmbedder())
    monkeypatch.setattr(main_module.settings, "openai_api_key", "test-key")
    monkeypatch.setattr(main_module.settings, "ai_mode", "auto")
    monkeypatch.setattr(main_module, "ai_quota_exhausted", False)
    client = TestClient(main_module.app)
    request = {"question": "전기사업 근거를 알려주세요", "answer_mode": "terra"}

    first = client.post("/v1/questions", json=request)
    second = client.post("/v1/questions", json=request)
    status = client.get("/v1/corpus/status")

    assert first.json()["fallback_reason"] == "billing_or_quota_error"
    assert second.json()["fallback_reason"] == "quota_exhausted"
    assert second.json()["requested_answer_mode"] == "terra"
    assert status.json()["ai_available"] is False
    assert status.json()["ai_unavailable_reason"] == "quota_exhausted"
    assert FailingAnswerer.models == ["gpt-5.6-terra"]


def test_disabled_ai_reports_safe_reason_without_calling_openai(monkeypatch) -> None:
    async def search(*args, **kwargs):
        return []

    async def last_sync():
        return None

    async def consume_quota(*args, **kwargs):
        return True

    FailingAnswerer.models = []
    monkeypatch.setattr(main_module.repository, "search_with_trace", _with_trace(search))
    monkeypatch.setattr(main_module.repository, "last_sync", last_sync)
    monkeypatch.setattr(main_module.repository, "consume_quota", consume_quota)
    monkeypatch.setattr(main_module, "OpenAIAnswerer", FailingAnswerer)
    monkeypatch.setattr(main_module.settings, "ai_mode", "off")
    monkeypatch.setattr(main_module, "ai_quota_exhausted", False)

    response = TestClient(main_module.app).post(
        "/v1/questions", json={"question": "전기사업 근거", "answer_mode": "terra"}
    )

    assert response.json()["requested_answer_mode"] == "terra"
    assert response.json()["fallback_reason"] == "ai_disabled"
    assert FailingAnswerer.models == []


def test_embedding_failure_with_no_keyword_evidence_is_explained(monkeypatch) -> None:
    async def search(*args, **kwargs):
        return []

    async def last_sync():
        return None

    async def consume_quota(*args, **kwargs):
        return True

    class FailingEmbedder:
        async def embed(self, texts):
            raise RuntimeError("must not be returned to clients")

    monkeypatch.setattr(main_module.repository, "search_with_trace", _with_trace(search))
    monkeypatch.setattr(main_module.repository, "last_sync", last_sync)
    monkeypatch.setattr(main_module.repository, "consume_quota", consume_quota)
    monkeypatch.setattr(main_module, "_embedder", lambda: FailingEmbedder())
    monkeypatch.setattr(main_module.settings, "openai_api_key", "test-key")
    monkeypatch.setattr(main_module.settings, "ai_mode", "auto")
    monkeypatch.setattr(main_module, "ai_quota_exhausted", False)

    response = TestClient(main_module.app).post(
        "/v1/questions", json={"question": "전기사업 근거", "answer_mode": "terra"}
    )

    assert response.json()["fallback_reason"] == "embedding_error"
    assert "must not be returned" not in response.text


def test_explicit_search_only_mode_never_calls_generation_model(monkeypatch) -> None:
    async def search(*args, **kwargs):
        return []

    async def last_sync():
        return None

    async def consume_quota(*args, **kwargs):
        return True

    FailingAnswerer.models = []

    class ForbiddenEmbedder:
        async def embed(self, texts):
            raise AssertionError("search_only must not call the embedding model")

    monkeypatch.setattr(main_module.repository, "search_with_trace", _with_trace(search))
    monkeypatch.setattr(main_module.repository, "last_sync", last_sync)
    monkeypatch.setattr(main_module.repository, "consume_quota", consume_quota)
    monkeypatch.setattr(main_module, "OpenAIAnswerer", FailingAnswerer)
    monkeypatch.setattr(main_module, "_embedder", lambda: ForbiddenEmbedder())
    monkeypatch.setattr(main_module.settings, "openai_api_key", "test-key")
    monkeypatch.setattr(main_module, "ai_quota_exhausted", False)

    response = TestClient(main_module.app).post(
        "/v1/questions",
        json={
            "question": "원문만 검색해 주세요",
            "as_of_date": "2026-07-14",
            "answer_mode": "search_only",
        },
    )

    assert response.status_code == 200
    assert response.json()["mode"] == "search_only"
    assert response.json()["requested_answer_mode"] == "search_only"
    assert response.json()["fallback_reason"] is None
    assert FailingAnswerer.models == []


def test_unknown_answer_mode_is_rejected_at_boundary() -> None:
    response = TestClient(main_module.app).post(
        "/v1/questions",
        json={
            "question": "지원하지 않는 모델을 사용해 주세요",
            "answer_mode": "other-model",
        },
    )

    assert response.status_code == 422


def test_nvidia_generation_without_openai_key_skips_embedding_call(monkeypatch) -> None:
    hit = SearchHit(
        provision_id=uuid4(),
        document_id=uuid4(),
        document_title="전기사업법",
        source_kind=SourceKind.LAW,
        version_label="MST 1",
        effective_from=date(2025, 1, 1),
        effective_to=None,
        path="제1조",
        content="에너지 관련 근거",
        source_url="https://www.law.go.kr",
    )

    async def search(*args, **kwargs):
        return [hit]

    async def last_sync():
        return None

    async def consume_quota(*args, **kwargs):
        return True

    class ForbiddenEmbedder:
        async def embed(self, texts):
            raise AssertionError("embedding provider must not be called")

    class FailedNvidiaAnswerer:
        async def answer(self, payload, hits):
            raise RuntimeError("NVIDIA mock generation failure")

    monkeypatch.setattr(main_module.repository, "search_with_trace", _with_trace(search))
    monkeypatch.setattr(main_module.repository, "last_sync", last_sync)
    monkeypatch.setattr(main_module.repository, "consume_quota", consume_quota)
    monkeypatch.setattr(main_module, "_embedder", lambda: ForbiddenEmbedder())
    monkeypatch.setattr(main_module, "_answerer", lambda: FailedNvidiaAnswerer())
    monkeypatch.setattr(main_module.settings, "answer_provider", "nvidia_nim")
    monkeypatch.setattr(main_module.settings, "nvidia_api_key", "nvapi-test")
    monkeypatch.setattr(main_module.settings, "openai_api_key", None)
    monkeypatch.setattr(main_module, "ai_quota_exhausted", False)

    response = TestClient(main_module.app).post(
        "/v1/questions",
        json={"question": "에너지 근거를 알려주세요", "answer_mode": "terra"},
    )

    assert response.status_code == 200
    assert response.json()["fallback_reason"] == "generation_error"
