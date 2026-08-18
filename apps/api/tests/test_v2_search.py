import os
import subprocess
import sys

import pytest
from fastapi.testclient import TestClient


def test_module_import_does_not_build_vector_store_with_database_only() -> None:
    child_environment = os.environ.copy()
    child_environment.update(
        {
            "DATABASE_URL": "postgresql://db.example/law",
            "NVIDIA_API_KEY": "",
            "ENVIRONMENT": "test",
            "SUPABASE_URL": "",
            "SUPABASE_SECRET_KEY": "",
            "COLLECTOR_STATE_DIR": ".data/nonexistent-api-test-state",
            "PYTHONPATH": os.getcwd(),
        }
    )
    script = """
from law_rag_llamaindex import store

def fail_build(settings):
    raise AssertionError("vector store must not be built without NVIDIA_API_KEY")

store.build_vector_store = fail_build
import app.main as main_module

assert main_module.llamaindex_vector_store is None
assert main_module.llamaindex_embedder is None
assert main_module.llamaindex_repository is None
"""
    result = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        env=child_environment,
        check=False,
    )

    assert result.returncode == 0, result.stderr


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    import app.main as main_module

    monkeypatch.setattr(main_module, "llamaindex_vector_store", object())
    monkeypatch.setattr(main_module, "llamaindex_embedder", object())

    async def fake_ready() -> bool:
        return True

    async def fake_search(store, embedder, query, as_of_date, limit):
        return []

    monkeypatch.setattr(main_module, "_v2_index_ready", fake_ready)
    monkeypatch.setattr(main_module, "llamaindex_search", fake_search)
    return TestClient(main_module.app)


def test_v2_search_returns_empty_list_when_ready(client: TestClient) -> None:
    response = client.post(
        "/v2/search", json={"query": "태양광", "as_of_date": "2026-01-01", "limit": 5}
    )

    assert response.status_code == 200
    assert response.json() == []


def test_v2_search_returns_503_with_stable_code_when_not_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import app.main as main_module

    monkeypatch.setattr(main_module, "llamaindex_vector_store", None)
    monkeypatch.setattr(main_module, "llamaindex_embedder", None)
    client = TestClient(main_module.app)

    response = client.post(
        "/v2/search", json={"query": "태양광", "as_of_date": "2026-01-01", "limit": 5}
    )

    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "v2_search_not_ready"


def test_v2_search_returns_503_when_resource_factory_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import app.main as main_module

    monkeypatch.setattr(main_module.settings, "database_url", "postgresql://db.example/law")
    monkeypatch.setattr(main_module, "llamaindex_settings", type("Settings", (), {
        "nvidia_api_key": "nvidia-test-key",
    })())
    monkeypatch.setattr(main_module, "llamaindex_vector_store", None)
    monkeypatch.setattr(main_module, "llamaindex_embedder", None)
    monkeypatch.setattr(main_module, "llamaindex_repository", None)

    def fail_build(settings) -> object:
        raise RuntimeError("database credentials and DDL details must stay private")

    monkeypatch.setattr(main_module, "build_llamaindex_vector_store", fail_build)
    main_module._build_llamaindex_resources.cache_clear()
    response = TestClient(main_module.app).post(
        "/v2/search", json={"query": "태양광", "as_of_date": "2026-01-01", "limit": 5}
    )

    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "v2_search_not_ready"
    assert "database credentials" not in response.text
