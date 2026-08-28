"""Version 1 HTTP transport routes."""

from fastapi import APIRouter

from app.api.v1 import account, corpus, questions


def build_router() -> APIRouter:
    """Assemble the unchanged v1 public route contract."""

    router = APIRouter()
    router.include_router(corpus.router)
    router.include_router(questions.router)
    router.include_router(account.router)
    return router
