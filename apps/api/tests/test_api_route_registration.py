"""Transport routers remain the only owners of public HTTP endpoint registration."""

from fastapi.routing import APIRoute

from app.api.v1 import build_router as build_v1_router
from app.api.v2 import build_router as build_v2_router
from app.main import create_app, dependencies


def _registered_routes(routes: object) -> dict[str, str]:
    """Traverse FastAPI's nested-router representation without flattening it."""

    registered: dict[str, str] = {}
    for route in routes:
        if isinstance(route, APIRoute):
            registered[route.path] = route.endpoint.__module__
            continue
        child = getattr(route, "original_router", None)
        if child is not None:
            registered.update(_registered_routes(child.routes))
    return registered


def test_application_composes_versioned_transport_routers() -> None:
    """Fail if a public route stops being registered by its versioned transport module."""

    application = create_app(dependencies)
    routes = _registered_routes(application.routes)

    assert routes["/v1/questions"] == "app.api.v1.questions"
    assert routes["/v1/auth/me"] == "app.api.v1.account"
    assert routes["/v1/corpus/status"] == "app.api.v1.corpus"
    assert routes["/v2/search"] == "app.api.v2.search"
    assert routes["/v2/question-executions"] == "app.api.v2.executions"
    assert routes["/v2/question-executions/{execution_id}/core"] == "app.api.v2.sse"
    assert build_v1_router.__module__ == "app.api.v1"
    assert build_v2_router.__module__ == "app.api.v2"
