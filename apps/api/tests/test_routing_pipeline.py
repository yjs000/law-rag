from datetime import date
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

import app.main as main_module
from app.adapters.mock_route_classifier import MockRouteClassifier
from app.adapters.nvidia_nim_route_classifier import NvidiaNimRouteClassifier
from app.domain.catalog import SourceKind
from app.domain.routing import RouteDecision, RouteExample, nearest_example
from app.domain.schemas import SearchHit
from app.domain.search_queries import SearchTrace

pytestmark = pytest.mark.usefixtures("ready_corpus_temporal_state")


def test_route_classifier_uses_mock_without_api_key(monkeypatch) -> None:
    monkeypatch.setattr(main_module.settings, "nvidia_api_key", None)
    assert isinstance(main_module._route_classifier(), MockRouteClassifier)


def test_route_classifier_uses_nvidia_with_api_key(monkeypatch) -> None:
    monkeypatch.setattr(main_module.settings, "nvidia_api_key", "nvapi-test")
    assert isinstance(main_module._route_classifier(), NvidiaNimRouteClassifier)


def test_tier2_classifier_failure_falls_back_to_legal_search(monkeypatch) -> None:
    embedding_calls: list[int] = []
    search_calls: list[int] = []
    _patch_ai_ready(monkeypatch, embedding_calls=embedding_calls, search_calls=search_calls)

    class FailingClassifier:
        async def classify(self, question, hint):
            raise RuntimeError("NVIDIA mock outage")

    monkeypatch.setattr(main_module, "_route_classifier", lambda: FailingClassifier())

    class StubAnswerer:
        async def answer(self, payload, hits):
            raise RuntimeError("not exercised")

    monkeypatch.setattr(main_module, "_answerer", lambda: StubAnswerer())

    response = TestClient(main_module.app).post(
        "/v1/questions",
        json={"question": "태양광 발전사업 허가는 어떻게 받나요?", "answer_mode": "terra"},
    )

    assert response.status_code == 200
    # tier 2 failure degrades to legal_search rather than a 500 - see main.py's routing
    # block: blocking on an infra error would deny more answerable questions than
    # searching would incorrectly search unanswerable ones.
    assert embedding_calls == [1]
    assert search_calls == [1]


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
        content="에너지 관련 근거",
        source_url="https://www.law.go.kr",
        score=1,
    )


def _patch_ai_ready(monkeypatch, *, embedding_calls: list[int], search_calls: list[int]):
    async def search(*args, **kwargs):
        search_calls.append(1)
        return [_hit()]

    async def last_sync():
        return None

    async def consume_quota(*args, **kwargs):
        return True

    class NoopEmbedder:
        async def embed(self, texts):
            embedding_calls.append(1)
            return [[1.0, *([0.0] * 511)]]

    monkeypatch.setattr(main_module.repository, "search_with_trace", _with_trace(search))
    monkeypatch.setattr(main_module.repository, "last_sync", last_sync)
    monkeypatch.setattr(main_module.repository, "consume_quota", consume_quota)
    monkeypatch.setattr(main_module, "_embedder", lambda: NoopEmbedder())
    monkeypatch.setattr(main_module.settings, "nvidia_api_key", "nvapi-test")
    monkeypatch.setattr(main_module, "ai_quota_exhausted", False)


def test_realtime_question_is_blocked_before_embedding_or_search(monkeypatch) -> None:
    embedding_calls: list[int] = []
    search_calls: list[int] = []
    _patch_ai_ready(monkeypatch, embedding_calls=embedding_calls, search_calls=search_calls)

    response = TestClient(main_module.app).post(
        "/v1/questions",
        json={"question": "지금 시세로 전기를 팔면 얼마나 받을 수 있나요?", "answer_mode": "terra"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "search_only"
    assert body["route"] == "realtime_required"
    assert "시점에 따라 달라지는 정보" in body["summary"]
    assert embedding_calls == []
    assert search_calls == []


def test_external_document_question_is_blocked_before_embedding_or_search(monkeypatch) -> None:
    embedding_calls: list[int] = []
    search_calls: list[int] = []
    _patch_ai_ready(monkeypatch, embedding_calls=embedding_calls, search_calls=search_calls)

    response = TestClient(main_module.app).post(
        "/v1/questions",
        json={
            "question": "정산서를 보니 금액이 안 맞는데 어떻게 확인하나요?",
            "answer_mode": "terra",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "search_only"
    assert body["route"] == "external_document_required"
    assert "문서 확인이 필요합니다" in body["summary"]
    assert embedding_calls == []
    assert search_calls == []


def test_conditional_variance_question_gets_resubmission_template(monkeypatch) -> None:
    embedding_calls: list[int] = []
    search_calls: list[int] = []
    _patch_ai_ready(monkeypatch, embedding_calls=embedding_calls, search_calls=search_calls)
    question = "전기 사용 방식에 따라 신고 절차가 다릅니다 어떻게 다른가요?"

    response = TestClient(main_module.app).post(
        "/v1/questions",
        json={"question": question, "answer_mode": "terra"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "search_only"
    assert body["route"] == "clarification_required"
    assert "추가 정보만 따로 보내지 마세요" in body["summary"]
    assert question in body["summary"]
    assert embedding_calls == []
    assert search_calls == []


def test_ordinary_legal_question_still_reaches_search(monkeypatch) -> None:
    embedding_calls: list[int] = []
    search_calls: list[int] = []
    _patch_ai_ready(monkeypatch, embedding_calls=embedding_calls, search_calls=search_calls)

    class StubAnswerer:
        async def answer(self, payload, hits):
            raise RuntimeError("not exercised - grounding gate test not needed here")

    monkeypatch.setattr(main_module, "_answerer", lambda: StubAnswerer())

    response = TestClient(main_module.app).post(
        "/v1/questions",
        json={"question": "태양광 발전사업 허가는 어떻게 받나요?", "answer_mode": "terra"},
    )

    assert response.status_code == 200
    # tier 1 doesn't match, mock tier 2 classifier defaults to legal_search with no hint,
    # so the pipeline proceeds past routing into the existing embedding/search path.
    assert embedding_calls == [1]
    assert search_calls == [1]


def test_search_only_mode_is_not_gated_by_routing(monkeypatch) -> None:
    """Deliberate scope decision (2026-08-08): routing only gates use_ai (terra)
    requests for now - search_only keeps its pre-0028 behavior."""
    embedding_calls: list[int] = []
    search_calls: list[int] = []
    _patch_ai_ready(monkeypatch, embedding_calls=embedding_calls, search_calls=search_calls)

    response = TestClient(main_module.app).post(
        "/v1/questions",
        json={
            "question": "지금 시세로 전기를 팔면 얼마나 받을 수 있나요?",
            "answer_mode": "search_only",
        },
    )

    assert response.status_code == 200
    assert response.json()["mode"] == "search_only"
    assert response.json().get("route") is None
    assert search_calls == [1]


def test_tier2_llm_explanation_is_appended_to_blocked_message(monkeypatch) -> None:
    """2026-08-08 (user proposal): tier 2's own reasoning, already produced for free,
    should make blocked-route messages question-specific instead of purely canned."""
    embedding_calls: list[int] = []
    search_calls: list[int] = []
    _patch_ai_ready(monkeypatch, embedding_calls=embedding_calls, search_calls=search_calls)

    class ExplainingClassifier:
        async def classify(self, question, hint):
            from app.domain.routing import RouteJudgment

            return RouteJudgment(
                route="external_document_required",
                confidence=0.9,
                reason="사용자가 보유한 보증서 내용을 직접 대조해야 판단할 수 있다.",
            )

    monkeypatch.setattr(main_module, "_route_classifier", lambda: ExplainingClassifier())

    response = TestClient(main_module.app).post(
        "/v1/questions",
        json={"question": "이거 애매한 질문인데 확인해줄래요?", "answer_mode": "terra"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["route"] == "external_document_required"
    assert "보증서 내용을 직접 대조" in body["summary"]
    assert embedding_calls == []
    assert search_calls == []


def test_mock_classifier_explanation_never_reaches_the_user(monkeypatch) -> None:
    """MockRouteClassifier's reason text is a debug placeholder, not meant for display -
    only exercised when NVIDIA_API_KEY is absent (local dev)."""
    embedding_calls: list[int] = []
    search_calls: list[int] = []
    _patch_ai_ready(monkeypatch, embedding_calls=embedding_calls, search_calls=search_calls)

    class HintedClassifier:
        async def classify(self, question, hint_arg):
            return await MockRouteClassifier().classify(question, hint_arg)

    monkeypatch.setattr(main_module, "_route_classifier", lambda: HintedClassifier())

    with_hint_result = None

    async def route_tier2_with_hint(question, classifier, *, hint=None):
        nonlocal with_hint_result
        example = RouteExample(
            example_id="x", route="realtime_required", embedding=(1.0, 0.0)
        )
        forced_hint = nearest_example((1.0, 0.0), (example,))
        with_hint_result = await classifier.classify(question, forced_hint)
        return RouteDecision(
            route=with_hint_result.route,
            reason_code="tier2_llm_judgment",
            tier=2,
            confidence=with_hint_result.confidence,
            explanation=with_hint_result.reason,
        )

    monkeypatch.setattr(main_module, "route_tier2", route_tier2_with_hint)

    response = TestClient(main_module.app).post(
        "/v1/questions",
        json={"question": "이거 애매한 질문인데 확인해줄래요?", "answer_mode": "terra"},
    )

    assert response.status_code == 200
    assert "mock_classifier" not in response.json()["summary"]
