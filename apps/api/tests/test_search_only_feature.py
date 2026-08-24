from datetime import date
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

import app.main as main_module
from app.domain.catalog import SourceKind
from app.domain.schemas import SearchHit
from app.domain.search_queries import SearchTrace
from app.settings import Settings

pytestmark = pytest.mark.usefixtures("ready_corpus_temporal_state")


def test_search_only_feature_defaults_to_disabled_and_can_be_enabled(monkeypatch) -> None:
    monkeypatch.delenv("SEARCH_ONLY_ENABLED", raising=False)

    assert not Settings(_env_file=None).search_only_enabled
    assert Settings(search_only_enabled=True, _env_file=None).search_only_enabled


def test_disabled_search_only_feature_rejects_explicit_search_request(monkeypatch) -> None:
    monkeypatch.setattr(main_module.settings, "search_only_enabled", False)

    response = TestClient(main_module.app).post(
        "/v1/questions",
        json={
            "question": "원문만 검색해 주세요",
            "as_of_date": "2026-07-14",
            "answer_mode": "search_only",
        },
    )

    assert response.status_code == 503
    assert response.json()["detail"] == "검색 전용 기능이 비활성화되어 있습니다."


def test_disabled_search_only_feature_does_not_return_generation_fallback(monkeypatch) -> None:
    monkeypatch.setattr(main_module.settings, "ai_mode", "off")
    monkeypatch.setattr(main_module.settings, "search_only_enabled", False)

    response = TestClient(main_module.app).post(
        "/v1/questions", json={"question": "전기사업 근거", "answer_mode": "terra"}
    )

    assert response.status_code == 503
    assert response.json()["detail"] == "AI 답변을 현재 사용할 수 없습니다."


def test_disabled_search_only_feature_reports_ai_unavailability_without_search_only_warning(
    monkeypatch,
) -> None:
    monkeypatch.setattr(main_module.settings, "ai_mode", "off")
    monkeypatch.setattr(main_module.settings, "search_only_enabled", False)
    monkeypatch.setattr(main_module, "ai_quota_exhausted", False)

    response = TestClient(main_module.app).get("/v1/corpus/status")

    assert response.status_code == 200
    warnings = response.json()["warnings"]
    assert "AI가 비활성화되어 답변을 생성할 수 없습니다." in warnings
    assert "AI가 비활성화되어 검색 전용 모드로 동작합니다." not in warnings


def test_disabled_search_only_feature_returns_503_after_generation_failure(monkeypatch) -> None:
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
        return [hit], SearchTrace(
            strategy="keyword",
            normalized_query="test",
            terms=("test",),
            executed_query="test",
            relaxed=False,
            reference_title=None,
            reference_path=None,
            candidate_count=1,
        )

    async def last_sync():
        return None

    class Embedder:
        async def embed(self, texts):
            return [[0.0] * 512]

    class FailingAnswerer:
        async def answer(self, payload, hits):
            raise RuntimeError("generation failure")

    monkeypatch.setattr(main_module.repository, "search_with_trace", search)
    monkeypatch.setattr(main_module.repository, "last_sync", last_sync)
    monkeypatch.setattr(main_module, "_embedder", lambda: Embedder())
    monkeypatch.setattr(main_module, "_answerer", lambda: FailingAnswerer())
    monkeypatch.setattr(main_module.settings, "nvidia_api_key", "nvapi-test")
    monkeypatch.setattr(main_module.settings, "ai_mode", "auto")
    monkeypatch.setattr(main_module.settings, "search_only_enabled", False)
    monkeypatch.setattr(main_module, "ai_quota_exhausted", False)

    response = TestClient(main_module.app).post(
        "/v1/questions", json={"question": "전기사업 근거", "answer_mode": "terra"}
    )

    assert response.status_code == 503
    assert response.json()["detail"] == "AI 답변을 생성하지 못했습니다. 잠시 후 다시 시도해 주세요."