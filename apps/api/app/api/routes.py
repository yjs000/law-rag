"""FastAPI URL registration grouped by public API responsibility."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from fastapi import APIRouter, FastAPI

from app.domain.auth_schemas import MockLoginResponse
from app.domain.schemas import (
    ConversationPage,
    ConversationTurnPage,
    CorpusStatus,
    DocumentChangesResponse,
    MockUser,
    ProvisionResponse,
    QuestionHistoryEntry,
    QuestionResponse,
    SearchHit,
)

Endpoint = Callable[..., Any]


@dataclass(frozen=True)
class ApiEndpoints:
    """HTTP handlers composed by :mod:`app.main` and registered by responsibility."""

    health: Endpoint
    search: Endpoint
    search_v2: Endpoint
    provision: Endpoint
    changes: Endpoint
    corpus_status: Endpoint
    question: Endpoint
    prepare_question_execution: Endpoint
    core_question_execution: Endpoint
    finalize_question_execution: Endpoint
    cancel_question_execution: Endpoint
    cancel_question: Endpoint
    mock_google_login: Endpoint
    current_user: Endpoint
    logout: Endpoint
    delete_account: Endpoint
    question_history: Endpoint
    conversations: Endpoint
    conversation_turns: Endpoint
    delete_conversation: Endpoint
    question_history_detail: Endpoint
    delete_question_history: Endpoint
    export_checklist: Endpoint


def register_routes(app: FastAPI, endpoints: ApiEndpoints) -> None:
    """Register all public routes without coupling URL definitions to business logic."""

    app.include_router(_catalog_router(endpoints))
    app.include_router(_question_router(endpoints))
    app.include_router(_auth_and_history_router(endpoints))


def _catalog_router(endpoints: ApiEndpoints) -> APIRouter:
    router = APIRouter()
    router.add_api_route(
        "/health", endpoints.health, methods=["GET"], response_model=dict[str, str]
    )
    router.add_api_route(
        "/v1/search", endpoints.search, methods=["POST"], response_model=list[SearchHit]
    )
    router.add_api_route(
        "/v2/search", endpoints.search_v2, methods=["POST"], response_model=list[SearchHit]
    )
    router.add_api_route(
        "/v1/provisions/{provision_id}",
        endpoints.provision,
        methods=["GET"],
        response_model=ProvisionResponse,
    )
    router.add_api_route(
        "/v1/documents/{document_id}/changes",
        endpoints.changes,
        methods=["GET"],
        response_model=DocumentChangesResponse,
    )
    router.add_api_route(
        "/v1/corpus/status",
        endpoints.corpus_status,
        methods=["GET"],
        response_model=CorpusStatus,
    )
    return router


def _question_router(endpoints: ApiEndpoints) -> APIRouter:
    router = APIRouter()
    router.add_api_route(
        "/v1/questions", endpoints.question, methods=["POST"], response_model=QuestionResponse
    )
    router.add_api_route(
        "/v2/question-executions", endpoints.prepare_question_execution, methods=["POST"]
    )
    router.add_api_route(
        "/v2/question-executions/{execution_id}/core",
        endpoints.core_question_execution,
        methods=["POST"],
    )
    router.add_api_route(
        "/v2/question-executions/{execution_id}/finalize",
        endpoints.finalize_question_execution,
        methods=["POST"],
    )
    router.add_api_route(
        "/v2/question-executions/{execution_id}",
        endpoints.cancel_question_execution,
        methods=["DELETE"],
        status_code=202,
    )
    router.add_api_route(
        "/v1/questions/{client_request_id}/cancel",
        endpoints.cancel_question,
        methods=["POST"],
        status_code=202,
    )
    return router


def _auth_and_history_router(endpoints: ApiEndpoints) -> APIRouter:
    router = APIRouter()
    router.add_api_route(
        "/v1/auth/mock/google",
        endpoints.mock_google_login,
        methods=["POST"],
        response_model=MockLoginResponse,
    )
    router.add_api_route(
        "/v1/auth/me", endpoints.current_user, methods=["GET"], response_model=MockUser
    )
    router.add_api_route("/v1/auth/logout", endpoints.logout, methods=["POST"], status_code=204)
    router.add_api_route(
        "/v1/account", endpoints.delete_account, methods=["DELETE"], status_code=204
    )
    router.add_api_route(
        "/v1/questions/history",
        endpoints.question_history,
        methods=["GET"],
        response_model=list[QuestionHistoryEntry],
    )
    router.add_api_route(
        "/v1/conversations",
        endpoints.conversations,
        methods=["GET"],
        response_model=ConversationPage,
    )
    router.add_api_route(
        "/v1/conversations/{conversation_id}/turns",
        endpoints.conversation_turns,
        methods=["GET"],
        response_model=ConversationTurnPage,
    )
    router.add_api_route(
        "/v1/conversations/{conversation_id}",
        endpoints.delete_conversation,
        methods=["DELETE"],
        status_code=204,
    )
    router.add_api_route(
        "/v1/questions/history/{history_id}",
        endpoints.question_history_detail,
        methods=["GET"],
        response_model=QuestionHistoryEntry,
    )
    router.add_api_route(
        "/v1/questions/history/{history_id}",
        endpoints.delete_question_history,
        methods=["DELETE"],
        status_code=204,
    )
    router.add_api_route(
        "/v1/questions/history/{history_id}/checklist",
        endpoints.export_checklist,
        methods=["GET"],
    )
    return router
