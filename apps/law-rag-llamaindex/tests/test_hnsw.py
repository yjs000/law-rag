from __future__ import annotations

import importlib

import pytest
import sqlalchemy.ext.asyncio

from law_rag_llamaindex.hnsw import HnswIndexManager


class FakeResult:
    def __init__(self, value: bool) -> None:
        self.value = value

    def scalar_one(self) -> bool:
        return self.value


class FakeConnection:
    def __init__(self, *, status: bool = False) -> None:
        self.status = status
        self.execution_options_calls: list[dict[str, object]] = []
        self.executed: list[tuple[object, dict[str, object] | None]] = []

    async def execution_options(self, **options: object) -> FakeConnection:
        self.execution_options_calls.append(options)
        return self

    async def execute(
        self, statement: object, parameters: dict[str, object] | None = None
    ) -> FakeResult:
        self.executed.append((statement, parameters))
        return FakeResult(self.status)


class FakeConnectionContext:
    def __init__(self, connection: FakeConnection) -> None:
        self.connection = connection

    async def __aenter__(self) -> FakeConnection:
        return self.connection

    async def __aexit__(self, exc_type, exc_value, traceback) -> None:
        return None


class FakeEngine:
    def __init__(self, connection: FakeConnection) -> None:
        self.connection = connection
        self.connect_calls = 0

    def connect(self) -> FakeConnectionContext:
        self.connect_calls += 1
        return FakeConnectionContext(self.connection)


@pytest.mark.asyncio
async def test_enable_uses_autocommit_and_exact_v2_cosine_hnsw_ddl() -> None:
    connection = FakeConnection()
    manager = HnswIndexManager(FakeEngine(connection), "law_rag_llamaindex")

    await manager.enable()

    assert connection.execution_options_calls == [{"isolation_level": "AUTOCOMMIT"}]
    assert len(connection.executed) == 1
    statement, parameters = connection.executed[0]
    assert parameters is None
    assert str(statement).strip() == (
        "CREATE INDEX CONCURRENTLY IF NOT EXISTS "
        "data_law_rag_llamaindex_embedding_hnsw_idx "
        "ON data_law_rag_llamaindex USING hnsw "
        "(embedding vector_cosine_ops) "
        "WITH (m = 16, ef_construction = 128)"
    )


@pytest.mark.asyncio
async def test_disable_uses_autocommit_and_exact_v2_drop_ddl() -> None:
    connection = FakeConnection()
    manager = HnswIndexManager(FakeEngine(connection), "law_rag_llamaindex")

    await manager.disable()

    assert connection.execution_options_calls == [{"isolation_level": "AUTOCOMMIT"}]
    statement, parameters = connection.executed[0]
    assert parameters is None
    assert str(statement).strip() == (
        "DROP INDEX CONCURRENTLY IF EXISTS "
        "data_law_rag_llamaindex_embedding_hnsw_idx"
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("present", [True, False])
async def test_status_returns_catalog_result(present: bool) -> None:
    connection = FakeConnection(status=present)
    manager = HnswIndexManager(FakeEngine(connection), "law_rag_llamaindex")

    assert await manager.status() is present

    statement, parameters = connection.executed[0]
    assert "pg_class" in str(statement)
    assert parameters == {"index_name": "data_law_rag_llamaindex_embedding_hnsw_idx"}


@pytest.mark.asyncio
@pytest.mark.parametrize(("present", "expected"), [(True, False), (False, True)])
async def test_ensure_only_enables_missing_index(present: bool, expected: bool) -> None:
    connection = FakeConnection(status=present)
    manager = HnswIndexManager(FakeEngine(connection), "law_rag_llamaindex")

    assert await manager.ensure() is expected

    assert len(connection.executed) == (1 if present else 2)
    assert len(connection.execution_options_calls) == (0 if present else 1)


@pytest.mark.parametrize(
    "table_name",
    [
        "",
        "Law",
        "law-rag",
        "law.rag",
        "law rag",
        "law;drop",
        "other_table",
        None,
        42,
    ],
)
def test_rejects_invalid_table_name(table_name: object) -> None:
    with pytest.raises(ValueError):
        HnswIndexManager(FakeEngine(FakeConnection()), table_name)  # type: ignore[arg-type]


def test_import_does_not_create_engine_or_run_cli(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail_if_engine_created(*args: object, **kwargs: object) -> None:
        raise AssertionError("module import must not create a database engine")

    module = importlib.import_module("law_rag_llamaindex.hnsw")
    original_engine_factory = module.create_async_engine
    monkeypatch.setattr(sqlalchemy.ext.asyncio, "create_async_engine", fail_if_engine_created)
    importlib.reload(module)
    monkeypatch.setattr(module, "create_async_engine", original_engine_factory)
