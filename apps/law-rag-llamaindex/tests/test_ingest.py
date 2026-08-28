import os
from typing import cast

import pytest
from llama_index.core.schema import TextNode
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncEngine

from law_rag_llamaindex.generations import (
    GenerationCatalog,
    GenerationSource,
    provision_fingerprint,
)
from law_rag_llamaindex.ingest import (
    _async_database_url,
    _sync_database_url,
    build_nodes,
    changed_provision_ids,
    copy_generation_vectors,
    existing_hashes,
    main,
    run_generation_ingestion,
    run_generation_pipeline,
    run_ingestion,
    verify_generation_vectors,
)
from law_rag_llamaindex.passage import build_passage_text, compute_source_text_sha256


@pytest.fixture(autouse=True)
def _replace_physical_generation_verifier(monkeypatch):
    async def verifier(*args, **kwargs) -> None:
        return None

    monkeypatch.setattr("law_rag_llamaindex.ingest.verify_generation_vectors", verifier)

    def pipeline(provisions, embedder):
        nodes = build_nodes(provisions)
        embeddings = embedder.get_text_embedding_batch([node.text for node in nodes])
        for node, embedding in zip(nodes, embeddings, strict=True):
            node.embedding = embedding
        return nodes

    monkeypatch.setattr("law_rag_llamaindex.ingest.run_generation_pipeline", pipeline)


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


def test_generation_pipeline_computes_embeddings_without_vector_or_docstore(monkeypatch):
    observed: dict[str, object] = {}

    class Pipeline:
        def __init__(self, *, transformations):
            observed["transformations"] = transformations

        def run(self, *, nodes):
            observed["nodes"] = nodes
            for node in nodes:
                node.embedding = [0.1, 0.2]
            return nodes

    embedder = object()
    monkeypatch.setattr("law_rag_llamaindex.ingest.IngestionPipeline", Pipeline)

    nodes = run_generation_pipeline([_record("a", "본문 A")], embedder)

    assert observed["transformations"] == [embedder]
    assert len(nodes) == 1
    assert nodes[0].embedding == [0.1, 0.2]


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


class _CopyResult:
    rowcount = 2


class _CopyConnection(_ConnectionContext):
    def __init__(self) -> None:
        self.statement = None
        self.parameters = None

    async def execute(self, statement, parameters):
        self.statement = statement
        self.parameters = parameters
        return _CopyResult()


class _CopyEngine:
    def __init__(self, connection: _CopyConnection) -> None:
        self.connection = connection

    def begin(self):
        return self.connection


class _VerificationResult:
    def __init__(self, row: dict[str, int]) -> None:
        self.row = row

    def mappings(self):
        return self

    def one(self):
        return self.row


class _VerificationConnection(_ConnectionContext):
    def __init__(self, row: dict[str, int]) -> None:
        self.row = row
        self.statement = None

    async def execute(self, statement):
        self.statement = statement
        return _VerificationResult(self.row)


class _VerificationEngine:
    def __init__(self, connection: _VerificationConnection) -> None:
        self.connection = connection

    def connect(self):
        return self.connection


class _LifecycleResult:
    def __init__(self, run_id: str) -> None:
        self._run_id = run_id

    def scalar_one(self) -> str:
        return self._run_id

    def __iter__(self):
        return iter(())


class _LifecycleConnection(_ConnectionContext):
    def __init__(self, events: list[str], *, failed_update_error: Exception | None = None) -> None:
        self.events = events
        self.statements: list[tuple[str, dict | None]] = []
        self.failed_update_error = failed_update_error

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
            if parameters["status"] == "failed" and self.failed_update_error is not None:
                raise self.failed_update_error
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


class _GenerationRepository:
    def __init__(self, events: list[str]) -> None:
        self.events = events
        self.catalog = GenerationCatalog()

    async def start(self, source_fingerprint: str, transform_fingerprint: str):
        self.events.append("generation-start")
        return self.catalog.start(source_fingerprint, transform_fingerprint)

    async def verify(self, generation_id, *, source_count: int, node_count: int) -> None:
        self.events.append("generation-verify")
        self.catalog.verify(generation_id, source_count=source_count, node_count=node_count)

    async def record_sources(self, generation_id, sources) -> None:
        self.events.append("generation-record-sources")
        assert [source["provision_id"] for source in sources] == ["a"]

    async def active(self):
        return self.catalog.active()

    async def sources(self, generation_id):
        return []

    async def publish(self, generation_id) -> None:
        self.events.append("generation-publish")
        self.catalog.publish(generation_id)

    async def fail(self, generation_id, failure_code: str) -> None:
        self.events.append(f"generation-fail:{failure_code}")
        self.catalog.fail(generation_id, failure_code)


@pytest.mark.asyncio
async def test_run_generation_ingestion_publishes_only_after_vector_write(monkeypatch):
    events: list[str] = []
    repository = _GenerationRepository(events)
    vector_store = _VectorStore(events)
    monkeypatch.setattr(
        "law_rag_llamaindex.source.fetch_provisions", lambda _engine: _provisions(events)
    )

    result = await run_generation_ingestion(
        object(),
        repository,
        lambda _generation: vector_store,
        _Embedder(),
        transform_fingerprint="a" * 64,
    )

    assert result.total_provisions == 1
    assert result.embedded_count == 1
    assert events.index("generation-start") < events.index("vector-write")
    assert events.index("vector-write") < events.index("generation-verify")
    assert events.index("vector-write") < events.index("generation-record-sources")
    assert events.index("generation-record-sources") < events.index("generation-verify")
    assert events.index("generation-verify") < events.index("generation-publish")
    assert repository.catalog.active() is not None


@pytest.mark.asyncio
async def test_run_generation_ingestion_marks_candidate_failed_without_active_pointer(monkeypatch):
    events: list[str] = []
    repository = _GenerationRepository(events)
    vector_store = _VectorStore(events, error=RuntimeError("vector write failed"))
    monkeypatch.setattr(
        "law_rag_llamaindex.source.fetch_provisions", lambda _engine: _provisions(events)
    )

    with pytest.raises(RuntimeError, match="vector write failed"):
        await run_generation_ingestion(
            object(),
            repository,
            lambda _generation: vector_store,
            _Embedder(),
            transform_fingerprint="a" * 64,
        )

    assert "generation-publish" not in events
    assert "generation-fail:vector_write_failed" in events
    assert repository.catalog.active() is None


@pytest.mark.asyncio
async def test_run_generation_ingestion_copies_unchanged_vectors_from_active_generation(
    monkeypatch,
):
    events: list[str] = []

    class RepositoryWithActiveSource(_GenerationRepository):
        def __init__(self, events: list[str]) -> None:
            super().__init__(events)
            active = self.catalog.start("old-source", "a" * 64)
            self.catalog.verify(active.id, source_count=1, node_count=1)
            self.catalog.publish(active.id)
            self.active_generation = active
            self.active_source = GenerationSource(
                provision_id="a", source_fingerprint="", node_count=1
            )

        async def sources(self, generation_id):
            return [
                GenerationSource(
                    provision_id="a",
                    source_fingerprint=self.active_source.source_fingerprint,
                    node_count=1,
                )
            ]

    repository = RepositoryWithActiveSource(events)
    provision = _record("a", "본문 A")
    repository.active_source = GenerationSource(
        provision_id="a",
        source_fingerprint=provision_fingerprint(provision),
        node_count=1,
    )
    copied: dict[str, object] = {}

    async def copy_vectors(engine, source_table, target_table, node_ids):
        copied.update(source_table=source_table, target_table=target_table, node_ids=node_ids)
        return len(node_ids)

    monkeypatch.setattr(
        "law_rag_llamaindex.source.fetch_provisions",
        lambda _engine: _single_provision(events, provision),
    )
    monkeypatch.setattr("law_rag_llamaindex.ingest.copy_generation_vectors", copy_vectors)

    result = await run_generation_ingestion(
        object(),
        repository,
        lambda _generation: _VectorStore(events),
        _Embedder(),
        transform_fingerprint="a" * 64,
    )

    assert result.embedded_count == 0
    assert result.skipped_count == 1
    assert copied["source_table"] == repository.active_generation.table_name
    assert copied["node_ids"] == ["a"]
    assert repository.catalog.active().node_count == 1


@pytest.mark.asyncio
async def test_run_generation_ingestion_reembeds_when_transform_changes(monkeypatch):
    events: list[str] = []

    class RepositoryWithDifferentTransform(_GenerationRepository):
        def __init__(self, events: list[str]) -> None:
            super().__init__(events)
            active = self.catalog.start("old-source", "b" * 64)
            self.catalog.verify(active.id, source_count=1, node_count=1)
            self.catalog.publish(active.id)

    repository = RepositoryWithDifferentTransform(events)

    async def fail_copy(*args, **kwargs):
        raise AssertionError("a transform change must force re-embedding")

    monkeypatch.setattr(
        "law_rag_llamaindex.source.fetch_provisions", lambda _engine: _provisions(events)
    )
    monkeypatch.setattr("law_rag_llamaindex.ingest.copy_generation_vectors", fail_copy)

    result = await run_generation_ingestion(
        object(),
        repository,
        lambda _generation: _VectorStore(events),
        _Embedder(),
        transform_fingerprint="a" * 64,
    )

    assert result.embedded_count == 1
    assert result.skipped_count == 0
    assert "vector-write" in events


@pytest.mark.asyncio
async def test_run_generation_ingestion_rejects_partial_vector_copy(monkeypatch):
    events: list[str] = []

    class RepositoryWithActiveSource(_GenerationRepository):
        def __init__(self, events: list[str]) -> None:
            super().__init__(events)
            active = self.catalog.start("old-source", "a" * 64)
            self.catalog.verify(active.id, source_count=1, node_count=1)
            self.catalog.publish(active.id)
            self.active_generation = active

        async def sources(self, generation_id):
            return [
                GenerationSource(
                    provision_id="a",
                    source_fingerprint=provision_fingerprint(provision),
                    node_count=1,
                )
            ]

    provision = _record("a", "본문 A")
    repository = RepositoryWithActiveSource(events)

    async def partial_copy(*args, **kwargs):
        return 0

    monkeypatch.setattr(
        "law_rag_llamaindex.source.fetch_provisions",
        lambda _engine: _single_provision(events, provision),
    )
    monkeypatch.setattr("law_rag_llamaindex.ingest.copy_generation_vectors", partial_copy)

    with pytest.raises(ValueError, match="copied vector count"):
        await run_generation_ingestion(
            object(),
            repository,
            lambda _generation: _VectorStore(events),
            _Embedder(),
            transform_fingerprint="a" * 64,
        )

    assert "generation-fail:vector_copy_failed" in events


async def _provisions(events: list[str]) -> list[dict]:
    events.append("retrieve")
    return [_record("a", "본문 A")]


async def _single_provision(events: list[str], provision: dict) -> list[dict]:
    events.append("retrieve")
    return [provision]


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
async def test_run_ingestion_preserves_original_error_when_failed_update_fails(monkeypatch):
    events: list[str] = []
    connection = _LifecycleConnection(
        events, failed_update_error=RuntimeError("failed marker write failed")
    )
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

    assert events.index("vector-write") < events.index("failed")
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


@pytest.mark.asyncio
async def test_copy_generation_vectors_uses_allowlisted_tables_and_bound_node_ids():
    connection = _CopyConnection()
    source = "law_rag_li_12345678123456781234567812345678"
    target = "law_rag_li_87654321876543218765432187654321"

    copied = await copy_generation_vectors(_CopyEngine(connection), source, target, ["a", "b"])

    assert copied == 2
    assert f'INSERT INTO "data_{target}"' in connection.statement.text
    assert f'FROM "data_{source}"' in connection.statement.text
    assert connection.parameters == {"node_ids": ["a", "b"]}
    with pytest.raises(ValueError, match="allowlisted"):
        await copy_generation_vectors(_CopyEngine(connection), "untrusted", target, ["a"])


@pytest.mark.asyncio
async def test_verify_generation_vectors_rejects_incomplete_physical_generation():
    generation = GenerationCatalog().start("a" * 64, "b" * 64)
    connection = _VerificationConnection(
        {
            "node_count": 1,
            "distinct_node_count": 1,
            "source_count": 1,
            "invalid_metadata_count": 0,
        }
    )

    await verify_generation_vectors(
        _VerificationEngine(connection), generation, source_count=1, node_count=1
    )
    assert "count(DISTINCT node_id)" in connection.statement.text
    with pytest.raises(ValueError, match="source coverage"):
        await verify_generation_vectors(
            _VerificationEngine(
                _VerificationConnection(
                    {
                        "node_count": 1,
                        "distinct_node_count": 1,
                        "source_count": 0,
                        "invalid_metadata_count": 0,
                    }
                )
            ),
            generation,
            source_count=1,
            node_count=1,
        )


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


def test_async_database_url_adds_asyncpg_driver_to_plain_postgresql_url():
    assert (
        _async_database_url("postgresql://user:pass@host:5432/db")
        == "postgresql+asyncpg://user:pass@host:5432/db"
    )


def test_async_database_url_leaves_asyncpg_url_unchanged():
    url = "postgresql+asyncpg://user:pass@host:5432/db"
    assert _async_database_url(url) == url


def test_sync_database_url_uses_psycopg_for_plain_or_asyncpg_urls():
    assert (
        _sync_database_url("postgresql://user:pass@host:5432/db")
        == "postgresql+psycopg://user:pass@host:5432/db"
    )
    assert (
        _sync_database_url("postgresql+asyncpg://user:pass@host:5432/db")
        == "postgresql+psycopg://user:pass@host:5432/db"
    )


@pytest.mark.asyncio
async def test_main_raises_without_database_url(monkeypatch):
    from law_rag_llamaindex.config import Settings

    monkeypatch.setattr(
        "law_rag_llamaindex.config.get_settings",
        lambda: Settings(_env_file=None, database_url=None, nvidia_api_key="key"),
    )
    with pytest.raises(SystemExit, match="DATABASE_URL"):
        await main()


@pytest.mark.asyncio
async def test_main_raises_without_nvidia_api_key(monkeypatch):
    from law_rag_llamaindex.config import Settings

    monkeypatch.setattr(
        "law_rag_llamaindex.config.get_settings",
        lambda: Settings(
            _env_file=None, database_url="postgresql+asyncpg://u:p@h:5432/d", nvidia_api_key=None
        ),
    )
    with pytest.raises(SystemExit, match="NVIDIA_API_KEY"):
        await main()
