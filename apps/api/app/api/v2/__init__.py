"""Version 2 HTTP transport routes."""

from fastapi import APIRouter

from app.api.v2 import executions, search, sse


def build_router() -> APIRouter:
    """Assemble the v2 search and execution transport contract."""

    router = APIRouter()
    router.include_router(search.router)
    router.include_router(executions.router)
    router.include_router(sse.router)
    return router
