"""Transport routers remain the only owners of public HTTP endpoint registration."""

from fastapi.routing import APIRoute

from app.api.v1 import build_router as build_v1_router
from app.api.v2 import build_router as build_v2_router
from app.main import create_app, dependencies


def _registered_routes(routes: object) -> dict[tuple[str, str], str]:
    """Traverse FastAPI's nested-router representation without flattening it."""

    registered: dict[tuple[str, str], str] = {}
    for route in routes:
        if isinstance(route, APIRoute):
            for method in route.methods:
                registered[(method, route.path)] = route.endpoint.__module__
            continue
        child = getattr(route, "original_router", None)
        if child is not None:
            registered.update(_registered_routes(child.routes))
    return registered


def test_application_composes_versioned_transport_routers() -> None:
    """Fail if a public route stops being registered by its versioned transport module."""

    application = create_app(dependencies)
    routes = _registered_routes(application.routes)

    expected_routes = {
        ("GET", "/health"): "app.api.v1.corpus",
        ("POST", "/v1/search"): "app.api.v1.corpus",
        ("GET", "/v1/provisions/{provision_id}"): "app.api.v1.corpus",
        ("GET", "/v1/documents/{document_id}/changes"): "app.api.v1.corpus",
        ("GET", "/v1/corpus/status"): "app.api.v1.corpus",
        ("POST", "/v1/questions"): "app.api.v1.questions",
        ("POST", "/v1/questions/{client_request_id}/cancel"): "app.api.v1.questions",
        ("POST", "/v1/auth/mock/google"): "app.api.v1.account",
        ("GET", "/v1/auth/me"): "app.api.v1.account",
        ("POST", "/v1/auth/logout"): "app.api.v1.account",
        ("DELETE", "/v1/account"): "app.api.v1.account",
        ("GET", "/v1/questions/history"): "app.api.v1.account",
        ("GET", "/v1/conversations"): "app.api.v1.account",
        ("GET", "/v1/conversations/{conversation_id}/turns"): "app.api.v1.account",
        ("DELETE", "/v1/conversations/{conversation_id}"): "app.api.v1.account",
        ("GET", "/v1/questions/history/{history_id}"): "app.api.v1.account",
        ("DELETE", "/v1/questions/history/{history_id}"): "app.api.v1.account",
        ("GET", "/v1/questions/history/{history_id}/checklist"): "app.api.v1.account",
        ("POST", "/v2/search"): "app.api.v2.search",
        ("POST", "/v2/question-executions"): "app.api.v2.executions",
        ("DELETE", "/v2/question-executions/{execution_id}"): "app.api.v2.executions",
        ("POST", "/v2/question-executions/{execution_id}/core"): "app.api.v2.sse",
        ("POST", "/v2/question-executions/{execution_id}/finalize"): "app.api.v2.sse",
    }
    public_routes = {
        route: module
        for route, module in routes.items()
        if route[1] == "/health" or route[1].startswith(("/v1/", "/v2/"))
    }

    assert public_routes == expected_routes
    assert build_v1_router.__module__ == "app.api.v1"
    assert build_v2_router.__module__ == "app.api.v2"
