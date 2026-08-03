import json
from datetime import date
from types import SimpleNamespace
from uuid import uuid4

import httpx
import pytest
from openai import APITimeoutError
from sqlalchemy import text

import scripts.backfill_embeddings as backfill_module
from app.adapters.postgres_repository import PostgresLegalRepository
from app.domain.embedding_profiles import NVIDIA_NEMOTRON_512_PROFILE
from scripts.backfill_embeddings import (
    _HNSW_READY_SQL,
    CachedEmbedding,
    PendingProvision,
    _append_cache,
    _cache_batch_values,
    _cache_file_lock,
    _cache_pending,
    _database_state,
    _embed_with_retry,
    _generate_cache,
    _load_cache,
    _pending,
    _profile_gate_failure,
    _promote_embedding_profile,
    _read_cache,
    _reusable_cache_vectors,
    _source_passages,
    _verify_dense_search,
)


def _row(*, stored_sha256=None) -> dict:
    return {
        "provision_id": uuid4(),
        "document_title": "전기사업법",
        "path": "제7조/항①",
        "heading": "사업의 허가",
        "content": "전기사업을 하려는 자는 허가를 받아야 한다.",
        "stored_sha256": stored_sha256,
        "stored_dimensions": 512 if stored_sha256 is not None else None,
        "stored_norm": 1.0 if stored_sha256 is not None else None,
    }


def test_pending_uses_full_versioned_passage_hash() -> None:
    first = _row()
    pending, missing, stale = _pending([first])
    current = {
        **first,
        "stored_sha256": pending[0].source_text_sha256,
        "stored_dimensions": 512,
        "stored_norm": 1.0,
    }
    changed = {
        **first,
        "stored_sha256": "0" * 64,
        "stored_dimensions": 512,
        "stored_norm": 1.0,
        "content": "변경된 본문",
    }

    current_pending, current_missing, current_stale = _pending([current])
    changed_pending, changed_missing, changed_stale = _pending([changed])

    assert missing == 1 and stale == 0
    assert current_pending == [] and current_missing == current_stale == 0
    assert len(changed_pending) == 1 and changed_missing == 0 and changed_stale == 1


def test_pending_repairs_same_hash_vector_with_invalid_norm() -> None:
    row = _row(stored_sha256="placeholder")
    passage = _source_passages([row])[0]
    row["stored_sha256"] = passage.source_text_sha256
    row["stored_norm"] = 0.8

    pending, missing, stale = _pending([row])

    assert [item.provision_id for item in pending] == [row["provision_id"]]
    assert missing == 0
    assert stale == 1


@pytest.mark.asyncio
async def test_transient_embedding_failure_is_retried(monkeypatch) -> None:
    class Embedder:
        calls = 0

        async def embed(self, texts):
            self.calls += 1
            if self.calls == 1:
                raise APITimeoutError(request=httpx.Request("POST", "https://example.test"))
            return [[1.0, 0.0]]

    embedder = Embedder()

    async def no_sleep(_):
        return None

    monkeypatch.setattr(backfill_module.asyncio, "sleep", no_sleep)

    result = await _embed_with_retry(
        embedder,  # type: ignore[arg-type]
        ["본문"],
        max_retries=1,
        retry_base_seconds=0.01,
    )

    assert result == [[1.0, 0.0]]
    assert embedder.calls == 2


@pytest.mark.asyncio
async def test_repository_rejects_unknown_profile_before_database_access() -> None:
    repository = PostgresLegalRepository.__new__(PostgresLegalRepository)

    with pytest.raises(ValueError, match="unsupported embedding profile"):
        await repository.upsert_embeddings([(uuid4(), "0" * 64, [1.0])], "unknown", 512)


@pytest.mark.asyncio
async def test_repository_rejects_wrong_vector_dimensions_before_database_access() -> None:
    repository = PostgresLegalRepository.__new__(PostgresLegalRepository)

    with pytest.raises(ValueError, match="vector dimensions"):
        await repository.upsert_embeddings(
            [(uuid4(), "0" * 64, [1.0, 0.0])],
            NVIDIA_NEMOTRON_512_PROFILE.key,
            NVIDIA_NEMOTRON_512_PROFILE.stored_dimensions,
        )


class _RowsResult:
    def __init__(self, rows=None, *, scalar=True) -> None:
        self.rows = rows or []
        self.scalar = scalar

    def mappings(self):
        return self

    def all(self):
        return self.rows

    def scalar_one(self):
        return self.scalar


class _EmbeddingConnection:
    def __init__(self, provision_id, current_sha256) -> None:
        self.provision_id = provision_id
        self.current_sha256 = current_sha256
        self.statements: list[str] = []
        self.params: list[object] = []

    async def execute(self, statement, params=None):
        sql = str(statement)
        self.statements.append(sql)
        self.params.append(params)
        if "source_text_sha256" in sql and "FROM provisions" in sql:
            return _RowsResult(
                [
                    {
                        "provision_id": self.provision_id,
                        "source_text_sha256": self.current_sha256,
                    }
                ]
            )
        if "schema.corpus_search_ready_v1" in sql:
            return _RowsResult(scalar=True)
        return _RowsResult()


class _BeginContext:
    def __init__(self, connection) -> None:
        self.connection = connection

    async def __aenter__(self):
        return self.connection

    async def __aexit__(self, *_):
        return None


class _EmbeddingEngine:
    def __init__(self, connection) -> None:
        self.connection = connection

    def begin(self):
        return _BeginContext(self.connection)


@pytest.mark.asyncio
async def test_repository_upsert_embeddings_locks_and_rejects_stale_batch() -> None:
    provision_id = uuid4()
    connection = _EmbeddingConnection(provision_id, "1" * 64)
    repository = PostgresLegalRepository.__new__(PostgresLegalRepository)
    repository.engine = _EmbeddingEngine(connection)  # type: ignore[assignment]

    with pytest.raises(RuntimeError, match="source hash is stale"):
        await repository.upsert_embeddings(
            [(provision_id, "0" * 64, [1.0] + [0.0] * 511)],
            NVIDIA_NEMOTRON_512_PROFILE.key,
            NVIDIA_NEMOTRON_512_PROFILE.stored_dimensions,
        )

    assert "pg_advisory_xact_lock" in connection.statements[0]
    assert not any("INSERT INTO provision_embeddings" in sql for sql in connection.statements)


@pytest.mark.asyncio
async def test_repository_upsert_embeddings_commits_only_current_hash() -> None:
    provision_id = uuid4()
    source_sha256 = "1" * 64
    connection = _EmbeddingConnection(provision_id, source_sha256)
    repository = PostgresLegalRepository.__new__(PostgresLegalRepository)
    repository.engine = _EmbeddingEngine(connection)  # type: ignore[assignment]

    await repository.upsert_embeddings(
        [(provision_id, source_sha256, [1.0] + [0.0] * 511)],
        NVIDIA_NEMOTRON_512_PROFILE.key,
        NVIDIA_NEMOTRON_512_PROFILE.stored_dimensions,
    )

    assert "pg_advisory_xact_lock" in connection.statements[0]
    assert "source_record_state='available'" in connection.statements[1]
    assert "lifecycle_state IN ('active','scheduled')" in connection.statements[1]
    assert "parser_schema_version='3'" in connection.statements[1]
    assert "text_template_version='legal-provision-v1'" in connection.statements[1]
    assert "schema.corpus_search_ready_v1" in connection.statements[2]
    assert "SET active=false" in connection.statements[3]
    assert "INSERT INTO runtime_flags" in connection.statements[4]
    assert set(text(connection.statements[4])._bindparams) == {"key", "value"}
    assert json.loads(connection.params[4]["value"])["ready"] is False
    assert "INSERT INTO provision_embeddings" in connection.statements[5]


@pytest.mark.asyncio
async def test_runtime_postgres_repository_refuses_corpus_writes() -> None:
    repository = PostgresLegalRepository.__new__(PostgresLegalRepository)

    with pytest.raises(RuntimeError, match="runtime reader"):
        await repository.upsert_document(object())  # type: ignore[arg-type]


def test_cache_round_trip_keeps_last_record_and_no_source_text(tmp_path) -> None:
    cache = tmp_path / "vectors.jsonl"
    provision_id = uuid4()
    first = PendingProvision(provision_id, "비저장 원문", "0" * 64)
    changed = PendingProvision(provision_id, "변경된 비저장 원문", "1" * 64)
    vector = [1.0] + [0.0] * 511

    _append_cache(cache, [first], [vector])
    _append_cache(cache, [changed], [vector])
    records, line_count = _read_cache(cache)

    assert line_count == 2
    assert records[str(provision_id)].source_text_sha256 == "1" * 64
    assert records[str(provision_id)].embedding == vector
    assert "비저장 원문" not in cache.read_text(encoding="utf-8")


def test_cache_recovers_an_incomplete_final_json_line(tmp_path) -> None:
    cache = tmp_path / "vectors.jsonl"
    first = PendingProvision(uuid4(), "first", "1" * 64)
    second = PendingProvision(uuid4(), "second", "2" * 64)
    vector = [1.0] + [0.0] * 511
    _append_cache(cache, [first], [vector])
    with cache.open("ab") as stream:
        stream.write(b'{"profile_key":')

    records_before, line_count_before = _read_cache(cache)
    _append_cache(cache, [second], [vector])
    records_after, line_count_after = _read_cache(cache)

    assert set(records_before) == {str(first.provision_id)}
    assert line_count_before == 1
    assert set(records_after) == {str(first.provision_id), str(second.provision_id)}
    assert line_count_after == 2


def test_cache_file_lock_rejects_a_concurrent_process(tmp_path) -> None:
    cache = tmp_path / "vectors.jsonl"

    with _cache_file_lock(cache):
        with pytest.raises(RuntimeError, match="already in use"):
            with _cache_file_lock(cache):
                raise AssertionError("unreachable")


def test_cache_pending_distinguishes_missing_stale_and_current() -> None:
    missing = PendingProvision(uuid4(), "a", "0" * 64)
    stale = PendingProvision(uuid4(), "b", "1" * 64)
    current = PendingProvision(uuid4(), "c", "2" * 64)
    vector = [1.0] + [0.0] * 511
    records = {
        str(stale.provision_id): CachedEmbedding(str(stale.provision_id), "f" * 64, vector),
        str(current.provision_id): CachedEmbedding(
            str(current.provision_id), current.source_text_sha256, vector
        ),
    }

    pending, missing_count, stale_count = _cache_pending(
        [missing, stale, current], records
    )

    assert pending == [missing, stale]
    assert missing_count == 1
    assert stale_count == 1


def test_cache_reuses_same_profile_vector_when_only_provision_id_changed() -> None:
    old_id = uuid4()
    new_id = uuid4()
    source_sha256 = "1" * 64
    vector = [1.0] + [0.0] * 511
    pending = [PendingProvision(new_id, "same passage", source_sha256)]
    records = {
        str(old_id): CachedEmbedding(str(old_id), source_sha256, vector),
    }

    passages, vectors = _reusable_cache_vectors(pending, records)

    assert passages == pending
    assert vectors == [vector]


@pytest.mark.asyncio
async def test_generate_cache_id_only_migration_needs_no_nvidia_key(
    monkeypatch, tmp_path
) -> None:
    row = _row()
    current = _source_passages([row])[0]
    old = PendingProvision(uuid4(), current.text, current.source_text_sha256)
    cache = tmp_path / "vectors.jsonl"
    _append_cache(cache, [old], [[1.0] + [0.0] * 511])

    async def source_provisions(_repository):
        return [row]

    def unexpected_embedder(*_args, **_kwargs):
        raise AssertionError("NVIDIA embedder must not be created for hash reuse")

    monkeypatch.setattr(backfill_module, "_source_provisions", source_provisions)
    monkeypatch.setattr(backfill_module, "_embedder", unexpected_embedder)

    result = await _generate_cache(
        SimpleNamespace(
            cache=cache,
            batch_size=32,
            max_items=None,
            max_retries=0,
            retry_base_seconds=1.0,
        ),
        object(),  # type: ignore[arg-type]
        SimpleNamespace(nvidia_api_key=None),
    )

    assert result["generated_count"] == 0
    assert result["reused_count"] == 1
    assert result["state"]["complete"] is True


@pytest.mark.asyncio
async def test_database_state_interpolates_the_searchable_corpus_sql(monkeypatch) -> None:
    class Result:
        def mappings(self):
            return self

        def one(self):
            return {
                "db_revision": "0010",
                "hybrid_function_exists": False,
                "hnsw_ready": True,
                "profile_active": False,
                "corpus_search_ready": False,
                "corpus_search_capability": True,
                "stored_count": 0,
                "non_unit_count": 0,
            }

    class Connection:
        statement = ""

        async def execute(self, statement, _params=None):
            self.statement = str(statement)
            return Result()

    connection = Connection()

    class Engine:
        def connect(self):
            return _BeginContext(connection)

    async def no_provisions(_repository):
        return []

    monkeypatch.setattr(backfill_module, "_provisions", no_provisions)

    await _database_state(SimpleNamespace(engine=Engine()))  # type: ignore[arg-type]

    assert "{SEARCHABLE_DOCUMENT_VERSION_SQL}" not in connection.statement
    assert "source_record_state='available'" in connection.statement
    assert "parser_schema_version='3'" in connection.statement
    assert "corpus_search_ready" in connection.statement


def test_cache_batch_values_rejects_vector_for_an_old_source_hash() -> None:
    provision = PendingProvision(uuid4(), "현재 본문", "1" * 64)
    record = CachedEmbedding(
        str(provision.provision_id), "0" * 64, [1.0] + [0.0] * 511
    )

    with pytest.raises(RuntimeError, match="cache became stale"):
        _cache_batch_values([provision], {record.provision_id: record})


def test_profile_gate_requires_complete_current_unit_index() -> None:
    profile = NVIDIA_NEMOTRON_512_PROFILE
    state = {
        "provider": profile.provider,
        "model": profile.model,
        "native_dimensions": profile.native_dimensions,
        "stored_dimensions": profile.stored_dimensions,
        "document_input_type": profile.document_input_type,
        "query_input_type": profile.query_input_type,
        "truncation": profile.truncation,
        "normalization": profile.normalization,
        "text_template_version": profile.text_template_version,
        "profile_version": profile.profile_version,
        "provision_count": 10,
        "current_count": 10,
        "wrong_dimensions_count": 0,
        "non_unit_count": 0,
        "hnsw_ready": True,
    }

    assert _profile_gate_failure(state) is None
    assert _profile_gate_failure({**state, "current_count": 9}) is not None
    assert _profile_gate_failure({**state, "non_unit_count": 1}) is not None
    assert _profile_gate_failure({**state, "hnsw_ready": False}) is not None


def test_hnsw_gate_checks_schema_table_operator_expression_and_profile() -> None:
    assert "n.nspname='public'" in _HNSW_READY_SQL
    assert "c.relname='provision_embeddings_nemotron_512_hnsw'" in _HNSW_READY_SQL
    assert "to_regclass('public.provision_embeddings')" in _HNSW_READY_SQL
    assert "am.amname='hnsw'" in _HNSW_READY_SQL
    assert "vector_cosine_ops" in _HNSW_READY_SQL
    assert "format_type(index_column.atttypid,index_column.atttypmod)='vector(512)'" in (
        _HNSW_READY_SQL
    )
    assert "pg_get_expr(i.indexprs,i.indrelid)" in _HNSW_READY_SQL
    assert NVIDIA_NEMOTRON_512_PROFILE.key in _HNSW_READY_SQL


@pytest.mark.asyncio
async def test_failed_profile_promotion_commits_inactive_without_exposing_index() -> None:
    profile = NVIDIA_NEMOTRON_512_PROFILE
    gate_state = {
        "profile_active": False,
        "provider": profile.provider,
        "model": profile.model,
        "native_dimensions": profile.native_dimensions,
        "stored_dimensions": profile.stored_dimensions,
        "document_input_type": profile.document_input_type,
        "query_input_type": profile.query_input_type,
        "truncation": profile.truncation,
        "normalization": profile.normalization,
        "text_template_version": profile.text_template_version,
        "profile_version": profile.profile_version,
        "provision_count": 10,
        "current_count": 9,
        "wrong_dimensions_count": 0,
        "non_unit_count": 0,
        "hnsw_ready": True,
    }

    class GateResult(_RowsResult):
        def mappings(self):
            return self

        def one_or_none(self):
            return self.rows[0] if self.rows else None

    class Connection:
        def __init__(self) -> None:
            self.statements = []

        async def execute(self, statement, _params=None):
            sql = str(statement)
            self.statements.append(sql)
            if "SELECT ep.active profile_active" in sql:
                return GateResult([gate_state])
            if "schema.corpus_search_ready_v1" in sql:
                return GateResult(scalar=True)
            return GateResult()

    connection = Connection()

    class Repository:
        engine = _EmbeddingEngine(connection)

    with pytest.raises(RuntimeError, match="activation refused"):
        await _promote_embedding_profile(Repository())  # type: ignore[arg-type]

    assert "pg_advisory_xact_lock" in connection.statements[0]
    assert "pg_advisory_xact_lock" in connection.statements[1]
    assert "SET active=false" in connection.statements[2]
    assert any("INSERT INTO runtime_flags" in sql for sql in connection.statements)
    assert not any("SET active=true" in sql for sql in connection.statements)


@pytest.mark.asyncio
async def test_load_cache_writes_only_database_missing_or_stale_rows(monkeypatch, tmp_path) -> None:
    source_rows = [_row(), _row()]
    passages = _source_passages(source_rows)
    vector = [1.0] + [0.0] * 511
    records = {
        str(item.provision_id): CachedEmbedding(
            str(item.provision_id), item.source_text_sha256, vector
        )
        for item in passages
    }
    database_rows = [
        {
            **source_rows[0],
            "stored_sha256": passages[0].source_text_sha256,
            "stored_dimensions": 512,
            "stored_norm": 1.0,
        },
        {**source_rows[1], "stored_sha256": None},
    ]
    events: list[str] = []

    class ScalarResult:
        def scalar_one(self):
            return True

    class Connection:
        async def execute(self, _statement, _params=None):
            return ScalarResult()

    class Engine:
        def connect(self):
            return _BeginContext(Connection())

    class Repository:
        engine = Engine()

        def __init__(self) -> None:
            self.batches = []

        async def upsert_embeddings(self, values, profile_key, dimensions):
            self.batches.append((values, profile_key, dimensions))

    repository = Repository()

    async def source_provisions(_repository):
        return source_rows

    async def provisions(_repository):
        return database_rows

    async def deactivate(_repository):
        events.append("inactive")

    async def promote(_repository):
        events.append("active")
        return {}

    async def database_state(_repository):
        return {"profile_active": True, "corpus_search_ready": True}

    monkeypatch.setattr(backfill_module, "_source_provisions", source_provisions)
    monkeypatch.setattr(backfill_module, "_provisions", provisions)
    monkeypatch.setattr(backfill_module, "_deactivate_embedding_profile", deactivate)
    monkeypatch.setattr(backfill_module, "_promote_embedding_profile", promote)
    monkeypatch.setattr(backfill_module, "_database_state", database_state)
    monkeypatch.setattr(backfill_module, "_read_cache", lambda _path: (records, 2))

    result = await _load_cache(
        SimpleNamespace(cache=tmp_path / "cache.jsonl", batch_size=100),
        repository,  # type: ignore[arg-type]
    )

    assert result == {
        "loaded_count": 1,
        "state": {"profile_active": True, "corpus_search_ready": True},
    }
    assert events == ["inactive", "active"]
    assert len(repository.batches) == 1
    assert repository.batches[0][0][0][0] == passages[1].provision_id


def test_read_cache_rejects_wrong_vector_dimensions(tmp_path) -> None:
    cache = tmp_path / "invalid.jsonl"
    payload = {
        "profile_key": NVIDIA_NEMOTRON_512_PROFILE.key,
        "dimensions": NVIDIA_NEMOTRON_512_PROFILE.stored_dimensions,
        "provision_id": str(uuid4()),
        "source_text_sha256": "0" * 64,
        "embedding": [1.0],
    }
    cache.write_text(json.dumps(payload) + "\n", encoding="utf-8")

    with pytest.raises(ValueError, match="512 dimensions"):
        _read_cache(cache)


@pytest.mark.asyncio
async def test_verify_dense_search_uses_query_profile_without_printing_content(
    monkeypatch,
) -> None:
    async def database_state(_repository):
        return {
            "pending_count": 0,
            "hnsw_ready": True,
            "profile_active": True,
            "corpus_search_capability": True,
            "corpus_search_ready": True,
            "hybrid_function_exists": False,
        }

    class Embedder:
        async def embed(self, texts):
            assert texts == ["태양광 발전 정의"]
            return [[1.0] + [0.0] * 511]

    def embedder(_settings, *, input_type):
        assert input_type == NVIDIA_NEMOTRON_512_PROFILE.query_input_type
        return Embedder()

    class Repository:
        async def search_with_trace(self, query, as_of, limit, vector, profile_key):
            assert (query, as_of, limit) == ("태양광 발전 정의", date(2026, 8, 3), 3)
            assert len(vector) == 512
            assert profile_key == NVIDIA_NEMOTRON_512_PROFILE.key
            hit = SimpleNamespace(
                document_title="신에너지법",
                path="제2조",
                heading="정의",
                content="출력되면 안 되는 원문",
                score=0.8,
            )
            return [hit], SimpleNamespace(strategy="dense_only", candidate_count=1)

    monkeypatch.setattr(backfill_module, "_database_state", database_state)
    monkeypatch.setattr(backfill_module, "_embedder", embedder)
    arguments = SimpleNamespace(
        query=" 태양광 발전 정의 ", as_of=date(2026, 8, 3), limit=3
    )

    result = await _verify_dense_search(arguments, Repository(), object())

    assert result["retrieval_strategy"] == "dense_only"
    assert result["query_dimensions"] == 512
    assert result["profile_active"] is True
    assert result["corpus_search_ready"] is True
    assert result["results"][0]["document_title"] == "신에너지법"
    assert "content" not in result["results"][0]


@pytest.mark.asyncio
@pytest.mark.parametrize(("query", "limit"), [("  ", 3), ("질문", 0), ("질문", 21)])
async def test_verify_dense_search_rejects_invalid_arguments(query, limit) -> None:
    arguments = SimpleNamespace(query=query, as_of=date(2026, 8, 3), limit=limit)

    with pytest.raises(ValueError):
        await _verify_dense_search(arguments, object(), object())


@pytest.mark.asyncio
async def test_verify_dense_search_rejects_inactive_profile(monkeypatch) -> None:
    async def database_state(_repository):
        return {"pending_count": 0, "hnsw_ready": True, "profile_active": False}

    monkeypatch.setattr(backfill_module, "_database_state", database_state)

    with pytest.raises(RuntimeError, match="not ready"):
        await _verify_dense_search(
            SimpleNamespace(query="질문", as_of=date(2026, 8, 3), limit=3),
            object(),
            object(),
        )


@pytest.mark.asyncio
async def test_verify_dense_search_rejects_an_unready_corpus(monkeypatch) -> None:
    async def database_state(_repository):
        return {
            "pending_count": 0,
            "hnsw_ready": True,
            "profile_active": True,
            "corpus_search_capability": True,
            "corpus_search_ready": False,
        }

    monkeypatch.setattr(backfill_module, "_database_state", database_state)

    with pytest.raises(RuntimeError, match="not ready"):
        await _verify_dense_search(
            SimpleNamespace(query="질문", as_of=date(2026, 8, 3), limit=3),
            object(),
            object(),
        )
