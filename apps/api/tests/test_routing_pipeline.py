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

pytestmark = pytest.mark.usefixtures("ready_corpus_temporal_state", "search_only_enabled")


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


class _StubBlockedAnswerer:
    def __init__(self, draft, *, captured: dict[str, object] | None = None):
        self._draft = draft
        self._captured = captured

    async def answer_blocked_route(self, request, route, reason):
        if self._captured is not None:
            self._captured["route"] = route
            self._captured["reason"] = reason
        return self._draft


def _unanswerable_draft(summary: str):
    from app.adapters.openai_answerer import DraftAnswer

    return DraftAnswer(
        summary=summary, scope="검색 미실행", sections=[], checklist=[], action="unanswerable"
    )


def _clarification_draft(missing: list[str]):
    from app.adapters.openai_answerer import DraftAnswer

    return DraftAnswer(
        summary="부족한 사실을 확인해야 합니다.",
        scope="검색 미실행",
        sections=[],
        checklist=[],
        action="clarification_required",
        missing_information=missing,
    )


def test_realtime_question_is_blocked_before_embedding_or_search(monkeypatch) -> None:
    embedding_calls: list[int] = []
    search_calls: list[int] = []
    _patch_ai_ready(monkeypatch, embedding_calls=embedding_calls, search_calls=search_calls)
    monkeypatch.setattr(
        main_module,
        "_answerer",
        lambda: _StubBlockedAnswerer(
            _unanswerable_draft(
                "이 시스템은 실시간 가격 정보에 연결되어 있지 않아 답할 수 없습니다."
            )
        ),
    )

    response = TestClient(main_module.app).post(
        "/v1/questions",
        json={"question": "지금 시세로 전기를 팔면 얼마나 받을 수 있나요?", "answer_mode": "terra"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "ai"
    assert body["route"] == "realtime_required"
    assert body["action"] == "unanswerable"
    assert "실시간 가격 정보" in body["summary"]
    assert embedding_calls == []
    assert search_calls == []


def test_external_document_question_is_blocked_before_embedding_or_search(monkeypatch) -> None:
    embedding_calls: list[int] = []
    search_calls: list[int] = []
    _patch_ai_ready(monkeypatch, embedding_calls=embedding_calls, search_calls=search_calls)
    monkeypatch.setattr(
        main_module,
        "_answerer",
        lambda: _StubBlockedAnswerer(
            _unanswerable_draft("이 시스템은 해당 문서에 연결되어 있지 않아 답할 수 없습니다.")
        ),
    )

    response = TestClient(main_module.app).post(
        "/v1/questions",
        json={
            "question": "정산서를 보니 금액이 안 맞는데 어떻게 확인하나요?",
            "answer_mode": "terra",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "ai"
    assert body["route"] == "external_document_required"
    assert body["action"] == "unanswerable"
    assert "해당 문서에 연결되어 있지 않아" in body["summary"]
    assert embedding_calls == []
    assert search_calls == []


def test_conditional_variance_question_gets_resubmission_template(monkeypatch) -> None:
    embedding_calls: list[int] = []
    search_calls: list[int] = []
    _patch_ai_ready(monkeypatch, embedding_calls=embedding_calls, search_calls=search_calls)
    monkeypatch.setattr(
        main_module,
        "_answerer",
        lambda: _StubBlockedAnswerer(_clarification_draft(["전기 사용 방식"])),
    )
    question = "전기 사용 방식에 따라 신고 절차가 다릅니다 어떻게 다른가요?"

    response = TestClient(main_module.app).post(
        "/v1/questions",
        json={"question": question, "answer_mode": "terra"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "ai"
    assert body["route"] == "clarification_required"
    assert body["action"] == "clarification_required"
    assert "추가 정보만 따로 보내지 마세요" in body["summary"]
    assert question in body["summary"]
    assert "전기 사용 방식" in body["summary"]
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


def test_abbreviated_provision_followup_routes_to_search_only(monkeypatch) -> None:
    """Regression test for 0049: documents that an abbreviated provision-only follow-up
    query like '7조1항' currently gets routed/downgraded to search_only instead of
    legal_search, even after an earlier conversation turn established the relevant law.
    This is a known bug, not the desired behavior - see
    docs/exec-plans/todo/0049-abbreviated-article-reference-routes-to-search-only.md
    (now deleted) for the original repro/analysis.

    Root cause (confirmed by reading app/main.py's _retrieve_question_evidence and
    _answer_question): retrieval calls repository.search_with_trace(payload.question, ...)
    using only the current turn's question text - conversation_context is never fed into
    search, only into generation prompts (see openai_answerer.py). Routing itself is not
    the culprit: tier 1 has no keyword match for "7조1항" and the mock tier 2 classifier
    defaults to legal_search with no hint (see MockRouteClassifier.classify), so
    route_decision.route stays "legal_search". The downgrade happens afterwards, in two
    steps inside _answer_question: because "7조1항" carries no law name, search finds no
    matching provision, hits comes back empty and fallback_reason is set to
    AiFallbackReason.NO_EVIDENCE (main.py's "if use_ai and not hits" block) - but
    generation is still attempted with zero evidence (main.py only skips generation when
    `not use_ai`, never when hits is merely empty). When the model still tries to answer
    despite having nothing to cite, validate_draft() (openai_answerer.py) rejects the
    draft because it isn't a clean, citation-free "unanswerable" response, which
    overwrites fallback_reason to GROUNDING_FAILED and returns the search_only fallback
    (main.py's "if not validate_draft(...)" branch). Either way - NO_EVIDENCE alone, or
    NO_EVIDENCE cascading into GROUNDING_FAILED - the terra request ends up as
    mode="search_only" instead of an AI answer, even though route_decision.route was
    correctly "legal_search" the whole time.
    """
    embedding_calls: list[int] = []
    search_calls: list[str] = []

    async def search(question, *args, **kwargs):
        search_calls.append(question)
        # The earlier turn's full query (with a law name) resolves fine; the abbreviated
        # follow-up ("7조1항", no law name) cannot be resolved by search alone since
        # conversation_context is never passed into retrieval - it returns no hits.
        if question == "7조1항":
            return []
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

    class OvereagerAnswerer:
        """Stands in for a real model that still attempts an answer despite having zero
        retrieved evidence to cite - validate_draft() must reject this (it only accepts a
        clean, citation-free "unanswerable" draft when hits is empty)."""

        async def answer(self, payload, hits):
            from app.adapters.openai_answerer import DraftAnswer
            from app.domain.schemas import AnswerSection

            return DraftAnswer(
                summary="전기사업법 제7조제1항에 따라 답변합니다.",
                scope="전기사업법 제7조제1항",
                sections=[
                    AnswerSection(
                        claim="제7조제1항 요건을 충족해야 합니다.",
                        explanation="이전 대화에서 다룬 법령을 기준으로 판단했습니다.",
                        citation_ids=["C1"],
                    )
                ],
                checklist=[],
                action="fully_answerable",
            )

    monkeypatch.setattr(main_module, "_answerer", lambda: OvereagerAnswerer())

    response = TestClient(main_module.app).post(
        "/v1/questions",
        json={
            "question": "7조1항",
            "answer_mode": "terra",
            "conversation_context": [
                {
                    "question": "전기사업법 제2조는 무슨 내용인가요?",
                    "answer": "전기사업법 제2조는 용어의 정의를 규정합니다.",
                }
            ],
        },
    )

    assert response.status_code == 200
    body = response.json()
    # Routing itself got it right ...
    assert body["route"] == "legal_search"
    # ... but the response still comes back as search_only, not an AI answer, because
    # retrieval (which ignores conversation_context) found no evidence for the bare
    # "7조1항" reference. This is the bug: the user asked a terra follow-up expecting it
    # to resolve against the law discussed earlier in the conversation, but got a
    # search_only fallback instead.
    assert body["mode"] == "search_only"
    assert body["fallback_reason"] == "grounding_failed"
    assert search_calls == ["7조1항"]
    assert embedding_calls == [1]


def test_tier2_llm_explanation_is_passed_to_blocked_route_generation(monkeypatch) -> None:
    """2026-08-08 (user proposal): tier 2's own reasoning, already produced for free,
    should make blocked-route messages question-specific instead of purely canned. 0046:
    the reasoning now flows into the LLM generation call as its `reason` argument."""
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
    captured: dict[str, object] = {}
    monkeypatch.setattr(
        main_module,
        "_answerer",
        lambda: _StubBlockedAnswerer(
            _unanswerable_draft("이 시스템은 해당 문서에 연결되어 있지 않아 답할 수 없습니다."),
            captured=captured,
        ),
    )

    response = TestClient(main_module.app).post(
        "/v1/questions",
        json={"question": "이거 애매한 질문인데 확인해줄래요?", "answer_mode": "terra"},
    )

    assert response.status_code == 200
    assert response.json()["route"] == "external_document_required"
    assert captured["reason"] == "사용자가 보유한 보증서 내용을 직접 대조해야 판단할 수 있다."
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
    captured: dict[str, object] = {}
    monkeypatch.setattr(
        main_module,
        "_answerer",
        lambda: _StubBlockedAnswerer(_unanswerable_draft("답할 수 없습니다."), captured=captured),
    )

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
    assert captured["reason"] is None


def test_blocked_route_generation_failure_falls_back_to_canned_message(monkeypatch) -> None:
    embedding_calls: list[int] = []
    search_calls: list[int] = []
    _patch_ai_ready(monkeypatch, embedding_calls=embedding_calls, search_calls=search_calls)

    class RaisingAnswerer:
        async def answer_blocked_route(self, request, route, reason):
            raise RuntimeError("NVIDIA mock outage")

    monkeypatch.setattr(main_module, "_answerer", lambda: RaisingAnswerer())

    response = TestClient(main_module.app).post(
        "/v1/questions",
        json={"question": "지금 시세로 전기를 팔면 얼마나 받을 수 있나요?", "answer_mode": "terra"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "search_only"
    assert body["route"] == "realtime_required"
    assert "시점에 따라 달라지는 정보" in body["summary"]
