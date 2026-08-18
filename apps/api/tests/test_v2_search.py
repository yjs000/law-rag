import pytest
from fastapi.testclient import TestClient


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
