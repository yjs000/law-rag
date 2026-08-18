from law_rag_llamaindex.config import Settings
from law_rag_llamaindex.store import build_vector_store


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
