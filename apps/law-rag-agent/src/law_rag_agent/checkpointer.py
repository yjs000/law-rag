from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

from law_rag_agent.config import Settings


def _psycopg_database_url(database_url: str) -> str:
    if database_url.startswith("postgresql+asyncpg://"):
        return database_url.replace("postgresql+asyncpg://", "postgresql://", 1)
    return database_url


def build_checkpointer_context(settings: Settings):
    if not settings.database_url:
        raise ValueError("database_url is required to build the checkpointer")
    return AsyncPostgresSaver.from_conn_string(_psycopg_database_url(settings.database_url))
