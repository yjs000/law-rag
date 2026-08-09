import json
from datetime import date
from uuid import uuid4

import pytest
from law_rag_core.parsers.law_json import parse_legal_document
from law_rag_core.persistence import CORPUS_SEARCH_READY_FLAG_KEY

from app.adapters.memory_repository import MemoryLegalRepository
from app.adapters.postgres_repository import PostgresLegalRepository
from app.domain.catalog import SourceKind
from app.domain.embedding_profiles import NVIDIA_NEMOTRON_512_PROFILE
from app.domain.entities import ProvisionRecord
from app.domain.errors import CorpusSearchUnavailableError
from app.domain.search_queries import prepare_search_query


class _MappingsResult:
    def __init__(self, rows: list[dict]) -> None:
        self._rows = rows

    def mappings(self):
        return self

    def all(self):
        return self._rows

    def first(self):
        return self._rows[0] if self._rows else None


class _ScalarResult:
    def __init__(self, value: object) -> None:
        self._value = value

    def scalar_one(self):
        return self._value


class _FakeConnection:
    def __init__(
        self,
        rows_by_query: dict[str, list[dict]],
        *,
        search_ready: bool = True,
        explain_plan: object | None = None,
        temporal_row: dict[str, object] | None = None,
    ) -> None:
        self.rows_by_query = rows_by_query
        self.search_ready = search_ready
        self.explain_plan = explain_plan
        self.temporal_row = temporal_row
        self.readiness_checks = 0
        self.calls: list[dict] = []
        self.statements: list[str] = []
        self.executed_sql: list[str] = []
        self.temporal_calls: list[dict] = []
        self.temporal_statements: list[str] = []
        self.execution_order: list[str] = []

    async def execute(self, statement, params: dict | None = None):
        sql = str(statement)
        self.executed_sql.append(sql)
        if "pg_advisory_xact_lock_shared" in sql:
            raise AssertionError("production readers must not take a shared advisory lock")
        if "corpus_search_readiness_check" in sql:
            self.readiness_checks += 1
            self.execution_order.append("readiness")
            return _MappingsResult(
                [
                    {
                        "ready": self.search_ready,
                        "reason": None if self.search_ready else "embedding_backfill_started",
                    }
                ]
            )
        if "corpus_temporal_population" in sql:
            assert isinstance(params, dict)
            self.readiness_checks += 1
            self.temporal_calls.append(params)
            self.temporal_statements.append(sql)
            self.execution_order.append("temporal_state")
            population = self.temporal_row or {
                "supported_from": date(1900, 1, 1),
                "eligible_provision_count": 1,
                "fingerprint_sha256": "a" * 64,
            }
            return _MappingsResult(
                [
                    {
                        "ready": self.search_ready,
                        "reason": (None if self.search_ready else "embedding_backfill_started"),
                        **population,
                    }
                ]
            )
        assert isinstance(params, dict)
        self.calls.append(params)
        self.statements.append(sql)
        self.execution_order.append("retrieval")
        if sql.startswith("EXPLAIN "):
            return _ScalarResult(self.explain_plan)
        key = "__dense__" if "embedding" in params else params.get("query", "__direct__")
        return _MappingsResult(self.rows_by_query.get(key, []))


class _ConnectionContext:
    def __init__(self, connection: _FakeConnection) -> None:
        self.connection = connection

    async def __aenter__(self):
        return self.connection

    async def __aexit__(self, *_):
        return None


class _FakeEngine:
    def __init__(self, connection: _FakeConnection) -> None:
        self.connection = connection

    def connect(self):
        return _ConnectionContext(self.connection)


def _row(
    title: str,
    content: str,
    *,
    document_id=None,
    path: str = "제1조",
    score: float = 1.0,
) -> dict:
    return {
        "provision_id": uuid4(),
        "document_id": document_id or uuid4(),
        "document_title": title,
        "source_kind": SourceKind.LAW.value,
        "version_label": "MST 1",
        "effective_from": date(2020, 1, 1),
        "effective_to": None,
        "path": path,
        "heading": None,
        "content": content,
        "source_url": "https://open.law.go.kr/mock",
        "score": score,
    }


def _document(title: str, source_id: str, content: str):
    body = json.dumps(
        {
            "법령": {
                "기본정보": {
                    "법령명_한글": title,
                    "법령ID": source_id,
                    "법령일련번호": source_id,
                    "공포일자": "20200101",
                    "시행일자": "20200101",
                    "소관부처": "산업통상자원부",
                },
                "조문": {"조문단위": [{"조문번호": "1", "조문내용": content}]},
            }
        },
        ensure_ascii=False,
    )
    return parse_legal_document(
        body,
        expected_title=title,
        source_kind=SourceKind.LAW,
        source_url="https://open.law.go.kr/mock",
    )


@pytest.mark.asyncio
async def test_all_terms_stage_stops_on_strict_match() -> None:
    repository = MemoryLegalRepository()
    await repository.upsert_document(
        _document("전기사업법", "strict", "제1조 전기사업 허가 신청 서류를 정한다.")
    )

    hits, trace = await repository.search_with_trace("전기사업 허가 서류", date(2026, 7, 18), 10)

    assert hits
    assert [stage.stage for stage in trace.stages] == ["all_terms"]
    assert trace.stages[0].accepted_candidate_count == 1
    assert trace.total_duration_ms >= 0


@pytest.mark.asyncio
async def test_memory_natural_search_keeps_one_leaf_per_article() -> None:
    repository = MemoryLegalRepository()
    document = _document("전기사업법", "dedup", "제1조 전기사업 허가 서류")
    document.provisions.append(
        ProvisionRecord(
            id=uuid4(),
            path="제1조/항①",
            heading=None,
            content="① 전기사업 허가 서류",
            parent_path="제1조",
            ordinal=1,
        )
    )
    await repository.upsert_document(document)

    hits, _ = await repository.search_with_trace("전기사업 허가 서류", date(2026, 7, 18), 10)

    assert len(hits) == 1
    assert hits[0].path.startswith("제1조")


@pytest.mark.asyncio
async def test_search_hit_carries_the_document_law_type_code() -> None:
    repository = MemoryLegalRepository()
    document = _document("전기사업법", "law-type", "제1조 전기사업 허가 서류")
    document.law_type_code = "01"
    await repository.upsert_document(document)

    hits, _ = await repository.search_with_trace("전기사업 허가 서류", date(2026, 7, 18), 10)

    assert hits
    assert hits[0].law_type_code == "01"


@pytest.mark.asyncio
async def test_memory_temporal_state_uses_earliest_collected_date_and_content_identity() -> None:
    repository = MemoryLegalRepository()
    document = _document("전기사업법", "temporal", "제1조 전기사업 허가 기준")
    document.effective_from = date(2020, 1, 1)
    await repository.upsert_document(document)

    first = await repository.corpus_temporal_state(date(2026, 8, 3))
    second = await repository.corpus_temporal_state(date(2026, 8, 4))

    assert first.ready is True
    assert first.supported_as_of_from == date(2020, 1, 1)
    assert first.supported_as_of_through == date(2026, 8, 3)
    assert first.eligible_provision_count == 1
    assert first.corpus_snapshot_id == second.corpus_snapshot_id


@pytest.mark.asyncio
async def test_memory_temporal_state_excludes_old_parser_and_empty_versions() -> None:
    repository = MemoryLegalRepository()
    current = _document("전기사업법", "current-parser", "현재 parser 본문")
    current.effective_from = date(2020, 1, 1)
    old_parser = _document("전기사업법", "old-parser", "구 parser 본문")
    old_parser.effective_from = date(1990, 1, 1)
    old_parser.parser_schema_version = "2"
    empty = _document("전기사업법", "empty-version", "비워질 본문")
    empty.effective_from = date(1980, 1, 1)
    empty.provisions = []
    await repository.upsert_document(current)
    await repository.upsert_document(old_parser)
    await repository.upsert_document(empty)

    state = await repository.corpus_temporal_state(date(2026, 8, 4))

    assert state.ready is True
    assert state.supported_as_of_from == date(2020, 1, 1)
    assert state.eligible_provision_count == 1


@pytest.mark.asyncio
async def test_empty_memory_corpus_is_temporally_unready() -> None:
    state = await MemoryLegalRepository().corpus_temporal_state(date(2026, 8, 4))

    assert state.ready is False
    assert state.reason == "no_currently_effective_corpus"
    assert state.corpus_snapshot_id is None


@pytest.mark.asyncio
async def test_minimum_two_candidates_are_gated_by_required_anchor() -> None:
    repository = MemoryLegalRepository()
    await repository.upsert_document(
        _document("전기사업법", "anchor", "제1조 전기사업 허가 기준을 정한다.")
    )

    hits, trace = await repository.search_with_trace("전기사업 허가 서류", date(2026, 7, 18), 10)

    assert hits
    assert [stage.stage for stage in trace.stages] == [
        "all_terms",
        "minimum_two",
        "anchor_required",
    ]
    assert trace.stages[1].status == "candidate_pool"
    assert trace.stages[2].status == "matched"
    assert trace.anchor_term == "전기사업"


@pytest.mark.asyncio
async def test_missing_anchor_finishes_with_insufficient_evidence() -> None:
    repository = MemoryLegalRepository()
    await repository.upsert_document(
        _document("가상 규정", "noise", "제1조 허가 신청 서류를 정한다.")
    )

    hits, trace = await repository.search_with_trace("전기사업 허가 서류", date(2026, 7, 18), 10)

    assert hits == []
    assert [stage.stage for stage in trace.stages] == [
        "all_terms",
        "minimum_two",
        "anchor_required",
        "insufficient_evidence",
    ]
    assert trace.stages[1].accepted_candidate_count == 1
    assert trace.stages[2].accepted_candidate_count == 0
    assert trace.stages[3].status == "insufficient_evidence"
    assert trace.total_duration_ms >= sum(stage.duration_ms for stage in trace.stages)


@pytest.mark.asyncio
async def test_postgres_dense_candidates_do_not_execute_or_fuse_keyword_search() -> None:
    document_id = uuid4()
    connection = _FakeConnection(
        {
            "__dense__": [
                _row(
                    "전기사업법",
                    "전기사업을 하려는 자는 장관의 허가를 받아야 한다.",
                    document_id=document_id,
                    path="제7조/항①",
                    score=0.91,
                ),
                _row(
                    "전기사업법",
                    "같은 조의 다른 항",
                    document_id=document_id,
                    path="제7조/항②",
                    score=0.89,
                ),
                _row(
                    "전기사업법",
                    "결격사유",
                    document_id=document_id,
                    path="제8조",
                    score=0.75,
                ),
            ]
        }
    )
    repository = PostgresLegalRepository.__new__(PostgresLegalRepository)
    repository.engine = _FakeEngine(connection)  # type: ignore[assignment]

    hits, trace = await repository.search_with_trace(
        "전기사업 허가",
        date(2026, 7, 18),
        10,
        [0.1, 0.2],
        NVIDIA_NEMOTRON_512_PROFILE.key,
    )

    assert [hit.path for hit in hits] == ["제7조/항①", "제8조"]
    assert [stage.stage for stage in trace.stages] == ["dense_retrieval"]
    assert trace.strategy == "dense_only"
    assert len(connection.calls) == 1
    assert connection.calls[0]["embedding"] == "[0.1, 0.2]"
    assert "hybrid_search" not in connection.statements[0]
    assert "pgroonga" not in connection.statements[0].casefold()
    assert "ep.active IS TRUE" in connection.statements[0]
    assert "e.source_text_sha256=encode(digest" in connection.statements[0]
    assert "source_record_state='available'" in connection.statements[0]
    assert "lifecycle_state IN ('active','scheduled')" in connection.statements[0]
    assert "parser_schema_version='3'" in connection.statements[0]
    assert "corpus.search_ready" in connection.statements[0]
    assert "schema.corpus_search_ready_v1" in connection.statements[0]
    assert "value->>'ready'='true'" in connection.statements[0]
    assert "WITH exact_eligible_distances AS MATERIALIZED" in connection.statements[0]
    assert "ORDER BY distance,ordinal" in connection.statements[0]
    assert "ORDER BY e.embedding::vector(512)" not in connection.statements[0]
    assert connection.readiness_checks == 1
    assert connection.execution_order[:2] == ["readiness", "retrieval"]
    assert all("pg_advisory_xact_lock_shared" not in sql for sql in connection.executed_sql)


@pytest.mark.asyncio
async def test_postgres_dense_zero_falls_back_to_separate_keyword_search() -> None:
    query = "전기사업 허가 서류"
    prepared = prepare_search_query(query)
    connection = _FakeConnection(
        {
            "__dense__": [],
            prepared.strict_query: [_row("가상 규정", "벡터로만 유사한 내용")],
            prepared.minimum_match_query: [_row("가상 규정", "허가 서류")],
            prepared.anchored_query: [_row("전기사업법", "전기사업 허가 기준")],
        }
    )
    repository = PostgresLegalRepository.__new__(PostgresLegalRepository)
    repository.engine = _FakeEngine(connection)  # type: ignore[assignment]

    hits, trace = await repository.search_with_trace(
        query,
        date(2026, 7, 18),
        10,
        [0.1, 0.2],
        NVIDIA_NEMOTRON_512_PROFILE.key,
    )

    assert [hit.document_title for hit in hits] == ["전기사업법"]
    assert [stage.stage for stage in trace.stages] == [
        "dense_retrieval",
        "all_terms",
        "minimum_two",
        "anchor_required",
    ]
    assert trace.stages[0].raw_candidate_count == 0
    assert trace.stages[1].raw_candidate_count == 1
    assert trace.stages[1].accepted_candidate_count == 0
    assert trace.stages[2].accepted_candidate_count == 1
    assert trace.stages[3].accepted_candidate_count == 1
    assert trace.strategy == "dense_then_keyword_fallback"
    assert len(connection.calls) == 4
    assert "embedding" in connection.calls[0]
    assert all("embedding" not in call for call in connection.calls[1:])
    assert all("hybrid_search" not in statement for statement in connection.statements)
    assert all(
        "source_record_state='available'" in statement
        and "lifecycle_state IN ('active','scheduled')" in statement
        and "parser_schema_version='3'" in statement
        and "corpus.search_ready" in statement
        for statement in connection.statements
    )


@pytest.mark.asyncio
async def test_experiment_dense_provision_path_has_no_grouping_or_keyword_fallback() -> None:
    document_id = uuid4()
    rows = [
        _row(
            "전기사업법",
            "허가 직접 근거",
            document_id=document_id,
            path="제7조/항①",
            score=0.91,
        ),
        _row(
            "전기사업법",
            "같은 조의 별도 근거",
            document_id=document_id,
            path="제7조/항②",
            score=0.90,
        ),
    ]
    connection = _FakeConnection({"__dense__": rows})
    repository = PostgresLegalRepository.__new__(PostgresLegalRepository)
    embedding = [1.0, *([0.0] * 511)]

    hits = await repository.search_dense_provisions_on_connection(
        connection,  # type: ignore[arg-type]
        date(2026, 7, 18),
        11,
        embedding,
        NVIDIA_NEMOTRON_512_PROFILE.key,
    )

    assert [hit.path for hit in hits] == ["제7조/항①", "제7조/항②"]
    assert connection.readiness_checks == 1
    assert len(connection.calls) == 1
    assert "pgroonga" not in connection.statements[0].casefold()
    assert "WITH exact_eligible_distances AS MATERIALIZED" in connection.statements[0]
    assert "ORDER BY distance,provision_id" in connection.statements[0]
    assert "ORDER BY e.embedding::vector(512)" not in connection.statements[0]
    assert "e.profile_key=:embedding_profile_key" in connection.statements[0]
    assert "e.dimensions=512" in connection.statements[0]
    assert "ep.active IS TRUE" in connection.statements[0]
    assert "e.source_text_sha256=encode(digest" in connection.statements[0]


@pytest.mark.asyncio
async def test_experiment_dense_provision_path_returns_empty_without_keyword_fallback() -> None:
    connection = _FakeConnection({"__dense__": []})
    repository = PostgresLegalRepository.__new__(PostgresLegalRepository)

    hits = await repository.search_dense_provisions_on_connection(
        connection,  # type: ignore[arg-type]
        date(2026, 7, 18),
        11,
        [1.0, *([0.0] * 511)],
        NVIDIA_NEMOTRON_512_PROFILE.key,
    )

    assert hits == []
    assert len(connection.calls) == 1


@pytest.mark.asyncio
async def test_experiment_dense_explain_wraps_the_exact_search_statement() -> None:
    plan = [{"Plan": {"Node Type": "CTE Scan", "CTE Name": "exact_eligible_distances"}}]
    connection = _FakeConnection({"__dense__": []}, explain_plan=plan)
    repository = PostgresLegalRepository.__new__(PostgresLegalRepository)
    embedding = [1.0, *([0.0] * 511)]

    await repository.search_dense_provisions_on_connection(
        connection,  # type: ignore[arg-type]
        date(2026, 7, 18),
        11,
        embedding,
        NVIDIA_NEMOTRON_512_PROFILE.key,
    )
    returned_plan = await repository.explain_dense_provisions_on_connection(
        connection,  # type: ignore[arg-type]
        date(2026, 7, 18),
        11,
        embedding,
        NVIDIA_NEMOTRON_512_PROFILE.key,
    )

    search_sql, explain_sql = connection.statements
    assert returned_plan == plan
    assert explain_sql.startswith("EXPLAIN (FORMAT JSON, COSTS OFF, SETTINGS TRUE)\n")
    assert (
        explain_sql.removeprefix("EXPLAIN (FORMAT JSON, COSTS OFF, SETTINGS TRUE)\n") == search_sql
    )
    assert search_sql.endswith("LIMIT :limit")
    assert "WITH exact_eligible_distances AS MATERIALIZED" in search_sql
    assert "ORDER BY distance,provision_id" in search_sql
    assert "ORDER BY e.embedding::vector(512)" not in search_sql
    assert connection.calls[0] == connection.calls[1]
    assert connection.readiness_checks == 2


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("method_name", "profile_key"),
    [
        ("search_dense_provisions_on_connection", "unsupported"),
        ("explain_dense_provisions_on_connection", "unsupported"),
    ],
)
async def test_experiment_dense_search_and_explain_share_request_validation(
    method_name: str,
    profile_key: str,
) -> None:
    connection = _FakeConnection({"__dense__": []})
    repository = PostgresLegalRepository.__new__(PostgresLegalRepository)

    with pytest.raises(ValueError, match="unsupported embedding profile"):
        await getattr(repository, method_name)(
            connection,
            date(2026, 7, 18),
            11,
            [1.0, *([0.0] * 511)],
            profile_key,
        )

    assert connection.readiness_checks == 0
    assert connection.calls == []


@pytest.mark.asyncio
async def test_experiment_dense_explain_checks_corpus_readiness_before_explain() -> None:
    connection = _FakeConnection({"__dense__": []}, search_ready=False)
    repository = PostgresLegalRepository.__new__(PostgresLegalRepository)

    with pytest.raises(CorpusSearchUnavailableError, match="embedding_backfill_started"):
        await repository.explain_dense_provisions_on_connection(
            connection,  # type: ignore[arg-type]
            date(2026, 7, 18),
            11,
            [1.0, *([0.0] * 511)],
            NVIDIA_NEMOTRON_512_PROFILE.key,
        )

    assert connection.readiness_checks == 1
    assert connection.calls == []


@pytest.mark.asyncio
async def test_postgres_direct_path_and_provision_reads_exclude_unavailable_versions() -> None:
    row = _row("전기사업법", "허가", path="제1조")
    direct_connection = _FakeConnection({"__direct__": [row]})
    repository = PostgresLegalRepository.__new__(PostgresLegalRepository)
    repository.engine = _FakeEngine(direct_connection)  # type: ignore[assignment]

    hits, trace = await repository.search_with_trace("전기사업법 제1조", date(2026, 7, 18), 10)

    assert hits and trace.strategy == "direct_path"
    assert "source_record_state='available'" in direct_connection.statements[0]
    assert "lifecycle_state IN ('active','scheduled')" in direct_connection.statements[0]
    assert "parser_schema_version='3'" in direct_connection.statements[0]
    assert "corpus.search_ready" in direct_connection.statements[0]

    provision_connection = _FakeConnection({"__direct__": [row]})
    repository.engine = _FakeEngine(provision_connection)  # type: ignore[assignment]
    hit = await repository.provision(row["provision_id"], date(2026, 7, 18))

    assert hit is not None
    assert "source_record_state='available'" in provision_connection.statements[0]
    assert "lifecycle_state IN ('active','scheduled')" in provision_connection.statements[0]
    assert "parser_schema_version='3'" in provision_connection.statements[0]
    assert "corpus.search_ready" in provision_connection.statements[0]
    assert direct_connection.execution_order == ["readiness", "retrieval"]
    assert provision_connection.execution_order == ["readiness", "retrieval"]
    assert all(
        "pg_advisory_xact_lock_shared" not in sql
        for connection in (direct_connection, provision_connection)
        for sql in connection.executed_sql
    )


@pytest.mark.asyncio
async def test_postgres_reports_closed_corpus_before_running_retrieval() -> None:
    connection = _FakeConnection({}, search_ready=False)
    repository = PostgresLegalRepository.__new__(PostgresLegalRepository)
    repository.engine = _FakeEngine(connection)  # type: ignore[assignment]

    with pytest.raises(CorpusSearchUnavailableError, match="embedding_backfill_started"):
        await repository.search_with_trace("전기사업 허가", date(2026, 7, 18), 10)

    assert connection.readiness_checks == 1
    assert connection.calls == []
    assert connection.execution_order == ["readiness"]
    assert all("pg_advisory_xact_lock_shared" not in sql for sql in connection.executed_sql)


@pytest.mark.asyncio
async def test_postgres_temporal_state_uses_collected_minimum_and_requested_today() -> None:
    supported_through = date(2026, 8, 4)
    connection = _FakeConnection(
        {},
        temporal_row={
            "supported_from": date(2007, 1, 1),
            "eligible_provision_count": 3066,
            "fingerprint_sha256": "a" * 64,
        },
    )
    repository = PostgresLegalRepository.__new__(PostgresLegalRepository)
    repository.engine = _FakeEngine(connection)  # type: ignore[assignment]

    state = await repository.corpus_temporal_state(supported_through)

    assert state.ready is True
    assert state.supported_as_of_from == date(2007, 1, 1)
    assert state.supported_as_of_through == supported_through
    assert state.eligible_provision_count == 3066
    assert state.corpus_snapshot_id is not None
    assert connection.readiness_checks == 1
    assert connection.temporal_calls == [
        {
            "corpus_ready_key": CORPUS_SEARCH_READY_FLAG_KEY,
            "supported_through": supported_through,
        }
    ]
    assert "MIN(effective_from)" in connection.temporal_statements[0]
    assert "effective_from<=:supported_through" in connection.temporal_statements[0]
    assert "effective_to>:supported_through" in connection.temporal_statements[0]
    assert (
        "effective_to"
        not in connection.temporal_statements[0]
        .split("jsonb_build_array(", 1)[1]
        .split(") ORDER BY", 1)[0]
    )


@pytest.mark.asyncio
async def test_postgres_temporal_state_rejects_future_only_or_empty_population() -> None:
    supported_through = date(2026, 8, 4)
    connection = _FakeConnection(
        {},
        temporal_row={
            "supported_from": None,
            "eligible_provision_count": 0,
            "fingerprint_sha256": "a" * 64,
        },
    )
    repository = PostgresLegalRepository.__new__(PostgresLegalRepository)
    repository.engine = _FakeEngine(connection)  # type: ignore[assignment]

    state = await repository.corpus_temporal_state(supported_through)

    assert state.ready is False
    assert state.reason == "no_currently_effective_corpus"
    assert state.supported_as_of_from is None
    assert state.corpus_snapshot_id is None


@pytest.mark.asyncio
async def test_postgres_temporal_state_does_not_hash_content_while_gate_is_closed() -> None:
    connection = _FakeConnection({}, search_ready=False)
    repository = PostgresLegalRepository.__new__(PostgresLegalRepository)
    repository.engine = _FakeEngine(connection)  # type: ignore[assignment]

    state = await repository.corpus_temporal_state(date(2026, 8, 4))

    assert state.ready is False
    assert state.reason == "embedding_backfill_started"
    assert connection.readiness_checks == 1
    assert connection.temporal_calls == [
        {
            "corpus_ready_key": CORPUS_SEARCH_READY_FLAG_KEY,
            "supported_through": date(2026, 8, 4),
        }
    ]
    assert len(connection.temporal_statements) == 1
    assert "(SELECT ready FROM readiness)" in connection.temporal_statements[0]


@pytest.mark.asyncio
async def test_postgres_rejects_embedding_without_matching_model() -> None:
    repository = PostgresLegalRepository.__new__(PostgresLegalRepository)

    with pytest.raises(ValueError, match="must be provided together"):
        await repository.search_with_trace(
            "전기사업 허가",
            date(2026, 7, 18),
            10,
            [0.1, 0.2],
        )


@pytest.mark.asyncio
async def test_single_term_no_result_does_not_repeat_identical_database_query() -> None:
    prepared = prepare_search_query("흐음")
    connection = _FakeConnection({prepared.strict_query: []})
    repository = PostgresLegalRepository.__new__(PostgresLegalRepository)
    repository.engine = _FakeEngine(connection)  # type: ignore[assignment]

    hits, trace = await repository.search_with_trace("흐음", date(2026, 7, 18), 10)

    assert hits == []
    assert len(connection.calls) == 1
    assert [stage.status for stage in trace.stages] == [
        "no_match",
        "skipped_duplicate_query",
        "skipped_no_anchor",
        "insufficient_evidence",
    ]
    assert trace.executed_query == prepared.strict_query


@pytest.mark.asyncio
async def test_two_term_no_result_does_not_repeat_equivalent_anchor_query() -> None:
    prepared = prepare_search_query("허가 서류")
    connection = _FakeConnection({prepared.strict_query: []})
    repository = PostgresLegalRepository.__new__(PostgresLegalRepository)
    repository.engine = _FakeEngine(connection)  # type: ignore[assignment]

    hits, trace = await repository.search_with_trace("허가 서류", date(2026, 7, 18), 10)

    assert hits == []
    assert prepared.strict_query == prepared.minimum_match_query == prepared.anchored_query
    assert len(connection.calls) == 1
    assert trace.executed_query == prepared.strict_query
