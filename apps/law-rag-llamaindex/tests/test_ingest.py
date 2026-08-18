import os
from typing import cast

import pytest
from llama_index.core.schema import TextNode
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncEngine

from law_rag_llamaindex.ingest import (
    build_nodes,
    changed_provision_ids,
    existing_hashes,
    run_ingestion,
)
from law_rag_llamaindex.passage import build_passage_text, compute_source_text_sha256


def _record(provision_id: str, content: str) -> dict:
    return {
        "provision_id": provision_id,
        "document_id": "doc-1",
        "document_title": "에너지법",
        "source_kind": "statute",
        "law_type_code": "01",
        "version_label": "MST 1",
        "effective_from": "2024-01-01",
        "effective_to": None,
        "path": "제1조",
        "heading": None,
        "content": content,
        "source_url": "https://example.test",
    }


def test_changed_provision_ids_includes_new_and_changed_only():
    provisions = [_record("a", "본문 A"), _record("b", "본문 B")]
    hash_a = compute_source_text_sha256(build_passage_text(provisions[0]))
    # "a" unchanged (hash matches), "b" is new (no existing hash)
    existing = {"a": hash_a}
    assert changed_provision_ids(provisions, existing) == {"b"}


def test_changed_provision_ids_includes_content_changed_rows():
    provisions = [_record("a", "본문 A 수정됨")]
    existing = {"a": compute_source_text_sha256(build_passage_text(_record("a", "본문 A")))}
    assert changed_provision_ids(provisions, existing) == {"a"}


def test_build_nodes_sets_id_text_and_metadata():
    provisions = [_record("a", "본문 A")]
    nodes = build_nodes(provisions)
    assert len(nodes) == 1
    node = nodes[0]
    assert isinstance(node, TextNode)
    assert node.id_ == "a"
    assert node.text == build_passage_text(provisions[0])
    assert node.metadata["content"] == "본문 A"
    assert "source_text_sha256" in node.metadata


class _ConnectionContext:
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_value, traceback):
        return None


class _MissingTableConnection(_ConnectionContext):
    def __init__(self) -> None:
        self.execute_called = False

    async def run_sync(self, _sync_operation):
        return False

    async def execute(self, _query):
        self.execute_called = True
        raise AssertionError("missing table must not be queried")


class _ExistingTableFailingQueryConnection(_ConnectionContext):
    async def run_sync(self, _sync_operation):
        return True

    async def execute(self, _query):
        raise OperationalError("SELECT 1", {}, RuntimeError("connection lost"))


class _Engine:
    def __init__(self, connection: _ConnectionContext) -> None:
        self._connection = connection

    def connect(self):
        return self._connection


class _LifecycleResult:
    def __init__(self, run_id: str) -> None:
        self._run_id = run_id

    def scalar_one(self) -> str:
        return self._run_id

    def __iter__(self):
        return iter(())


class _LifecycleConnection(_ConnectionContext):
    def __init__(self, events: list[str]) -> None:
        self.events = events
        self.statements: list[tuple[str, dict | None]] = []

    async def run_sync(self, _sync_operation):
        return True

    async def execute(self, query, parameters=None):
        sql = query.text
        self.statements.append((sql, parameters))
        if sql.lstrip().upper().startswith("INSERT INTO LAW_RAG_LLAMAINDEX_INGESTION_RUNS"):
            self.events.append("insert-running")
            return _LifecycleResult("run-1")
        if "SELECT node_id" in sql:
            return []
        if "status = :status" in sql:
            self.events.append(parameters["status"])
            return None
        raise AssertionError(f"unexpected query: {sql}")


class _LifecycleEngine:
    def __init__(self, connection: _LifecycleConnection) -> None:
        self.connection = connection

    def connect(self):
        return self.connection

    def begin(self):
        return self.connection


class _Embedder:
    def get_text_embedding_batch(self, texts: list[str]) -> list[list[float]]:
        return [[0.1, 0.2] for _ in texts]


class _VectorStore:
    def __init__(self, events: list[str], error: Exception | None = None) -> None:
        self.events = events
        self.error = error

    def add(self, nodes: list[TextNode]) -> None:
        self.events.append("vector-write")
        if self.error is not None:
            raise self.error


async def _provisions(events: list[str]) -> list[dict]:
    events.append("retrieve")
    return [_record("a", "본문 A")]


@pytest.mark.asyncio
async def test_run_ingestion_records_running_then_completed_after_vector_write(monkeypatch):
    events: list[str] = []
    connection = _LifecycleConnection(events)
    engine = _LifecycleEngine(connection)
    monkeypatch.setattr(
        "law_rag_llamaindex.source.fetch_provisions", lambda _engine: _provisions(events)
    )

    result = await run_ingestion(engine, _VectorStore(events), _Embedder(), "law_rag_llamaindex")

    lifecycle_statements = [
        (sql, parameters)
        for sql, parameters in connection.statements
        if "law_rag_llamaindex_ingestion_runs" in sql
    ]
    assert len(lifecycle_statements) == 2
    assert events.index("insert-running") < events.index("retrieve")
    assert events.index("vector-write") < events.index("completed")
    assert "RETURNING id" in lifecycle_statements[0][0]
    assert lifecycle_statements[0][1] == {"status": "running"}
    assert "finished_at" in lifecycle_statements[1][0]
    assert "node_count" in lifecycle_statements[1][0]
    assert lifecycle_statements[1][1] == {"status": "completed", "node_count": 1, "run_id": "run-1"}
    assert result.embedded_count == 1


@pytest.mark.asyncio
async def test_run_ingestion_records_failed_and_reraises_original_error(monkeypatch):
    events: list[str] = []
    connection = _LifecycleConnection(events)
    engine = _LifecycleEngine(connection)
    monkeypatch.setattr(
        "law_rag_llamaindex.source.fetch_provisions", lambda _engine: _provisions(events)
    )
    original_error = RuntimeError("vector write failed")

    with pytest.raises(RuntimeError, match="vector write failed") as raised:
        await run_ingestion(
            engine,
            _VectorStore(events, error=original_error),
            _Embedder(),
            "law_rag_llamaindex",
        )

    lifecycle_statements = [
        (sql, parameters)
        for sql, parameters in connection.statements
        if "law_rag_llamaindex_ingestion_runs" in sql
    ]
    assert len(lifecycle_statements) == 2
    assert events.index("vector-write") < events.index("failed")
    assert "finished_at" in lifecycle_statements[1][0]
    assert lifecycle_statements[1][1] == {"status": "failed", "run_id": "run-1"}
    assert not any(
        parameters and parameters.get("status") == "completed"
        for _, parameters in lifecycle_statements
    )
    assert raised.value is original_error


@pytest.mark.asyncio
async def test_existing_hashes_distinguishes_missing_table_from_query_failure():
    missing_table_connection = _MissingTableConnection()
    missing_table_engine = cast(AsyncEngine, _Engine(missing_table_connection))

    assert await existing_hashes(missing_table_engine, "law_rag_llamaindex") == {}
    assert not missing_table_connection.execute_called

    failing_query_engine = cast(AsyncEngine, _Engine(_ExistingTableFailingQueryConnection()))
    with pytest.raises(OperationalError, match="connection lost"):
        await existing_hashes(failing_query_engine, "law_rag_llamaindex")


pytestmark_db = pytest.mark.skipif(
    not os.environ.get("DATABASE_URL"), reason="requires a live Postgres DATABASE_URL"
)


@pytestmark_db
@pytest.mark.asyncio
async def test_run_ingestion_skips_unchanged_rows_on_second_run():
    import asyncpg  # noqa: F401  (ensures driver present for direct pool tests if needed later)
    from sqlalchemy.ext.asyncio import create_async_engine

    from law_rag_llamaindex.config import Settings
    from law_rag_llamaindex.embedding import build_embedder
    from law_rag_llamaindex.ingest import run_ingestion
    from law_rag_llamaindex.store import build_vector_store

    settings = Settings()
    engine = create_async_engine(settings.database_url)
    vector_store = build_vector_store(settings)
    embedder = build_embedder(settings)
    try:
        first = await run_ingestion(engine, vector_store, embedder, settings.vector_table_name)
        second = await run_ingestion(engine, vector_store, embedder, settings.vector_table_name)
    finally:
        await engine.dispose()
    assert first.embedded_count >= 0
    assert second.embedded_count == 0
    assert second.skipped_count == second.total_provisions
