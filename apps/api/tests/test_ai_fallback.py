from datetime import date
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

import app.main as main_module
from app.domain.catalog import SourceKind
from app.domain.schemas import SearchHit


class FailingAnswerer:
    models: list[str] = []
    error: Exception = RuntimeError("runtime failure")

    def __init__(self, *, api_key: str, model: str) -> None:
        self.models.append(model)

    async def answer(self, payload, hits):
        raise self.error


class QuotaFailure(Exception):
    status_code = 429


@pytest.mark.parametrize(
    "error",
    [
        RuntimeError("runtime"),
        PermissionError("authorization"),
        LookupError("model unavailable"),
        QuotaFailure("quota"),
    ],
)
def test_all_generation_failures_fall_back_without_another_model(monkeypatch, error) -> None:
    hit = SearchHit(
        provision_id=uuid4(),
        document_id=uuid4(),
        document_title="전기사업법",
        source_kind=SourceKind.LAW,
        version_label="MST 1",
        effective_from=date(2025, 1, 1),
        effective_to=None,
        path="제1조",
        content="분산에너지 관련 근거",
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
    monkeypatch.setattr(main_module.repository, "search", search)
    monkeypatch.setattr(main_module.repository, "last_sync", last_sync)
    monkeypatch.setattr(main_module.repository, "consume_quota", consume_quota)
    monkeypatch.setattr(main_module, "OpenAIAnswerer", FailingAnswerer)
    monkeypatch.setattr(main_module, "_embedder", lambda: NoopEmbedder())
    monkeypatch.setattr(main_module.settings, "openai_api_key", "test-key")
    monkeypatch.setattr(main_module, "ai_quota_exhausted", False)

    response = TestClient(main_module.app).post(
        "/v1/questions",
        json={
            "question": "분산에너지 근거를 알려주세요",
            "as_of_date": "2026-07-13",
            "project_stage": "planning",
        },
    )
    assert response.status_code == 200
    assert response.json()["mode"] == "search_only"
    assert FailingAnswerer.models == ["gpt-5.6-terra"]
