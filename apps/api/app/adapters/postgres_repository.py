import json
from collections.abc import Mapping
from datetime import date, datetime
from time import perf_counter
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine, create_async_engine
from sqlalchemy.pool import NullPool

from app.domain.catalog import MVP_CATALOG, SourceKind
from app.domain.entities import LegalDocumentRecord
from app.domain.provision_queries import parse_provision_reference
from app.domain.schemas import CorpusItemStatus, SearchHit
from app.domain.search_queries import (
    PreparedSearchQuery,
    SearchStageTrace,
    SearchTrace,
    matching_terms,
    prepare_search_query,
)


def _async_url(url: str) -> str:
    if url.startswith("postgresql+asyncpg://"):
        return url
    return url.replace("postgresql://", "postgresql+asyncpg://", 1)


class PostgresLegalRepository:
    def __init__(self, database_url: str) -> None:
        self.engine: AsyncEngine = create_async_engine(
            _async_url(database_url),
            poolclass=NullPool,
            connect_args={"statement_cache_size": 0},
        )

    async def consume_quota(self, subject_hash: str, day: date, kind: str, limit: int) -> bool:
        async with self.engine.begin() as connection:
            count = (
                await connection.execute(
                    text(
                        """INSERT INTO anonymous_usage(subject_hash,usage_date,kind,count)
                        VALUES(:subject,:day,:kind,1)
                        ON CONFLICT(subject_hash,usage_date,kind) DO UPDATE
                        SET count=anonymous_usage.count+1
                        WHERE anonymous_usage.count<:limit RETURNING count"""
                    ),
                    {"subject": subject_hash, "day": day, "kind": kind, "limit": limit},
                )
            ).scalar_one_or_none()
        return count is not None

    async def upsert_document(self, document: LegalDocumentRecord) -> UUID:
        async with self.engine.begin() as connection:
            document_id = (
                await connection.execute(
                    text(
                        """INSERT INTO legal_documents(source_id,exact_title,source_kind)
                        VALUES(:source_id,:title,:kind)
                        ON CONFLICT(source_kind,source_id) DO UPDATE SET exact_title=excluded.exact_title,
                        source_kind=excluded.source_kind RETURNING id"""
                    ),
                    {
                        "source_id": document.source_id,
                        "title": document.title,
                        "kind": document.source_kind.value,
                    },
                )
            ).scalar_one()
            version_id = (
                await connection.execute(
                    text(
                        """INSERT INTO document_versions(
                        document_id,mst,promulgation_number,promulgated_on,effective_from,ministry,
                        source_url,raw_format,raw_sha256,raw_storage_path,parser_schema_version,fallback_reason)
                        VALUES(:document_id,:mst,:number,:promulgated,:effective,:ministry,:url,:format,:hash,:storage,:schema,:fallback)
                        ON CONFLICT(document_id,mst) DO UPDATE SET
                        promulgation_number=excluded.promulgation_number,promulgated_on=excluded.promulgated_on,
                        effective_from=excluded.effective_from,ministry=excluded.ministry,source_url=excluded.source_url,
                        raw_format=excluded.raw_format,raw_sha256=excluded.raw_sha256,raw_storage_path=excluded.raw_storage_path,
                        parser_schema_version=excluded.parser_schema_version,fallback_reason=excluded.fallback_reason
                        RETURNING id"""
                    ),
                    {
                        "document_id": document_id,
                        "mst": document.mst,
                        "number": document.promulgation_number,
                        "promulgated": document.promulgated_on,
                        "effective": document.effective_from,
                        "ministry": document.ministry,
                        "url": document.source_url,
                        "format": document.raw_format,
                        "hash": document.raw_sha256,
                        "storage": document.raw_storage_path,
                        "schema": document.parser_schema_version,
                        "fallback": document.fallback_reason,
                    },
                )
            ).scalar_one()
            await connection.execute(
                text("DELETE FROM provisions WHERE version_id=:version_id"),
                {"version_id": version_id},
            )
            await connection.execute(
                text(
                    """INSERT INTO provisions(id,version_id,path,parent_path,heading,content,ordinal)
                    VALUES(:id,:version_id,:path,:parent_path,:heading,:content,:ordinal)"""
                ),
                [
                    {
                        "id": item.id,
                        "version_id": version_id,
                        "path": item.path,
                        "parent_path": item.parent_path,
                        "heading": item.heading,
                        "content": item.content,
                        "ordinal": item.ordinal,
                    }
                    for item in document.provisions
                ],
            )
        return document_id

    async def upsert_embeddings(
        self, values: list[tuple[UUID, list[float]]], model: str, dimensions: int
    ) -> None:
        if not values:
            return
        async with self.engine.begin() as connection:
            for provision_id, embedding in values:
                await connection.execute(
                    text(
                        """INSERT INTO provision_embeddings(provision_id,model,dimensions,embedding_version,embedding)
                        VALUES(:id,:model,:dimensions,'1',CAST(:embedding AS vector))
                        ON CONFLICT(provision_id,model,embedding_version) DO UPDATE SET embedding=excluded.embedding"""
                    ),
                    {
                        "id": provision_id,
                        "model": model,
                        "dimensions": dimensions,
                        "embedding": str(embedding),
                    },
                )

    async def search(
        self, query: str, as_of_date: date, limit: int, query_embedding: list[float] | None = None
    ) -> list[SearchHit]:
        hits, _ = await self.search_with_trace(query, as_of_date, limit, query_embedding)
        return hits

    async def search_with_trace(
        self, query: str, as_of_date: date, limit: int, query_embedding: list[float] | None = None
    ) -> tuple[list[SearchHit], SearchTrace]:
        started = perf_counter()
        embedding = str(query_embedding) if query_embedding else None
        reference = parse_provision_reference(query)
        prepared = prepare_search_query(query)
        async with self.engine.connect() as connection:
            path_rows = []
            if reference is not None:
                path_started = perf_counter()
            if reference is not None and reference.unrecognized_document_title is None:
                path_rows = (
                    (
                        await connection.execute(
                            text(
                                """SELECT p.id provision_id,d.id document_id,
                                d.exact_title document_title,d.source_kind,
                                'MST '||v.mst version_label,v.effective_from,v.effective_to,
                                p.path,p.heading,p.content,v.source_url,2.0 score
                                FROM provisions p
                                JOIN document_versions v ON v.id=p.version_id
                                JOIN legal_documents d ON d.id=v.document_id
                                WHERE p.path IN (
                                  SELECT jsonb_array_elements_text(CAST(:paths AS jsonb))
                                )
                                  AND (
                                    CAST(:title AS text) IS NULL
                                    OR d.exact_title=CAST(:title AS text)
                                  )
                                  AND (v.effective_from IS NULL OR v.effective_from<=:as_of)
                                  AND (v.effective_to IS NULL OR v.effective_to>:as_of)
                                ORDER BY d.exact_title,p.path LIMIT :limit"""
                            ),
                            {
                                "paths": json.dumps(reference.storage_paths),
                                "title": reference.document_title,
                                "as_of": as_of_date,
                                "limit": limit,
                            },
                        )
                    )
                    .mappings()
                    .all()
                )
            if reference is not None:
                selected = [self._hit(row) for row in path_rows][:limit]
                duration_ms = _elapsed_ms(path_started)
                return selected, SearchTrace(
                    strategy="direct_path",
                    normalized_query=prepared.normalized_text,
                    terms=prepared.terms,
                    executed_query=None,
                    relaxed=False,
                    reference_title=reference.document_title,
                    reference_path=reference.path,
                    candidate_count=len(selected),
                    anchor_term=prepared.anchor_term,
                    stages=(
                        SearchStageTrace(
                            stage="direct_path",
                            query=reference.path,
                            raw_candidate_count=len(path_rows),
                            accepted_candidate_count=len(selected),
                            duration_ms=duration_ms,
                            status="matched" if selected else "insufficient_evidence",
                        ),
                    ),
                    total_duration_ms=_elapsed_ms(started),
                )

            stages: list[SearchStageTrace] = []
            executed_queries: set[str] = set()
            last_executed_query: str | None = None
            candidate_limit = min(max(limit * 5, 50), 200)
            match_cache: dict[UUID, set[str]] = {}

            def row_matches(row: Mapping[str, Any]) -> set[str]:
                provision_id = row["provision_id"]
                if provision_id not in match_cache:
                    match_cache[provision_id] = _row_matching_terms(row, prepared)
                return match_cache[provision_id]

            stage_started = perf_counter()
            strict_rows = await _execute_search(
                connection,
                prepared.strict_query,
                as_of_date,
                embedding,
                candidate_limit,
            )
            if prepared.strict_query:
                executed_queries.add(prepared.strict_query)
                last_executed_query = prepared.strict_query
            strict_accepted = [
                row
                for row in strict_rows
                if prepared.terms and len(row_matches(row)) == len(prepared.terms)
            ]
            stages.append(
                _stage_trace(
                    "all_terms",
                    prepared.strict_query,
                    len(strict_rows),
                    len(strict_accepted),
                    stage_started,
                    "matched" if strict_accepted else "no_match",
                )
            )
            if strict_accepted:
                return _postgres_natural_result(
                    self,
                    strict_accepted,
                    limit,
                    prepared,
                    stages,
                    started,
                    prepared.strict_query,
                    query_embedding is not None,
                    False,
                )

            stage_started = perf_counter()
            minimum_query_executed = bool(
                prepared.minimum_match_query
                and prepared.minimum_match_query not in executed_queries
            )
            if minimum_query_executed:
                minimum_rows = await _execute_search(
                    connection,
                    prepared.minimum_match_query,
                    as_of_date,
                    embedding,
                    candidate_limit,
                )
                executed_queries.add(prepared.minimum_match_query)
                last_executed_query = prepared.minimum_match_query
            else:
                minimum_rows = strict_rows
            minimum = min(2, len(prepared.terms))
            minimum_accepted = [
                row for row in minimum_rows if minimum and len(row_matches(row)) >= minimum
            ]
            stages.append(
                _stage_trace(
                    "minimum_two",
                    prepared.minimum_match_query,
                    len(minimum_rows),
                    len(minimum_accepted),
                    stage_started,
                    (
                        "candidate_pool"
                        if minimum_accepted
                        else "no_match"
                        if minimum_query_executed
                        else "skipped_duplicate_query"
                    ),
                )
            )

            stage_started = perf_counter()
            anchored = (
                [row for row in minimum_accepted if prepared.anchor_term in row_matches(row)]
                if prepared.anchor_term
                else []
            )
            anchor_raw_count = len(minimum_accepted)
            anchor_query_executed = False
            anchor_query_skipped = False
            if (
                not anchored
                and prepared.anchored_query
                and prepared.anchored_query not in executed_queries
            ):
                anchor_query_executed = True
                anchor_rows = await _execute_search(
                    connection,
                    prepared.anchored_query,
                    as_of_date,
                    embedding,
                    candidate_limit,
                )
                executed_queries.add(prepared.anchored_query)
                last_executed_query = prepared.anchored_query
                anchor_raw_count = len(anchor_rows)
                anchored = [
                    row
                    for row in anchor_rows
                    if prepared.anchor_term in row_matches(row) and len(row_matches(row)) >= minimum
                ]
            elif not anchored and prepared.anchored_query in executed_queries:
                anchor_query_skipped = True
            stages.append(
                _stage_trace(
                    "anchor_required",
                    prepared.anchored_query if anchor_query_executed else None,
                    anchor_raw_count,
                    len(anchored),
                    stage_started,
                    (
                        "matched"
                        if anchored
                        else "skipped_no_anchor"
                        if prepared.anchor_term is None
                        else "skipped_duplicate_query"
                        if anchor_query_skipped
                        else "no_match"
                    ),
                )
            )
            if anchored:
                return _postgres_natural_result(
                    self,
                    anchored,
                    limit,
                    prepared,
                    stages,
                    started,
                    (
                        prepared.anchored_query
                        if anchor_query_executed
                        else prepared.minimum_match_query
                    ),
                    query_embedding is not None,
                    True,
                )

        stage_started = perf_counter()
        stages.append(
            _stage_trace(
                "insufficient_evidence",
                None,
                0,
                0,
                stage_started,
                "insufficient_evidence",
            )
        )
        return [], SearchTrace(
            strategy="four_stage_hybrid" if query_embedding else "four_stage_keyword",
            normalized_query=prepared.normalized_text,
            terms=prepared.terms,
            executed_query=last_executed_query,
            relaxed=True,
            reference_title=None,
            reference_path=None,
            candidate_count=0,
            anchor_term=prepared.anchor_term,
            stages=tuple(stages),
            total_duration_ms=_elapsed_ms(started),
        )

    async def provision(self, provision_id: UUID, as_of_date: date) -> SearchHit | None:
        async with self.engine.connect() as connection:
            row = (
                (
                    await connection.execute(
                        text(
                            """SELECT p.id provision_id,d.id document_id,d.exact_title document_title,d.source_kind,
                        'MST '||v.mst version_label,v.effective_from,v.effective_to,p.path,p.heading,p.content,
                        v.source_url,1.0 score FROM provisions p JOIN document_versions v ON v.id=p.version_id
                        JOIN legal_documents d ON d.id=v.document_id WHERE p.id=:id AND
                        (v.effective_from IS NULL OR v.effective_from<=:as_of) AND
                        (v.effective_to IS NULL OR v.effective_to>:as_of)"""
                        ),
                        {"id": provision_id, "as_of": as_of_date},
                    )
                )
                .mappings()
                .first()
            )
        return self._hit(row) if row else None

    async def corpus_items(self) -> list[CorpusItemStatus]:
        async with self.engine.connect() as connection:
            rows = (
                await connection.execute(
                    text(
                        "SELECT exact_title,MAX(effective_from) latest FROM legal_documents d JOIN document_versions v ON v.document_id=d.id GROUP BY exact_title"
                    )
                )
            ).all()
        ready = {row[0]: row[1] for row in rows}
        return [
            CorpusItemStatus(
                title=e.title,
                source_kind=e.source_kind,
                state="ready" if e.title in ready else "missing",
                latest_effective_date=ready.get(e.title),
            )
            for e in MVP_CATALOG
        ]

    async def last_sync(self) -> datetime | None:
        async with self.engine.connect() as connection:
            return (
                await connection.execute(text("SELECT MAX(collected_at) FROM document_versions"))
            ).scalar_one_or_none()

    @staticmethod
    def _hit(row) -> SearchHit:
        return SearchHit(
            provision_id=row["provision_id"],
            document_id=row["document_id"],
            document_title=row["document_title"],
            source_kind=SourceKind(row["source_kind"]),
            version_label=row["version_label"],
            effective_from=row["effective_from"],
            effective_to=row["effective_to"],
            path=row["path"],
            heading=row["heading"],
            content=row["content"],
            source_url=row["source_url"],
            score=float(row["score"]),
        )


async def _execute_search(
    connection: AsyncConnection,
    query: str,
    as_of_date: date,
    embedding: str | None,
    limit: int,
) -> list[Mapping[str, Any]]:
    if not query:
        return []
    return list(
        (
            await connection.execute(
                text("SELECT * FROM hybrid_search(:query,:as_of,:embedding,:limit)"),
                {
                    "query": query,
                    "as_of": as_of_date,
                    "embedding": embedding,
                    "limit": limit,
                },
            )
        )
        .mappings()
        .all()
    )


def _row_matching_terms(row: Mapping[str, Any], prepared: PreparedSearchQuery) -> set[str]:
    return matching_terms(
        " ".join(
            (
                str(row["document_title"]),
                str(row["heading"] or ""),
                str(row["content"]),
            )
        ),
        prepared,
    )


def _elapsed_ms(started: float) -> float:
    return (perf_counter() - started) * 1000


def _stage_trace(
    stage: str,
    query: str | None,
    raw_count: int,
    accepted_count: int,
    started: float,
    status: str,
) -> SearchStageTrace:
    return SearchStageTrace(
        stage=stage,
        query=query or None,
        raw_candidate_count=raw_count,
        accepted_candidate_count=accepted_count,
        duration_ms=_elapsed_ms(started),
        status=status,
    )


def _postgres_natural_result(
    repository: PostgresLegalRepository,
    rows: list[Mapping[str, Any]],
    limit: int,
    prepared: PreparedSearchQuery,
    stages: list[SearchStageTrace],
    started: float,
    executed_query: str,
    hybrid: bool,
    relaxed: bool,
) -> tuple[list[SearchHit], SearchTrace]:
    selected: list[SearchHit] = []
    seen: set[UUID] = set()
    for row in rows:
        provision_id = row["provision_id"]
        if provision_id in seen:
            continue
        seen.add(provision_id)
        selected.append(repository._hit(row))
        if len(selected) == limit:
            break
    return selected, SearchTrace(
        strategy="four_stage_hybrid" if hybrid else "four_stage_keyword",
        normalized_query=prepared.normalized_text,
        terms=prepared.terms,
        executed_query=executed_query,
        relaxed=relaxed,
        reference_title=None,
        reference_path=None,
        candidate_count=len(selected),
        anchor_term=prepared.anchor_term,
        stages=tuple(stages),
        total_duration_ms=_elapsed_ms(started),
    )
