"""v2 LlamaIndex PostgreSQL vector store를 구성한다."""

from llama_index.vector_stores.postgres import PGVectorStore
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.ext.asyncio import AsyncEngine

from law_rag_llamaindex.config import Settings
from law_rag_llamaindex.generations import RetrievalGeneration


def build_vector_store(settings: Settings) -> PGVectorStore:
    """데이터베이스 URL이 있는 설정으로 vector store를 생성한다. (DB 저장소연결후 store객체 생성)

    URL이 없으면 네트워크 연결을 시도하지 않고 `ValueError`를 발생시킨다.
    """
    if not settings.database_url:
        raise ValueError("database_url is required to build the vector store")
    url = make_url(settings.database_url)
    return PGVectorStore.from_params(
        host=url.host,
        port=url.port or 5432,
        database=url.database,
        user=url.username,
        password=url.password,
        table_name=settings.vector_table_name,
        embed_dim=settings.embed_dim,
        hnsw_kwargs=settings.hnsw_kwargs,
        use_jsonb=True,
        perform_setup=True,
    )


def build_generation_vector_store(
    settings: Settings,
    generation: RetrievalGeneration,
    *,
    engine: Engine,
    async_engine: AsyncEngine,
    perform_setup: bool,
) -> PGVectorStore:
    """Open one server-derived generation table with caller-owned engines.

    The caller is responsible for engine lifecycle. API reads pass
    ``perform_setup=False`` so a request can never create a missing table.
    """

    return PGVectorStore(
        table_name=generation.table_name,
        embed_dim=settings.embed_dim,
        hnsw_kwargs=settings.hnsw_kwargs,
        use_jsonb=True,
        perform_setup=perform_setup,
        engine=engine,
        async_engine=async_engine,
    )
