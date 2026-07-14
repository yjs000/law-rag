import json
import logging
from datetime import date
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

import app.main as main_module
from app.domain.catalog import SourceKind
from app.domain.schemas import AnswerMode, SearchHit
from app.domain.source_urls import is_allowed_source_url
from app.main import app
from app.observability import emit_question_outcome, question_metrics_snapshot

client = TestClient(app)


@pytest.mark.parametrize(
    "url",
    [
        "http://www.law.go.kr/DRF/lawService.do",
        "https://example.com/law",
        "https://www.law.go.kr.evil.example/law",
        "https://user@www.law.go.kr/law",
        "https://www.law.go.kr:444/law",
        "file:///etc/passwd",
        "http://127.0.0.1/admin",
    ],
)
def test_source_url_allowlist_blocks_ssrf_and_deceptive_hosts(url: str) -> None:
    assert not is_allowed_source_url(url)


def test_source_url_allowlist_accepts_only_official_https() -> None:
    assert is_allowed_source_url("https://www.law.go.kr/DRF/lawService.do?MST=1")
    assert is_allowed_source_url("https://open.law.go.kr/LSO/openApi/guideResult.do")


def test_search_response_drops_non_allowlisted_source_url(monkeypatch) -> None:
    malicious_hit = SearchHit(
        provision_id=uuid4(),
        document_id=uuid4(),
        document_title="위조 법령",
        source_kind=SourceKind.LAW,
        version_label="MST 1",
        effective_from=date(2026, 1, 1),
        effective_to=None,
        path="제1조",
        content="내부 주소로 이동하라",
        source_url="http://127.0.0.1/admin",
        score=1,
    )

    async def search(*args, **kwargs):
        return [malicious_hit]

    async def consume_quota(*args, **kwargs):
        return True

    monkeypatch.setattr(main_module.repository, "search", search)
    monkeypatch.setattr(main_module.repository, "consume_quota", consume_quota)
    monkeypatch.setattr(main_module.settings, "ai_mode", "off")

    response = client.post(
        "/v1/search", json={"query": "위조 법령", "as_of_date": "2026-07-14"}
    )
    assert response.status_code == 200
    assert response.json() == []


def test_oversized_question_and_search_are_rejected_at_boundary() -> None:
    question = client.post(
        "/v1/questions",
        json={"question": "가" * 2001, "as_of_date": "2026-07-14", "project_stage": "planning"},
    )
    search = client.post(
        "/v1/search",
        json={"query": "가" * 501, "as_of_date": "2026-07-14"},
    )
    assert question.status_code == 422
    assert search.status_code == 422


def test_forged_auth_schemes_cannot_bypass_history_authorization() -> None:
    for authorization in ("Basic abc", "Bearer", "bearer forged-token"):
        response = client.get(
            "/v1/questions/history", headers={"Authorization": authorization}
        )
        assert response.status_code == 401


def test_observability_event_has_only_request_id_mode_and_result(caplog) -> None:
    secret = "test-openai-secret-that-must-never-be-logged"
    question = "개인 사건 질문 전문"
    with caplog.at_level(logging.INFO, logger="law_rag.question_outcome"):
        emit_question_outcome("request-safe-id", AnswerMode.SEARCH_ONLY)
    payload = json.loads(caplog.records[-1].message)
    assert payload == {
        "request_id": "request-safe-id",
        "mode": "search_only",
        "result": "served",
    }
    assert secret not in caplog.text
    assert question not in caplog.text
    assert question_metrics_snapshot()["search_only"] >= 1


def test_question_and_secret_bearing_failure_are_not_logged(monkeypatch, caplog) -> None:
    secret = "test-openai-secret-that-must-never-be-logged"
    question = "개인 사건 질문 전문"

    class SecretFailEmbedder:
        async def embed(self, texts):
            raise RuntimeError(f"{secret}: {texts[0]}")

    async def search(*args, **kwargs):
        return []

    async def last_sync():
        return None

    async def consume_quota(*args, **kwargs):
        return True

    monkeypatch.setattr(main_module.repository, "search", search)
    monkeypatch.setattr(main_module.repository, "last_sync", last_sync)
    monkeypatch.setattr(main_module.repository, "consume_quota", consume_quota)
    monkeypatch.setattr(main_module, "_embedder", lambda: SecretFailEmbedder())
    monkeypatch.setattr(main_module.settings, "openai_api_key", "test-key")
    monkeypatch.setattr(main_module, "ai_quota_exhausted", False)

    with caplog.at_level(logging.INFO):
        response = client.post(
            "/v1/questions",
            json={
                "question": question,
                "as_of_date": "2026-07-14",
                "project_stage": "planning",
            },
        )
    assert response.status_code == 200
    assert secret not in caplog.text
    assert question not in caplog.text
