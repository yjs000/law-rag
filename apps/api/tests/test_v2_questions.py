from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient


def test_v2_resources_factory_uses_active_generation_provider_not_legacy_table(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from law_rag_llamaindex.active_index import ActiveGenerationIndexProvider

    import app.main as main_module

    monkeypatch.setattr(main_module.settings, "database_url", "postgresql://factory.example/law")
    monkeypatch.setattr(main_module, "llamaindex_vector_store", None)
    monkeypatch.setattr(main_module, "llamaindex_embedder", None)
    monkeypatch.setattr(main_module, "llamaindex_repository", None)

    class LlamaIndexSettings:
        nvidia_api_key = "nvidia-test-key"

    monkeypatch.setattr(main_module, "llamaindex_settings", LlamaIndexSettings())
    embedder = object()

    def build_generation_store(*args, **kwargs) -> object:
        raise AssertionError("v2 reads must resolve the active generation, never legacy table")

    def build_embedder(settings) -> object:
        return embedder

    class RepositoryDouble:
        pass

    def build_repository(delegate, vector_store, repository_embedder) -> RepositoryDouble:
        assert delegate is main_module.repository
        assert isinstance(vector_store, ActiveGenerationIndexProvider)
        assert repository_embedder is embedder
        return RepositoryDouble()

    monkeypatch.setattr(main_module, "build_generation_vector_store", build_generation_store)
    monkeypatch.setattr(main_module, "build_llamaindex_embedder", build_embedder)
    monkeypatch.setattr(main_module, "LlamaIndexLegalRepository", build_repository)
    main_module._build_llamaindex_resources.cache_clear()

    first = main_module._build_llamaindex_resources(
        main_module.settings.database_url, "nvidia-test-key"
    )
    second = main_module._build_llamaindex_resources(
        main_module.settings.database_url, "nvidia-test-key"
    )

    assert first is not None
    assert second is first
    assert isinstance(first[0], ActiveGenerationIndexProvider)
    resolved = main_module._llamaindex_resources()
    assert resolved is not None
    assert resolved[0] is first[0]
    assert resolved[1] is embedder
    assert resolved[2] is first[2]
    main_module._build_llamaindex_resources.cache_clear()


def test_v2_repository_does_not_request_legacy_query_embedding() -> None:
    import app.main as main_module
    from app.adapters.llamaindex_repository import LlamaIndexLegalRepository

    v2_repository = LlamaIndexLegalRepository(MagicMock(), object(), object())

    assert main_module._requires_legacy_query_embedding(v2_repository) is False
    assert main_module._requires_legacy_query_embedding(MagicMock()) is True

def test_v2_resources_factory_retries_after_transient_initialization_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import app.main as main_module

    monkeypatch.setattr(main_module.settings, "database_url", "postgresql://factory.example/law")
    monkeypatch.setattr(main_module, "llamaindex_vector_store", None)
    monkeypatch.setattr(main_module, "llamaindex_embedder", None)
    monkeypatch.setattr(main_module, "llamaindex_repository", None)

    class LlamaIndexSettings:
        nvidia_api_key = "nvidia-test-key"

    monkeypatch.setattr(main_module, "llamaindex_settings", LlamaIndexSettings())
    attempts = 0
    embedder = object()

    def build_embedder(settings) -> object:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise RuntimeError("temporary initialization failure")
        return embedder

    monkeypatch.setattr(main_module, "build_llamaindex_embedder", build_embedder)
    monkeypatch.setattr(
        main_module,
        "LlamaIndexLegalRepository",
        lambda delegate, vector_store, repository_embedder: object(),
    )
    main_module._build_llamaindex_resources.cache_clear()

    assert main_module._llamaindex_resources() is None
    assert main_module._llamaindex_resources() is not None
    assert attempts == 2
    main_module._build_llamaindex_resources.cache_clear()


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    import app.main as main_module

    monkeypatch.setattr(main_module, "llamaindex_repository", object())

    async def fake_ready() -> bool:
        return True

    async def fake_supported_as_of_date(requested_date, repository) -> None:
        return None

    monkeypatch.setattr(main_module, "_v2_index_ready", fake_ready)
    monkeypatch.setattr(main_module, "_require_supported_as_of_date", fake_supported_as_of_date)
    return TestClient(main_module.app)


def test_v2_questions_returns_503_when_not_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    import app.main as main_module

    monkeypatch.setattr(main_module, "llamaindex_repository", None)
    client = TestClient(main_module.app)
    response = client.post(
        "/v2/questions",
        json={
            "client_request_id": "11111111-1111-1111-1111-111111111111",
            "question": "태양광 설비 인허가 요건이 뭐야",
            "as_of_date": "2026-01-01",
            "project_stage": "planning",
            "answer_mode": "search_only",
        },
    )
    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "v2_search_not_ready"


def test_v2_questions_returns_503_when_resource_factory_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import app.main as main_module

    monkeypatch.setattr(main_module.settings, "database_url", "postgresql://db.example/law")
    monkeypatch.setattr(
        main_module,
        "llamaindex_settings",
        type(
            "Settings",
            (),
            {
                "nvidia_api_key": "nvidia-test-key",
            },
        )(),
    )
    monkeypatch.setattr(main_module, "llamaindex_vector_store", None)
    monkeypatch.setattr(main_module, "llamaindex_embedder", None)
    monkeypatch.setattr(main_module, "llamaindex_repository", None)

    def fail_build(settings) -> object:
        raise RuntimeError("database credentials and DDL details must stay private")

    monkeypatch.setattr(main_module, "build_llamaindex_embedder", fail_build)
    main_module._build_llamaindex_resources.cache_clear()
    response = TestClient(main_module.app).post(
        "/v2/questions",
        json={
            "client_request_id": "11111111-1111-1111-1111-111111111111",
            "question": "태양광 설비 인허가 요건이 뭐야",
            "as_of_date": "2026-01-01",
            "project_stage": "planning",
            "answer_mode": "search_only",
        },
    )

    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "v2_search_not_ready"
    assert "database credentials" not in response.text


def test_v2_questions_returns_503_when_index_is_not_ready(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import app.main as main_module

    monkeypatch.setattr(main_module, "llamaindex_repository", object())

    async def fake_not_ready() -> bool:
        return False

    monkeypatch.setattr(main_module, "_v2_index_ready", fake_not_ready)
    client = TestClient(main_module.app)
    response = client.post(
        "/v2/questions",
        json={
            "client_request_id": "11111111-1111-1111-1111-111111111111",
            "question": "태양광 설비 인허가 요건이 뭐야",
            "as_of_date": "2026-01-01",
            "project_stage": "planning",
            "answer_mode": "search_only",
        },
    )
    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "v2_search_not_ready"


def test_v2_questions_returns_stable_503_when_readiness_marker_connection_fails(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    import app.main as main_module

    monkeypatch.setattr(main_module, "llamaindex_repository", object())

    async def failed_readiness_check() -> bool:
        raise RuntimeError("migration state and database credentials must stay private")

    monkeypatch.setattr(main_module, "_v2_index_ready", failed_readiness_check)
    response = TestClient(main_module.app).post(
        "/v2/questions",
        json={
            "client_request_id": "11111111-1111-1111-1111-111111111111",
            "question": "태양광 설비 인허가 요건이 뭐야",
            "as_of_date": "2026-01-01",
            "project_stage": "planning",
            "answer_mode": "search_only",
        },
    )

    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "v2_search_not_ready"
    assert "database credentials" not in response.text
    assert "database credentials" not in caplog.text


def test_v2_questions_uses_llamaindex_repository_for_evidence(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    import app.main as main_module
    from app.domain.schemas import QuestionResponse

    captured_repository = {}

    async def fake_answer_question(payload, request, user, budget, repository):
        captured_repository["repository"] = repository
        return QuestionResponse(
            request_id=str(payload.client_request_id),
            mode="search_only",
            summary="ok",
            scope="",
            sections=[],
            checklist=[],
            citations=[],
            limitations=[],
            fallback_reason=None,
        )

    monkeypatch.setattr(main_module, "_answer_question", fake_answer_question)

    response = client.post(
        "/v2/questions",
        json={
            "client_request_id": "11111111-1111-1111-1111-111111111111",
            "question": "태양광 설비 인허가 요건이 뭐야",
            "as_of_date": "2026-01-01",
            "project_stage": "planning",
            "answer_mode": "search_only",
        },
    )
    assert response.status_code == 200
    assert captured_repository["repository"] is main_module.llamaindex_repository
