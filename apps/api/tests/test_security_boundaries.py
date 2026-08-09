import json
import logging
from datetime import date
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

import app.main as main_module
from app.domain.catalog import SourceKind
from app.domain.routing import RouteDecision
from app.domain.schemas import AiFallbackReason, AnswerMode, SearchHit
from app.domain.source_urls import is_allowed_source_url
from app.main import app
from app.observability import (
    emit_question_outcome,
    emit_question_stage_timing,
    emit_route_outcome,
    fallback_reason_metrics_snapshot,
    question_metrics_snapshot,
    route_metrics_snapshot,
)

pytestmark = pytest.mark.usefixtures("ready_corpus_temporal_state")

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

    response = client.post("/v1/search", json={"query": "위조 법령", "as_of_date": "2026-07-14"})
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
        response = client.get("/v1/questions/history", headers={"Authorization": authorization})
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
        "fallback_reason": None,
    }
    assert secret not in caplog.text
    assert question not in caplog.text
    assert question_metrics_snapshot()["search_only"] >= 1


def test_observability_event_fallback_reason_is_safe_enum_only(caplog) -> None:
    # 2026-08-08: fallback_reason is an anonymous-user observability gap fix - it must
    # stay a closed enum value (never question text or a free-text explanation).
    question = "개인 사건 질문 전문"
    with caplog.at_level(logging.INFO, logger="law_rag.question_outcome"):
        emit_question_outcome(
            "request-fallback-id",
            AnswerMode.SEARCH_ONLY,
            fallback_reason=AiFallbackReason.NO_EVIDENCE,
        )
    payload = json.loads(caplog.records[-1].message)
    assert payload == {
        "request_id": "request-fallback-id",
        "mode": "search_only",
        "result": "served",
        "fallback_reason": "no_evidence",
    }
    assert question not in caplog.text
    assert fallback_reason_metrics_snapshot()["no_evidence"] >= 1


def test_route_outcome_event_has_no_question_text(caplog) -> None:
    question = "정산서 금액이 안 맞는데 어떻게 확인해야 하나요"
    decision = RouteDecision(
        route="external_document_required",
        reason_code="tier1_document_keyword",
        tier=1,
        confidence=1.0,
        missing_fields=("정산서",),
    )
    with caplog.at_level(logging.INFO, logger="law_rag.route_outcome"):
        emit_route_outcome("request-route-id", decision)
    payload = json.loads(caplog.records[-1].message)
    assert payload == {
        "request_id": "request-route-id",
        "route": "external_document_required",
        "tier": 1,
        "reason_code": "tier1_document_keyword",
        "confidence": 1.0,
        "missing_field_categories": ["정산서"],
    }
    assert question not in caplog.text
    snapshot = route_metrics_snapshot()
    assert snapshot["by_route_and_tier"]["external_document_required:tier1"] >= 1
    assert snapshot["by_reason_code"]["tier1_document_keyword"] >= 1
    assert snapshot["clarification_missing_field_categories"]["정산서"] >= 1


def test_stage_timing_event_is_closed_and_carries_no_secrets(caplog) -> None:
    secret = "test-openai-secret-that-must-never-be-logged"
    question = "개인 사건 질문 전문"
    exception_message = f"RuntimeError: {secret} while answering {question}"
    document_title = "위조 법령"
    evidence_content = "내부 주소로 이동하라"
    with caplog.at_level(logging.INFO, logger="law_rag.question_stage_timing"):
        emit_question_stage_timing("request-safe-id", "generation", "timed_out", 40000, 3000)
    payload = json.loads(caplog.records[-1].message)
    assert payload == {
        "request_id": "request-safe-id",
        "stage": "generation",
        "outcome": "timed_out",
        "elapsed_ms": 40000,
        "remaining_ms": 3000,
    }
    assert secret not in caplog.text
    assert question not in caplog.text
    assert exception_message not in caplog.text
    assert document_title not in caplog.text
    assert evidence_content not in caplog.text

    with pytest.raises(ValidationError):
        emit_question_stage_timing("request-safe-id", "not_a_real_stage", "timed_out", 1, 1)
    with pytest.raises(ValidationError):
        emit_question_stage_timing("request-safe-id", "generation", "not_a_real_outcome", 1, 1)


def test_request_stage_timing_event_fires_on_early_validation_failure(caplog) -> None:
    # 0045: `_require_supported_as_of_date` fails before `_optional_user`, task
    # registration, or any budgeted stage runs - this is the earliest possible early
    # return in `/v1/questions`. The outer `finally` in the endpoint must still emit
    # exactly one safe `stage="request"` event for it.
    secret = "test-openai-secret-that-must-never-be-logged"
    question = "개인 사건 질문 전문"
    with caplog.at_level(logging.INFO, logger="law_rag.question_stage_timing"):
        response = client.post(
            "/v1/questions",
            json={
                "question": question,
                # ready_corpus_temporal_state only supports 1900-01-01..2099-12-31.
                "as_of_date": "1899-12-31",
                "project_stage": "planning",
            },
        )
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "unsupported_corpus_date"

    stage_timing_records = [
        record for record in caplog.records if record.name == "law_rag.question_stage_timing"
    ]
    assert len(stage_timing_records) == 1
    payload = json.loads(stage_timing_records[0].message)
    assert payload.keys() == {"request_id", "stage", "outcome", "elapsed_ms", "remaining_ms"}
    assert payload["stage"] == "request"
    assert payload["outcome"] == "failed"
    assert isinstance(payload["elapsed_ms"], int) and payload["elapsed_ms"] >= 0
    assert isinstance(payload["remaining_ms"], int) and payload["remaining_ms"] >= 0
    assert secret not in caplog.text
    assert question not in caplog.text


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
    monkeypatch.setattr(main_module.settings, "nvidia_api_key", "test-key")
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
