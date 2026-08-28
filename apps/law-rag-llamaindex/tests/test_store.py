import pytest

from law_rag_llamaindex.config import Settings
from law_rag_llamaindex.generations import GenerationCatalog
from law_rag_llamaindex.store import build_generation_vector_store, build_vector_store


def test_build_vector_store_uses_configured_table_and_dimension():
    settings = Settings(
        _env_file=None,
        database_url="postgresql+asyncpg://user:pass@localhost:5432/lawrag",
        embed_dim=2048,
        vector_table_name="law_rag_llamaindex",
        hnsw_kwargs=None,
    )
    store = build_vector_store(settings)
    assert store.table_name == "law_rag_llamaindex"
    assert store.embed_dim == 2048
    assert store.hnsw_kwargs is None


def test_build_vector_store_passes_through_hnsw_kwargs_when_set():
    settings = Settings(
        _env_file=None,
        database_url="postgresql+asyncpg://user:pass@localhost:5432/lawrag",
        embed_dim=2048,
        vector_table_name="law_rag_llamaindex",
        hnsw_kwargs={"hnsw_m": 16, "hnsw_ef_construction": 64},
    )
    store = build_vector_store(settings)
    assert store.hnsw_kwargs == {"hnsw_m": 16, "hnsw_ef_construction": 64}


def test_build_vector_store_raises_without_database_url():
    settings = Settings(_env_file=None, database_url=None)
    with pytest.raises(ValueError, match="database_url"):
        build_vector_store(settings)


def test_build_generation_vector_store_receives_caller_owned_engines(monkeypatch) -> None:
    import law_rag_llamaindex.store as store_module

    settings = Settings(
        _env_file=None,
        database_url="postgresql+asyncpg://user:pass@localhost:5432/lawrag",
        embed_dim=2048,
    )
    catalog = GenerationCatalog()
    generation = catalog.start("a" * 64, "b" * 64)
    sync_engine = object()
    async_engine = object()
    captured: dict[str, object] = {}

    class FakeStore:
        def __init__(self, **kwargs) -> None:
            captured.update(kwargs)

    monkeypatch.setattr(store_module, "PGVectorStore", FakeStore)

    result = build_generation_vector_store(
        settings,
        generation,
        engine=sync_engine,
        async_engine=async_engine,
        perform_setup=False,
    )

    assert isinstance(result, FakeStore)
    assert captured["table_name"] == generation.table_name
    assert captured["engine"] is sync_engine
    assert captured["async_engine"] is async_engine
    assert captured["perform_setup"] is False
