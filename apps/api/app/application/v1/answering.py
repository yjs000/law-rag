"""V1 evidence-first answer use case, separate from HTTP transport."""

from __future__ import annotations

import asyncio
import time
from typing import Literal

from fastapi import HTTPException, Request
from law_rag_core.ports.repository import LegalRepository

from app.adapters.openai_answerer import select_generation_hits, validate_draft
from app.api.dependencies import _save_if_authenticated, main_module
from app.application.answering import (
    post_generation_clarification_answer,
    route_guidance_fallback,
    search_only_answer,
)
from app.application.request_budget import RequestBudget, StageTimeoutError
from app.application.v1.guidance import generate_blocked_answer
from app.application.v1.retrieval import (
    elapsed_ms,
    remaining_ms,
    requires_legacy_query_embedding,
    retrieve_question_evidence,
)
from app.domain.answer_actions import derive_answer_action
from app.domain.errors import CorpusSearchUnavailableError
from app.domain.generation_profiles import NVIDIA_NEMOTRON_ULTRA_ANSWER_PROFILE_V2
from app.domain.routing import RouteDecision
from app.domain.schemas import (
    AiFallbackReason,
    Citation,
    MockUser,
    QuestionRequest,
    QuestionResponse,
)
from app.domain.source_urls import is_allowed_source_url
from app.observability import (
    QuestionStageTimingOutcome,
    emit_question_stage_timing,
    emit_route_outcome,
)


def _search_only_disabled_error() -> HTTPException:
    return HTTPException(status_code=503, detail="검색 전용 기능이 비활성화되어 있습니다.")


def _ai_unavailable_error() -> HTTPException:
    return HTTPException(status_code=503, detail="AI 답변을 현재 사용할 수 없습니다.")


def _generation_failed_error() -> HTTPException:
    return HTTPException(
        status_code=503,
        detail="AI 답변을 생성하지 못했습니다. 잠시 후 다시 시도해 주세요.",
    )


async def _answer_question(
    payload: QuestionRequest,
    request: Request,
    user: MockUser | None,
    budget: RequestBudget,
    repository: LegalRepository,
) -> QuestionResponse:
    """근거 우선 질문 답변 흐름을 라우팅·검색·생성 예산 안에서 실행한다.

    정상 법령 경로의 생성 실패·grounding 거부는 기존 검색 전용 fallback 계약을 따른다.
    라우터 불가 경로는 검색을 시작하지 않고 항상 AI-mode의 빈 unanswerable 응답으로 끝난다.
    """
    main = main_module()
    if payload.answer_mode == "search_only" and not main.settings.search_only_enabled:
        raise _search_only_disabled_error()
    if not main._ai_available() and not main.settings.search_only_enabled:
        await main._require_supported_as_of_date(payload.as_of_date, repository)
        raise _ai_unavailable_error()

    use_ai = payload.answer_mode == "terra" and main._ai_available()
    if not use_ai:
        await main._require_supported_as_of_date(payload.as_of_date, repository)
    fallback_reason = main._initial_fallback_reason(payload)
    diagnostics: dict[str, object] = {
        "schema_version": "1",
        "input_validation": {
            "status": "passed",
            "as_of_date": payload.as_of_date.isoformat(),
            "project_stage": payload.project_stage.value,
            "answer_mode": payload.answer_mode,
        },
        "parsing": {},
        "embedding": {
            "requested": payload.answer_mode == "terra",
            "attempted": False,
            "status": (
                "skipped_search_only"
                if payload.answer_mode == "search_only"
                else f"skipped_{main._ai_unavailable_reason() or 'not_started'}"
            ),
            "dimensions": None,
        },
        "retrieval": {},
        "evidence_source_validation": {"attempted": False, "status": "not_attempted"},
        "answer_generation": {"attempted": False, "status": "not_attempted"},
        "answer_validation": {"attempted": False, "status": "not_attempted"},
        "routing": {"attempted": False, "status": "not_attempted"},
        "clarification_generation": {"attempted": False, "status": "not_attempted"},
        "required_source_guidance_generation": {
            "attempted": False,
            "status": "not_attempted",
        },
        "blocked_answer_generation": {"attempted": False, "status": "not_attempted"},
        "blocked_response_validation": {"attempted": False, "status": "not_attempted"},
        "outcome": {},
    }
    await main._check_quota("ai" if use_ai else "search", user=user)
    await asyncio.sleep(0)
    # Routing applies only to Terra requests. Search-only requests intentionally retain
    # their existing direct retrieval contract.
    route_decision: RouteDecision | None = None
    if use_ai:
        routing_stage = diagnostics["routing"]
        assert isinstance(routing_stage, dict)
        routing_stage.update({"attempted": True, "status": "started"})
        routing_started = time.monotonic()
        routing_outcome: QuestionStageTimingOutcome = "failed"
        routing_timed_out = False
        try:
            route_decision = await budget.run(
                "routing",
                lambda: main.route_question(payload.question, main._question_router()),
                cap_seconds=main.settings.route_classifier_timeout_seconds,
            )
            routing_outcome = "succeeded"
        except StageTimeoutError:
            routing_timed_out = True
            routing_outcome = "timed_out"
            route_decision = RouteDecision(
                route="routing_unavailable",
                reason_code="routing_timeout",
                confidence=0.0,
            )
        except Exception:
            routing_outcome = "failed"
            route_decision = RouteDecision(
                route="routing_unavailable",
                reason_code="routing_provider_error",
                confidence=0.0,
            )
        finally:
            emit_question_stage_timing(
                str(payload.client_request_id),
                "routing",
                routing_outcome,
                elapsed_ms(routing_started),
                remaining_ms(budget),
            )
        assert route_decision is not None
        real_explanation = (
            route_decision.explanation if route_decision.route != "routing_unavailable" else None
        )
        routing_stage.update(
            {
                "status": (
                    "timed_out"
                    if routing_timed_out
                    else "failed"
                    if routing_outcome == "failed"
                    else "resolved"
                ),
                "route": route_decision.route,
                "reason_code": route_decision.reason_code,
                "confidence": route_decision.confidence,
            }
        )
        emit_route_outcome(str(payload.client_request_id), route_decision)
        if route_decision.route != "legal_search":
            guidance_stage: Literal[
                "clarification_generation",
                "required_source_guidance_generation",
                "blocked_answer_generation",
            ] = (
                "blocked_answer_generation"
                if route_decision.route == "routing_unavailable"
                else "clarification_generation"
                if route_decision.route == "clarification_required"
                else "required_source_guidance_generation"
            )
            blocked_fallback = route_guidance_fallback(
                payload,
                route_decision.route,
                missing_fields=route_decision.missing_fields,
                explanation=real_explanation,
            )
            blocked_fallback.request_id = str(payload.client_request_id)
            route_answer = await generate_blocked_answer(
                payload,
                route_decision,
                real_explanation,
                blocked_fallback,
                diagnostics,
                budget,
                stage_name=guidance_stage,
            )
            return await _save_if_authenticated(user, payload, route_answer, diagnostics)
        await main._require_supported_as_of_date(payload.as_of_date, repository)
    query_embedding = None
    embedding_failed = False
    if use_ai and main.settings.embedding_enabled and requires_legacy_query_embedding(repository):
        embedding_stage = diagnostics["embedding"]
        assert isinstance(embedding_stage, dict)
        embedding_stage.update({"attempted": True, "status": "started"})
        embedding_started = time.monotonic()
        # 성공을 명시적으로 표시한다 - 기본값이 "succeeded"면 asyncio.CancelledError가
        # stage를 죽여도 finally가 잘못된 "succeeded"를 로깅해버린다(Finding 2).
        embedding_outcome: QuestionStageTimingOutcome = "failed"
        try:
            query_embedding = (
                await budget.run(
                    "embedding",
                    lambda: main._embedder().embed([payload.question]),
                    cap_seconds=main.settings.question_embedding_timeout_seconds,
                )
            )[0]
            embedding_outcome = "succeeded"
            embedding_stage.update({"status": "succeeded", "dimensions": len(query_embedding)})
        except StageTimeoutError:
            embedding_failed = True
            embedding_outcome = "timed_out"
            embedding_stage.update({"status": "timed_out", "dimensions": None})
        except Exception:
            embedding_failed = True
            embedding_outcome = "failed"
            embedding_stage.update({"status": "failed", "dimensions": None})
        finally:
            emit_question_stage_timing(
                str(payload.client_request_id),
                "embedding",
                embedding_outcome,
                elapsed_ms(embedding_started),
                remaining_ms(budget),
            )
    elif use_ai:
        embedding_stage = diagnostics["embedding"]
        assert isinstance(embedding_stage, dict)
        embedding_stage.update({"attempted": False, "status": "skipped_provider_unavailable"})
    retrieval_started = time.monotonic()
    # 성공을 명시적으로 표시한다 - 기본값이 "succeeded"면 asyncio.CancelledError가
    # stage를 죽여도 finally가 잘못된 "succeeded"를 로깅해버린다(Finding 2).
    retrieval_outcome: QuestionStageTimingOutcome = "failed"
    try:
        hits, search_trace, corpus_as_of = await budget.run(
            "retrieval",
            lambda: retrieve_question_evidence(payload, query_embedding, repository),
            cap_seconds=main.settings.retrieval_timeout_seconds,
        )
        retrieval_outcome = "succeeded"
    except StageTimeoutError as exc:
        # 검색 stage 예산을 다 썼다 - 아직 신뢰할 근거가 없으므로(부분 결과로 답을
        # 만들지 않는다) 재시도를 유도하는 고정 503 메시지로 끝낸다. corpus 미준비·일반
        # 검색 실패와는 원인이 다르므로 별도 분기로 유지한다.
        retrieval_outcome = "timed_out"
        raise HTTPException(
            status_code=503,
            detail="법령 검색 시간이 초과되었습니다. 잠시 후 다시 시도해 주세요.",
        ) from exc
    except CorpusSearchUnavailableError as exc:
        retrieval_outcome = "failed"
        raise main._corpus_unready_http_error() from exc
    except Exception as exc:
        retrieval_outcome = "failed"
        raise HTTPException(
            status_code=503,
            detail="법령 검색을 일시적으로 사용할 수 없습니다.",
        ) from exc
    finally:
        emit_question_stage_timing(
            str(payload.client_request_id),
            "retrieval",
            retrieval_outcome,
            elapsed_ms(retrieval_started),
            remaining_ms(budget),
        )
    original_hit_count = len(hits)
    hits = [hit for hit in hits if is_allowed_source_url(hit.source_url)]
    source_validation_stage = diagnostics["evidence_source_validation"]
    assert isinstance(source_validation_stage, dict)
    source_validation_stage.update(
        {
            "attempted": True,
            "status": "succeeded",
            "input_count": original_hit_count,
            "allowed_count": len(hits),
        }
    )
    diagnostics["retrieval"] = {
        **search_trace.as_dict(),
        "allowed_candidate_count": len(hits),
    }
    diagnostics["parsing"] = {
        "normalized_query": search_trace.normalized_query,
        "terms": list(search_trace.terms),
        "reference_detected": search_trace.reference_path is not None,
        "reference_title": search_trace.reference_title,
        "reference_path": search_trace.reference_path,
    }
    if use_ai and not hits:
        fallback_reason = (
            AiFallbackReason.EMBEDDING_ERROR if embedding_failed else AiFallbackReason.NO_EVIDENCE
        )
    fallback = search_only_answer(payload, hits, corpus_as_of, fallback_reason=fallback_reason)
    fallback.request_id = str(payload.client_request_id)
    if route_decision is not None:
        fallback.route = route_decision.route
    if not use_ai:
        generation_stage = diagnostics["answer_generation"]
        assert isinstance(generation_stage, dict)
        generation_stage["status"] = (
            "skipped_search_only" if payload.answer_mode == "search_only" else "skipped_ai_disabled"
        )
        return await _save_if_authenticated(user, payload, fallback, diagnostics)
    generation_stage = diagnostics["answer_generation"]
    assert isinstance(generation_stage, dict)
    generation_hits = select_generation_hits(hits, main.settings.answer_evidence_max_characters)
    generation_stage.update(
        {
            "attempted": True,
            "status": "started",
            "retrieved_evidence_count": len(hits),
            "selected_evidence_count": len(generation_hits),
            "dropped_evidence_count": len(hits) - len(generation_hits),
            "selected_evidence_characters": sum(len(hit.content) for hit in generation_hits),
            # 0025 M5 item 4: 어떤 model/prompt/schema/context/sampling 조합이 이 답변을
            # 만들었는지 SHA로 남긴다. 생성 경로는 NVIDIA NIM 하나로 고정돼 있다.
            # 0043, 2026-08-10: _answerer()가 build_messages_v2를 기본으로 쓰도록 전환하며
            # 이 프로필 참조도 V2로 맞췄다 - 프로필과 message_builder가 항상 짝을 이뤄야
            # generation_profile_sha256가 실제 생성에 쓰인 프롬프트를 정확히 가리킨다.
            "generation_profile_key": NVIDIA_NEMOTRON_ULTRA_ANSWER_PROFILE_V2.key,
            "generation_profile_sha256": NVIDIA_NEMOTRON_ULTRA_ANSWER_PROFILE_V2.sha256,
        }
    )
    generation_started = time.monotonic()
    # 성공을 명시적으로 표시한다 - 기본값이 "succeeded"면 asyncio.CancelledError가
    # stage를 죽여도 finally가 잘못된 "succeeded"를 로깅해버린다(Finding 2).
    generation_outcome: QuestionStageTimingOutcome = "failed"
    try:
        draft = await budget.run(
            "answer_generation",
            lambda: main._answerer().answer(payload, generation_hits),
            cap_seconds=main.settings.answer_timeout_seconds,
        )
        generation_outcome = "succeeded"
    except StageTimeoutError as exc:
        if not main.settings.search_only_enabled:
            raise _generation_failed_error() from exc
        # 생성 stage 예산을 다 썼다 - 이미 검증된 근거(fallback)가 있으니 에러가 아니라
        # 200 + search_only로 끝낸다. 웹 클라이언트 재시도 로직이 이 응답 모양에
        # 의존한다(에러 응답으로 바꾸면 안 된다).
        generation_outcome = "timed_out"
        fallback.fallback_reason = AiFallbackReason.GENERATION_ERROR
        generation_stage["status"] = "timed_out"
        return await _save_if_authenticated(user, payload, fallback, diagnostics)
    except Exception as exc:
        generation_outcome = "failed"
        status_code = getattr(exc, "status_code", None)
        if status_code in {402, 429}:
            main.ai_quota_exhausted = True
            fallback.fallback_reason = AiFallbackReason.BILLING_OR_QUOTA_ERROR
        else:
            fallback.fallback_reason = AiFallbackReason.GENERATION_ERROR
        generation_stage["status"] = (
            "billing_or_quota_error" if status_code in {402, 429} else "failed"
        )
        if not main.settings.search_only_enabled:
            raise _generation_failed_error() from exc
        return await _save_if_authenticated(user, payload, fallback, diagnostics)
    finally:
        emit_question_stage_timing(
            str(payload.client_request_id),
            "answer_generation",
            generation_outcome,
            elapsed_ms(generation_started),
            remaining_ms(budget),
        )
    validation_stage = diagnostics["answer_validation"]
    assert isinstance(validation_stage, dict)
    validation_stage.update({"attempted": True, "status": "started"})
    validation_started = time.monotonic()
    draft_is_valid = validate_draft(draft, generation_hits)
    emit_question_stage_timing(
        str(payload.client_request_id),
        "answer_validation",
        "succeeded" if draft_is_valid else "failed",
        elapsed_ms(validation_started),
        remaining_ms(budget),
    )
    if not draft_is_valid:
        validation_stage["status"] = "succeeded" if draft_is_valid else "grounding_failed"
        if not main.settings.search_only_enabled:
            raise _generation_failed_error()
        fallback.fallback_reason = AiFallbackReason.GROUNDING_FAILED
        generation_stage["status"] = "grounding_failed"
        return await _save_if_authenticated(user, payload, fallback, diagnostics)
    validation_stage["status"] = "succeeded"
    # 2026-08-08: 모델이 스스로 판단한 action이 checklist 기반 추정(derive_answer_action)과
    # 얼마나 일치하는지 diagnostics에 남긴다 - 라우터 설명을 저장하던 것과 같은 이유로,
    # D-10 표본 검토 때 이 자기보고 신호를 신뢰해도 되는지 나중에 확인하기 위해서다.
    generation_stage["model_action"] = draft.action
    generation_stage["checklist_derived_action"] = derive_answer_action(draft.checklist)
    generation_stage["action_agrees_with_checklist"] = (
        draft.action == generation_stage["checklist_derived_action"]
    )
    if draft.action == "clarification_required":
        clarification = post_generation_clarification_answer(
            payload,
            draft.missing_information,
            mode="search_only" if main.settings.search_only_enabled else "ai",
        )
        generation_stage["status"] = "clarification_required"
        return await _save_if_authenticated(user, payload, clarification, diagnostics)
    citations = [
        Citation(
            id=f"C{index}",
            provision_id=hit.provision_id,
            document_title=hit.document_title,
            version_label=hit.version_label,
            path=hit.path,
            quote=hit.content,
            source_url=hit.source_url,
            source_kind=hit.source_kind,
            law_type_code=hit.law_type_code,
        )
        for index, hit in enumerate(generation_hits, 1)
    ]
    answer = QuestionResponse(
        request_id=str(payload.client_request_id),
        mode="ai",
        summary=draft.summary,
        scope=draft.scope,
        sections=draft.sections,
        checklist=draft.checklist,
        citations=citations,
        limitations=[*draft.limitations, "이 서비스는 법률 자문을 대체하지 않습니다."],
        corpus_as_of=corpus_as_of,
        requested_answer_mode=payload.answer_mode,
        action=draft.action,
        route=route_decision.route if route_decision is not None else None,
    )
    generation_stage["status"] = "succeeded"
    return await _save_if_authenticated(user, payload, answer, diagnostics)
