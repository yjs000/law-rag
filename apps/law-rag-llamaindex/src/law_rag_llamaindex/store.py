from llama_index.vector_stores.postgres import PGVectorStore
from sqlalchemy.engine import make_url

from law_rag_llamaindex.config import Settings


def build_vector_store(settings: Settings) -> PGVectorStore:
    if not settings.database_url:
        raise ValueError("database_url is required to build the vector store")
    url = make_url(settings.database_url)
    return PGVectorStore.from_params(
        host=url.host,
        port=str(url.port or 5432),
        database=url.database,
        user=url.username,
        password=url.password,
        table_name=settings.vector_table_name,
        embed_dim=settings.embed_dim,
        hnsw_kwargs=settings.hnsw_kwargs,
        use_jsonb=True,
        perform_setup=True,
    )
