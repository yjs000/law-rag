from law_rag_agent.checkpointer import _psycopg_database_url
from law_rag_agent.config import Settings


def test_psycopg_database_url_strips_asyncpg_driver():
    assert (
        _psycopg_database_url("postgresql+asyncpg://user:pass@host:5432/db")
        == "postgresql://user:pass@host:5432/db"
    )


def test_psycopg_database_url_leaves_plain_url_unchanged():
    url = "postgresql://user:pass@host:5432/db"
    assert _psycopg_database_url(url) == url


def test_build_checkpointer_context_requires_database_url():
    import pytest

    settings = Settings(_env_file=None, database_url=None)
    with pytest.raises(ValueError, match="database_url"):
        from law_rag_agent.checkpointer import build_checkpointer_context

        build_checkpointer_context(settings)


def test_build_checkpointer_context_normalizes_url_and_returns_context_manager(monkeypatch):
    from unittest.mock import Mock

    from law_rag_agent import checkpointer

    settings = Settings(
        _env_file=None,
        database_url="postgresql+asyncpg://user:pass@host:5432/db",
    )
    context_manager = object()
    from_conn_string = Mock(return_value=context_manager)
    monkeypatch.setattr(checkpointer.AsyncPostgresSaver, "from_conn_string", from_conn_string)

    result = checkpointer.build_checkpointer_context(settings)

    from_conn_string.assert_called_once_with("postgresql://user:pass@host:5432/db")
    assert result is context_manager
