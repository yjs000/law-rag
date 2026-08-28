"""Regression coverage for the public route registration boundary."""

from fastapi.middleware.cors import CORSMiddleware
from fastapi.testclient import TestClient

from app.main import app, settings


def test_route_registration_preserves_public_openapi_contract() -> None:
    """All existing public URL and operation identifiers remain registered."""
    paths = TestClient(app).get("/openapi.json").json()["paths"]

    operations = {
        (path, method): operation["operationId"]
        for path, methods in paths.items()
        for method, operation in methods.items()
    }

    assert operations == {
        ("/health", "get"): "health_health_get",
        ("/v1/search", "post"): "search_v1_search_post",
        ("/v2/search", "post"): "search_v2_v2_search_post",
        ("/v1/questions", "post"): "question_v1_questions_post",
        (
            "/v2/question-executions",
            "post",
        ): "prepare_question_execution_v2_question_executions_post",
        (
            "/v2/question-executions/{execution_id}/core",
            "post",
        ): "core_question_execution_v2_question_executions__execution_id__core_post",
        (
            "/v2/question-executions/{execution_id}/finalize",
            "post",
        ): "finalize_question_execution_v2_question_executions__execution_id__finalize_post",
        (
            "/v2/question-executions/{execution_id}",
            "delete",
        ): "cancel_question_execution_v2_question_executions__execution_id__delete",
        (
            "/v1/questions/{client_request_id}/cancel",
            "post",
        ): "cancel_question_v1_questions__client_request_id__cancel_post",
        (
            "/v1/auth/mock/google",
            "post",
        ): "mock_google_login_v1_auth_mock_google_post",
        ("/v1/auth/me", "get"): "current_user_v1_auth_me_get",
        ("/v1/auth/logout", "post"): "logout_v1_auth_logout_post",
        ("/v1/account", "delete"): "delete_account_v1_account_delete",
        (
            "/v1/questions/history",
            "get",
        ): "question_history_v1_questions_history_get",
        ("/v1/conversations", "get"): "conversations_v1_conversations_get",
        (
            "/v1/conversations/{conversation_id}/turns",
            "get",
        ): "conversation_turns_v1_conversations__conversation_id__turns_get",
        (
            "/v1/conversations/{conversation_id}",
            "delete",
        ): "delete_conversation_v1_conversations__conversation_id__delete",
        (
            "/v1/questions/history/{history_id}",
            "get",
        ): "question_history_detail_v1_questions_history__history_id__get",
        (
            "/v1/questions/history/{history_id}",
            "delete",
        ): "delete_question_history_v1_questions_history__history_id__delete",
        (
            "/v1/questions/history/{history_id}/checklist",
            "get",
        ): "export_checklist_v1_questions_history__history_id__checklist_get",
        (
            "/v1/provisions/{provision_id}",
            "get",
        ): "provision_v1_provisions__provision_id__get",
        (
            "/v1/documents/{document_id}/changes",
            "get",
        ): "changes_v1_documents__document_id__changes_get",
        ("/v1/corpus/status", "get"): "corpus_status_v1_corpus_status_get",
    }


def test_route_registration_preserves_success_schemas_and_cors() -> None:
    """Registration keeps documented response models and browser request permissions."""
    client = TestClient(app)
    paths = client.get("/openapi.json").json()["paths"]

    expected_success_statuses = {
        ("/health", "get"): "200",
        ("/v1/search", "post"): "200",
        ("/v2/search", "post"): "200",
        ("/v1/questions", "post"): "200",
        ("/v2/question-executions", "post"): "200",
        ("/v2/question-executions/{execution_id}/core", "post"): "200",
        ("/v2/question-executions/{execution_id}/finalize", "post"): "200",
        ("/v2/question-executions/{execution_id}", "delete"): "202",
        ("/v1/questions/{client_request_id}/cancel", "post"): "202",
        ("/v1/auth/mock/google", "post"): "200",
        ("/v1/auth/me", "get"): "200",
        ("/v1/auth/logout", "post"): "204",
        ("/v1/account", "delete"): "204",
        ("/v1/questions/history", "get"): "200",
        ("/v1/conversations", "get"): "200",
        ("/v1/conversations/{conversation_id}/turns", "get"): "200",
        ("/v1/conversations/{conversation_id}", "delete"): "204",
        ("/v1/questions/history/{history_id}", "get"): "200",
        ("/v1/questions/history/{history_id}", "delete"): "204",
        ("/v1/questions/history/{history_id}/checklist", "get"): "200",
        ("/v1/provisions/{provision_id}", "get"): "200",
        ("/v1/documents/{document_id}/changes", "get"): "200",
        ("/v1/corpus/status", "get"): "200",
    }
    actual_success_statuses = {
        route: next(
            status_code
            for status_code in ("200", "202", "204")
            if status_code in paths[route[0]][route[1]]["responses"]
        )
        for route in expected_success_statuses
    }
    assert actual_success_statuses == expected_success_statuses

    def response_schema(path: str, method: str) -> dict[str, object]:
        response = paths[path][method]["responses"]["200"]
        return response["content"]["application/json"]["schema"]

    assert response_schema("/health", "get")["type"] == "object"
    assert response_schema("/health", "get")["additionalProperties"] == {"type": "string"}
    assert response_schema("/v1/search", "post")["items"] == {
        "$ref": "#/components/schemas/SearchHit"
    }
    assert response_schema("/v2/search", "post")["items"] == {
        "$ref": "#/components/schemas/SearchHit"
    }
    expected_references = {
        ("/v1/questions", "post"): "QuestionResponse",
        ("/v1/auth/mock/google", "post"): "MockLoginResponse",
        ("/v1/auth/me", "get"): "MockUser",
        ("/v1/conversations", "get"): "ConversationPage",
        ("/v1/conversations/{conversation_id}/turns", "get"): "ConversationTurnPage",
        ("/v1/questions/history/{history_id}", "get"): "QuestionHistoryEntry",
        ("/v1/provisions/{provision_id}", "get"): "ProvisionResponse",
        ("/v1/documents/{document_id}/changes", "get"): "DocumentChangesResponse",
        ("/v1/corpus/status", "get"): "CorpusStatus",
    }
    for route, model_name in expected_references.items():
        assert response_schema(*route) == {"$ref": f"#/components/schemas/{model_name}"}

    preflight = client.options(
        "/v2/question-executions",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "DELETE",
            "Access-Control-Request-Headers": (
                "Authorization, Content-Type, Idempotency-Key, X-Execution-Capability, "
                "X-Terms-Version, X-Privacy-Version"
            ),
        },
    )
    assert preflight.status_code == 200
    assert preflight.headers["access-control-allow-origin"] == "http://localhost:3000"
    assert {"GET", "POST", "DELETE"} <= set(
        preflight.headers["access-control-allow-methods"].split(", ")
    )
    assert {
        "authorization",
        "content-type",
        "idempotency-key",
        "x-execution-capability",
        "x-terms-version",
        "x-privacy-version",
    } <= {
        header.strip().lower()
        for header in preflight.headers["access-control-allow-headers"].split(",")
    }


def test_route_registration_preserves_inferred_schemas_and_exact_cors_policy() -> None:
    """Routes without explicit models and the CORS policy keep their original contracts."""
    client = TestClient(app)
    paths = client.get("/openapi.json").json()["paths"]

    def response_schema(path: str, method: str, status_code: str = "200") -> dict[str, object]:
        response = paths[path][method]["responses"][status_code]
        return response["content"]["application/json"]["schema"]

    assert response_schema("/v1/questions/history", "get")["items"] == {
        "$ref": "#/components/schemas/QuestionHistoryEntry"
    }
    assert response_schema("/v2/question-executions", "post") == {
        "type": "object",
        "additionalProperties": True,
        "title": "Response Prepare Question Execution V2 Question Executions Post",
    }
    assert response_schema("/v2/question-executions/{execution_id}/core", "post") == {}
    assert response_schema("/v2/question-executions/{execution_id}/finalize", "post") == {}
    assert response_schema("/v1/questions/history/{history_id}/checklist", "get") == {}
    assert response_schema("/v2/question-executions/{execution_id}", "delete", "202")[
        "additionalProperties"
    ] == {"type": "boolean"}
    assert response_schema("/v1/questions/{client_request_id}/cancel", "post", "202")[
        "additionalProperties"
    ] == {"type": "boolean"}

    cors = next(
        middleware for middleware in app.user_middleware if middleware.cls is CORSMiddleware
    )
    assert cors.kwargs == {
        "allow_origins": settings.web_origins,
        "allow_credentials": False,
        "allow_methods": ["GET", "POST", "DELETE"],
        "allow_headers": [
            "Authorization",
            "Content-Type",
            "Idempotency-Key",
            "X-Execution-Capability",
            "X-Terms-Version",
            "X-Privacy-Version",
        ],
    }

    requested_headers = (
        "Authorization, Content-Type, Idempotency-Key, X-Execution-Capability, "
        "X-Terms-Version, X-Privacy-Version"
    )
    for origin in settings.web_origins:
        preflight = client.options(
            "/v2/question-executions",
            headers={
                "Origin": origin,
                "Access-Control-Request-Method": "DELETE",
                "Access-Control-Request-Headers": requested_headers,
            },
        )
        assert preflight.status_code == 200
        assert preflight.headers["access-control-allow-origin"] == origin

    rejected = client.options(
        "/v2/question-executions",
        headers={
            "Origin": "https://untrusted.example",
            "Access-Control-Request-Method": "DELETE",
            "Access-Control-Request-Headers": requested_headers,
        },
    )
    assert rejected.status_code == 400
    assert "access-control-allow-origin" not in rejected.headers
