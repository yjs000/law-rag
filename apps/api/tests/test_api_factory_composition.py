"""Regression coverage for factory-scoped transport dependencies and seams."""

from contextlib import asynccontextmanager
from dataclasses import replace
from datetime import date
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from law_rag_core.domain.catalog import SourceKind

import app.main as main_module
from app.bootstrap import V2LlamaIndexResources
from app.domain.schemas import QuestionResponse, SearchHit

pytestmark = pytest.mark.usefixtures("ready_corpus_temporal_state")


class _FactoryRepository:
    """Minimal repository boundary used to distinguish a factory composition."""

    async def search(
        self, query: str, as_of_date: date, limit: int, _cursor: object | None
    ) -> list[SearchHit]:
        return [
            SearchHit(
                provision_id=uuid4(),
                document_id=uuid4(),
                document_title="Factory dependency statute",
                source_kind=SourceKind.LAW,
                version_label="factory-v1",
                effective_from=date(2020, 1, 1),
                effective_to=None,
                path="제1조",
                content="Factory-owned evidence.",
                source_url="https://www.law.go.kr/factory-test",
                score=1.0,
            )
        ]

    class _Result:
        def first(self) -> tuple[str]:
            return ("active",)

    class _Connection:
        async def execute(self, _statement: object) -> object:
            return _FactoryRepository._Result()

    class _Engine:
        @asynccontextmanager
        async def connect(self):
            yield _FactoryRepository._Connection()

    engine = _Engine()


def test_factory_request_uses_the_supplied_repository() -> None:
    """Fail if create_app routes requests through app.main's production repository."""

    factory_dependencies = replace(main_module.dependencies, repository=_FactoryRepository())

    response = TestClient(main_module.create_app(factory_dependencies)).post(
        "/v1/search",
        json={"query": "factory dependency", "as_of_date": "2026-07-15"},
    )

    assert response.status_code == 200
    assert response.json()[0]["document_title"] == "Factory dependency statute"


def test_factory_v2_request_uses_the_supplied_resources(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Fail if v2 readiness or search falls back to app.main's resource set."""

    factory_store = object()
    factory_embedder = object()
    factory_dependencies = replace(
        main_module.dependencies,
        repository=_FactoryRepository(),
        v2_resources=V2LlamaIndexResources(
            lambda: (factory_store, factory_embedder, object())  # type: ignore[arg-type]
        ),
    )
    monkeypatch.setattr(main_module.settings, "database_url", "postgresql://factory.test/law")

    async def factory_search(
        store: object, embedder: object, query: str, as_of_date: date, limit: int
    ) -> list[SearchHit]:
        assert store is factory_store
        assert embedder is factory_embedder
        return await _FactoryRepository().search(query, as_of_date, limit, None)

    monkeypatch.setattr(main_module, "llamaindex_search", factory_search)

    response = TestClient(main_module.create_app(factory_dependencies)).post(
        "/v2/search",
        json={"query": "factory v2 dependency", "as_of_date": "2026-07-15"},
    )

    assert response.status_code == 200
    assert response.json()[0]["document_title"] == "Factory dependency statute"


def test_question_route_uses_the_runtime_main_answer_seam(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Fail if the v1 route bypasses a patched app.main._answer_question seam."""

    async def patched_answer(*_args: object) -> QuestionResponse:
        return QuestionResponse(
            request_id="00000000-0000-4000-8000-000000000001",
            mode="search_only",
            summary="Answer supplied through app.main seam.",
            scope="factory seam regression",
            result_status="no_results",
            sections=[],
            checklist=[],
            citations=[],
            limitations=[],
        )

    monkeypatch.setattr(main_module, "_answer_question", patched_answer)

    response = TestClient(main_module.app).post(
        "/v1/questions",
        json={
            "question": "main seam answer",
            "as_of_date": "2026-07-15",
            "answer_mode": "search_only",
        },
    )

    assert response.status_code == 200
    assert response.json()["summary"] == "Answer supplied through app.main seam."


@pytest.mark.asyncio
async def test_app_lifespan_closes_each_long_lived_nvidia_adapter_once() -> None:
    """Catch a composition root that leaks a process-owned NVIDIA HTTP client."""

    class Adapter:
        def __init__(self) -> None:
            self.close_calls = 0

        async def aclose(self) -> None:
            self.close_calls += 1

    embedder = Adapter()
    answerer = Adapter()
    router = Adapter()
    app_dependencies = replace(
        main_module.dependencies,
        nvidia_embedder=embedder,
        nvidia_answerer=answerer,
        nvidia_question_router=router,
    )

    async with app_dependencies.lifespan(object()):
        pass

    assert (embedder.close_calls, answerer.close_calls, router.close_calls) == (1, 1, 1)
