import os
from typing import cast

import pytest
from llama_index.core.schema import TextNode
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncEngine

from law_rag_llamaindex.ingest import build_nodes, changed_provision_ids, existing_hashes
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
