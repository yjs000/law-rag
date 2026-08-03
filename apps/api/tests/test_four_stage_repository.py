import json
from datetime import date
from uuid import uuid4

import pytest

from app.adapters.memory_repository import MemoryLegalRepository
from app.adapters.postgres_repository import PostgresLegalRepository
from app.domain.catalog import SourceKind
from app.domain.embedding_profiles import NVIDIA_NEMOTRON_512_PROFILE
from app.domain.entities import ProvisionRecord
from app.domain.search_queries import prepare_search_query
from app.parsers.law_json import parse_legal_document


class _MappingsResult:
    def __init__(self, rows: list[dict]) -> None:
        self._rows = rows

    def mappings(self):
        return self

    def all(self):
        return self._rows


class _FakeConnection:
    def __init__(self, rows_by_query: dict[str, list[dict]]) -> None:
        self.rows_by_query = rows_by_query
        self.calls: list[dict] = []
        self.statements: list[str] = []

    async def execute(self, statement, params: dict):
        self.calls.append(params)
        self.statements.append(str(statement))
        key = "__dense__" if "embedding" in params else params["query"]
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
