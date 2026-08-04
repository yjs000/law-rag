import json
from collections.abc import Mapping
from datetime import date, datetime
from math import fsum, isfinite, sqrt
from time import perf_counter
from typing import Any
from uuid import UUID

from law_rag_core.domain.identifiers import PARSER_SCHEMA_VERSION
from law_rag_core.persistence import (
    CORPUS_MUTATION_LOCK_KEY,
    CORPUS_SEARCH_READY_CAPABILITY_SQL,
    CORPUS_SEARCH_READY_FLAG_KEY,
    CORPUS_SEARCH_READY_SQL,
    LEGAL_PROVISION_V1_SOURCE_SHA_SQL,
    SEARCHABLE_DOCUMENT_VERSION_SQL,
)
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine, create_async_engine
from sqlalchemy.pool import NullPool

from app.domain.catalog import MVP_CATALOG, SourceKind
from app.domain.corpus_temporal_contract import (
    UnsupportedCorpusDateError,
    canonical_corpus_snapshot_id,
    korea_today,
    require_supported_corpus_date,
)
from app.domain.embedding_profiles import NVIDIA_NEMOTRON_512_PROFILE
from app.domain.entities import LegalDocumentRecord
from app.domain.errors import CorpusSearchUnavailableError
from app.domain.provision_queries import parse_provision_references
from app.domain.schemas import (
    CorpusItemStatus,
    CorpusSearchStatus,
    CorpusTemporalState,
    SearchHit,
)
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
        raise RuntimeError(
            "PostgresLegalRepository is a runtime reader; "
            "only the validated collector may mutate the legal corpus"
        )

    async def upsert_embeddings(
        self,
        values: list[tuple[UUID, str, list[float]]],
        profile_key: str,
        dimensions: int,
    ) -> None:
        if not values:
            return
        if profile_key != NVIDIA_NEMOTRON_512_PROFILE.key:
            raise ValueError("unsupported embedding profile")
        if dimensions != NVIDIA_NEMOTRON_512_PROFILE.stored_dimensions:
            raise ValueError("embedding dimensions do not match profile")
        if any(len(embedding) != dimensions for _, _, embedding in values):
            raise ValueError("embedding vector dimensions do not match profile")
        values_by_id = {
            provision_id: (source_sha, embedding) for provision_id, source_sha, embedding in values
        }
        if len(values_by_id) != len(values):
            raise ValueError("embedding batch contains duplicate provision IDs")
        for source_sha, embedding in values_by_id.values():
            if (
                not isinstance(source_sha, str)
                or len(source_sha) != 64
                or any(character not in "0123456789abcdef" for character in source_sha)
            ):
                raise ValueError("embedding source hash must be a lowercase SHA-256")
            if any(
                isinstance(component, bool)
                or not isinstance(component, int | float)
                or not isfinite(component)
                for component in embedding
            ):
                raise ValueError("embedding vector contains a non-finite value")
            norm = sqrt(fsum(component * component for component in embedding))
            if abs(norm - 1.0) > 0.0001:
                raise ValueError("embedding vector must be L2-normalized")
        async with self.engine.begin() as connection:
            await connection.execute(
                text("SELECT pg_catalog.pg_advisory_xact_lock(:lock_key)"),
                {"lock_key": CORPUS_MUTATION_LOCK_KEY},
            )
            current_rows = (
                (
                    await connection.execute(
                        text(
                            f"""SELECT p.id provision_id,
                            {LEGAL_PROVISION_V1_SOURCE_SHA_SQL} source_text_sha256
                            FROM provisions p
                            JOIN document_versions v ON v.id=p.version_id
                            JOIN legal_documents d ON d.id=v.document_id
                            JOIN embedding_profiles ep
                              ON ep.profile_key=:profile_key
                             AND ep.stored_dimensions=:dimensions
                             AND ep.text_template_version='legal-provision-v1'
                            WHERE p.id=ANY(CAST(:provision_ids AS uuid[]))
                              AND {SEARCHABLE_DOCUMENT_VERSION_SQL}"""
                        ),
                        {
                            "profile_key": profile_key,
                            "dimensions": dimensions,
                            "provision_ids": list(values_by_id),
                        },
                    )
                )
                .mappings()
                .all()
            )
            current_hashes = {
                UUID(str(row["provision_id"])): row["source_text_sha256"] for row in current_rows
            }
            if set(current_hashes) != set(values_by_id):
                raise RuntimeError(
                    "embedding batch contains a provision outside the current eligible corpus"
                )
            if any(
                current_hashes[provision_id] != source_sha
                for provision_id, (source_sha, _) in values_by_id.items()
            ):
                raise RuntimeError(
                    "embedding batch source hash is stale; the complete batch was rolled back"
                )
            schema_ready = (
                await connection.execute(text(f"SELECT {CORPUS_SEARCH_READY_CAPABILITY_SQL}"))
            ).scalar_one()
            if not schema_ready:
                raise RuntimeError("database must be migrated to revision 0010 or later")
            await connection.execute(
                text(
                    """UPDATE embedding_profiles SET active=false
                    WHERE profile_key=:profile_key"""
                ),
                {"profile_key": profile_key},
            )
            await connection.execute(
                text(
                    """INSERT INTO runtime_flags(key,value,updated_at)
                    VALUES(:key,CAST(:value AS jsonb),now())
                    ON CONFLICT(key) DO UPDATE
                    SET value=excluded.value,updated_at=now()"""
                ),
                {
                    "key": CORPUS_SEARCH_READY_FLAG_KEY,
                    "value": json.dumps({"ready": False, "reason": "embedding_batch"}),
                },
            )
            await connection.execute(
                text(
                    """INSERT INTO provision_embeddings(
                    provision_id,profile_key,dimensions,source_text_sha256,embedding,embedded_at)
                    VALUES(:id,:profile_key,:dimensions,:source_text_sha256,CAST(:embedding AS vector),now())
                    ON CONFLICT(provision_id,profile_key) DO UPDATE SET
                    dimensions=excluded.dimensions,
                    source_text_sha256=excluded.source_text_sha256,
                    embedding=excluded.embedding,
                    embedded_at=excluded.embedded_at"""
                ),
                [
                    {
                        "id": provision_id,
                        "profile_key": profile_key,
                        "dimensions": dimensions,
                        "source_text_sha256": source_text_sha256,
                        "embedding": str(embedding),
                    }
                    for provision_id, source_text_sha256, embedding in values
                ],
            )

    async def search(
        self,
        query: str,
        as_of_date: date,
        limit: int,
        query_embedding: list[float] | None = None,
        embedding_profile_key: str | None = None,
    ) -> list[SearchHit]:
        hits, _ = await self.search_with_trace(
            query, as_of_date, limit, query_embedding, embedding_profile_key
        )
        return hits

    async def search_with_trace(
        self,
        query: str,
        as_of_date: date,
        limit: int,
        query_embedding: list[float] | None = None,
        embedding_profile_key: str | None = None,
    ) -> tuple[list[SearchHit], SearchTrace]:
        started = perf_counter()
        if (query_embedding is None) != (embedding_profile_key is None):
            raise ValueError("query embedding and profile must be provided together")
        if (
            embedding_profile_key is not None
            and embedding_profile_key != NVIDIA_NEMOTRON_512_PROFILE.key
        ):
            raise ValueError("unsupported embedding profile")
        embedding = str(query_embedding) if query_embedding else None
        provision_query = parse_provision_references(query)
        prepared = prepare_search_query(query)
        async with self.engine.connect() as connection:
            await _lock_and_require_supported_corpus_date(connection, as_of_date)
            path_rows = []
            if provision_query is not None:
                path_started = perf_counter()
            if (
                provision_query is not None
                and provision_query.unrecognized_document_title is None
                and provision_query.invalid_reason is None
            ):
                path_rows = (
                    (
                        await connection.execute(
                            text(
                                f"""SELECT p.id provision_id,d.id document_id,
                                d.exact_title document_title,d.source_kind,
                                'MST '||v.mst version_label,v.effective_from,v.effective_to,
                                p.path,p.heading,p.content,v.source_url,2.0 score
                                FROM provisions p
                                JOIN document_versions v ON v.id=p.version_id
                                JOIN legal_documents d ON d.id=v.document_id
                                JOIN jsonb_array_elements_text(CAST(:paths AS jsonb))
                                  WITH ORDINALITY requested(path, ordinal)
                                  ON requested.path=p.path
                                WHERE (
                                    CAST(:title AS text) IS NULL
                                    OR d.exact_title=CAST(:title AS text)
                                  )
                                  AND {SEARCHABLE_DOCUMENT_VERSION_SQL}
                                  AND {CORPUS_SEARCH_READY_SQL}
                                  AND (v.effective_from IS NULL OR v.effective_from<=:as_of)
                                  AND (v.effective_to IS NULL OR v.effective_to>:as_of)
                                ORDER BY requested.ordinal,d.exact_title,p.path LIMIT :limit"""
                            ),
                            {
                                "paths": json.dumps(provision_query.storage_paths),
                                "title": provision_query.document_title,
                                "as_of": as_of_date,
                                "limit": limit,
                            },
                        )
                    )
                    .mappings()
                    .all()
                )
            if provision_query is not None:
                selected = [self._hit(row) for row in path_rows][:limit]
                if not selected:
                    await _require_corpus_search_ready(connection)
                duration_ms = _elapsed_ms(path_started)
                return selected, SearchTrace(
                    strategy="direct_path",
                    normalized_query=prepared.normalized_text,
                    terms=prepared.terms,
                    executed_query=None,
                    relaxed=False,
                    reference_title=provision_query.document_title,
                    reference_path=", ".join(
                        reference.path for reference in provision_query.references
                    ),
                    candidate_count=len(selected),
                    anchor_term=prepared.anchor_term,
                    stages=(
                        SearchStageTrace(
                            stage="direct_path",
                            query=", ".join(
                                reference.path for reference in provision_query.references
                            ),
                            raw_candidate_count=len(path_rows),
                            accepted_candidate_count=len(selected),
                            duration_ms=duration_ms,
                            status="matched" if selected else "insufficient_evidence",
                        ),
                    ),
                    total_duration_ms=_elapsed_ms(started),
                )

            stages: list[SearchStageTrace] = []
            candidate_limit = min(max(limit * 5, 50), 200)
            retrieval_strategy = "four_stage_keyword"
            if embedding is not None and embedding_profile_key is not None:
                dense_started = perf_counter()
                dense_rows = await _execute_dense_search(
                    connection,
                    as_of_date,
                    embedding,
                    embedding_profile_key,
                    candidate_limit,
                )
                dense_candidates = _unique_article_rows(dense_rows)
                stages.append(
                    _stage_trace(
                        "dense_retrieval",
                        None,
                        len(dense_rows),
                        len(dense_candidates),
                        dense_started,
                        "matched" if dense_candidates else "no_match",
                    )
                )
                if dense_candidates:
                    return _postgres_natural_result(
                        self,
                        dense_candidates,
                        limit,
                        prepared,
                        stages,
                        started,
                        None,
                        "dense_only",
                        False,
                    )
                retrieval_strategy = "dense_then_keyword_fallback"

            executed_queries: set[str] = set()
            last_executed_query: str | None = None
            match_cache: dict[UUID, set[str]] = {}

            def row_matches(row: Mapping[str, Any]) -> set[str]:
                provision_id = row["provision_id"]
                if provision_id not in match_cache:
                    match_cache[provision_id] = _row_matching_terms(row, prepared)
                return match_cache[provision_id]

            stage_started = perf_counter()
            strict_rows = await _execute_keyword_search(
                connection,
                prepared.strict_query,
                as_of_date,
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
                    retrieval_strategy,
                    False,
                )

            stage_started = perf_counter()
            minimum_query_executed = bool(
                prepared.minimum_match_query
                and prepared.minimum_match_query not in executed_queries
            )
            if minimum_query_executed:
                minimum_rows = await _execute_keyword_search(
                    connection,
                    prepared.minimum_match_query,
                    as_of_date,
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
                anchor_rows = await _execute_keyword_search(
                    connection,
                    prepared.anchored_query,
                    as_of_date,
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
                    retrieval_strategy,
                    True,
                )

            await _require_corpus_search_ready(connection)

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
            strategy=retrieval_strategy,
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
            await _lock_and_require_supported_corpus_date(connection, as_of_date)
            row = (
                (
                    await connection.execute(
                        text(
                            f"""SELECT p.id provision_id,d.id document_id,d.exact_title document_title,d.source_kind,
                        'MST '||v.mst version_label,v.effective_from,v.effective_to,p.path,p.heading,p.content,
                        v.source_url,1.0 score FROM provisions p JOIN document_versions v ON v.id=p.version_id
                        JOIN legal_documents d ON d.id=v.document_id WHERE p.id=:id AND
                        {SEARCHABLE_DOCUMENT_VERSION_SQL} AND
                        {CORPUS_SEARCH_READY_SQL} AND
                        (v.effective_from IS NULL OR v.effective_from<=:as_of) AND
                        (v.effective_to IS NULL OR v.effective_to>:as_of)"""
                        ),
                        {"id": provision_id, "as_of": as_of_date},
                    )
                )
                .mappings()
                .first()
            )
            if row is None:
                await _require_corpus_search_ready(connection)
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

    async def corpus_search_status(self) -> CorpusSearchStatus:
        async with self.engine.connect() as connection:
            return await _corpus_search_status(connection)

    async def corpus_temporal_state(self, supported_through: date) -> CorpusTemporalState:
        async with self.engine.connect() as connection:
            return await _corpus_temporal_state(connection, supported_through)

    async def corpus_search_status_on_connection(
        self, connection: AsyncConnection
    ) -> CorpusSearchStatus:
        return await _corpus_search_status(connection)

    async def search_dense_provisions_on_connection(
        self,
        connection: AsyncConnection,
        as_of_date: date,
        limit: int,
        query_embedding: list[float],
        embedding_profile_key: str,
    ) -> list[SearchHit]:
        """Return raw dense provision rows without path, keyword, or article fallback."""

        embedding = _validate_dense_provision_request(
            limit,
            query_embedding,
            embedding_profile_key,
        )
        await _require_corpus_search_ready(connection)
        rows = list(
            (
                await connection.execute(
                    _experiment_dense_search_statement(),
                    _dense_search_parameters(
                        as_of_date,
                        embedding,
                        embedding_profile_key,
                        limit,
                    ),
                )
            )
            .mappings()
            .all()
        )
        provision_ids = [row["provision_id"] for row in rows]
        if len(set(provision_ids)) != len(provision_ids):
            raise ValueError("dense provision search returned duplicate IDs")
        if any(not isfinite(float(row["score"])) for row in rows):
            raise ValueError("dense provision search returned a non-finite score")
        return [self._hit(row) for row in rows]

    async def explain_dense_provisions_on_connection(
        self,
        connection: AsyncConnection,
        as_of_date: date,
        limit: int,
        query_embedding: list[float],
        embedding_profile_key: str,
    ) -> object:
        """Explain the exact raw dense provision query used by Experiment D."""

        embedding = _validate_dense_provision_request(
            limit,
            query_embedding,
            embedding_profile_key,
        )
        await _require_corpus_search_ready(connection)
        return (
            await connection.execute(
                _experiment_dense_search_statement(explain=True),
                _dense_search_parameters(
                    as_of_date,
                    embedding,
                    embedding_profile_key,
                    limit,
                ),
            )
        ).scalar_one()

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


async def _execute_dense_search(
    connection: AsyncConnection,
    as_of_date: date,
    embedding: str,
    embedding_profile_key: str,
    limit: int,
    *,
    tie_break_by_provision_id: bool = False,
) -> list[Mapping[str, Any]]:
    return list(
        (
            await connection.execute(
                _dense_search_statement(
                    tie_break_by_provision_id=tie_break_by_provision_id,
                ),
                _dense_search_parameters(
                    as_of_date,
                    embedding,
                    embedding_profile_key,
                    limit,
                ),
            )
        )
        .mappings()
        .all()
    )


def _validate_dense_provision_request(
    limit: int,
    query_embedding: list[float],
    embedding_profile_key: str,
) -> str:
    if embedding_profile_key != NVIDIA_NEMOTRON_512_PROFILE.key:
        raise ValueError("unsupported embedding profile")
    if not 1 <= limit <= 200:
        raise ValueError("dense provision limit must be between 1 and 200")
    if len(query_embedding) != NVIDIA_NEMOTRON_512_PROFILE.stored_dimensions:
        raise ValueError("query embedding dimensions do not match profile")
    if any(
        isinstance(component, bool)
        or not isinstance(component, int | float)
        or not isfinite(component)
        for component in query_embedding
    ):
        raise ValueError("query embedding contains a non-finite value")
    norm = sqrt(fsum(float(component) * float(component) for component in query_embedding))
    if abs(norm - 1.0) > 0.0001:
        raise ValueError("query embedding must be L2-normalized")
    return str(query_embedding)


def _dense_search_statement(
    *,
    tie_break_by_provision_id: bool = False,
    explain: bool = False,
):
    """Build the exhaustive dense query used while approximate search is deferred."""

    tie_breaker = "provision_id" if tie_break_by_provision_id else "ordinal"
    explain_prefix = "EXPLAIN (FORMAT JSON, COSTS OFF, SETTINGS TRUE)\n" if explain else ""
    return text(
        f"""{explain_prefix}WITH exact_eligible_distances AS MATERIALIZED (
        SELECT p.id provision_id,p.ordinal,d.id document_id,
        d.exact_title document_title,d.source_kind,
        'MST '||v.mst version_label,v.effective_from,v.effective_to,
        p.path,p.heading,p.content,v.source_url,
        e.embedding::vector(512) <=> CAST(:embedding AS vector(512)) distance
        FROM provisions p
        JOIN document_versions v ON v.id=p.version_id
        JOIN legal_documents d ON d.id=v.document_id
        JOIN provision_embeddings e ON e.provision_id=p.id
        JOIN embedding_profiles ep
          ON ep.profile_key=e.profile_key AND ep.stored_dimensions=e.dimensions
        WHERE (v.effective_from IS NULL OR v.effective_from<=:as_of)
          AND (v.effective_to IS NULL OR v.effective_to>:as_of)
          AND {SEARCHABLE_DOCUMENT_VERSION_SQL}
          AND {CORPUS_SEARCH_READY_SQL}
          AND e.profile_key=:embedding_profile_key
          AND e.dimensions=512
          AND ep.active IS TRUE
          AND ep.text_template_version='legal-provision-v1'
          AND e.source_text_sha256={LEGAL_PROVISION_V1_SOURCE_SHA_SQL}
        )
        SELECT provision_id,document_id,document_title,source_kind,
        version_label,effective_from,effective_to,path,heading,content,source_url,
        1.0-distance score
        FROM exact_eligible_distances
        ORDER BY distance,{tie_breaker}
        LIMIT :limit"""
    )


def _experiment_dense_search_statement(*, explain: bool = False):
    """Build Experiment D's exhaustive exact-cosine provision query.

    The materialized CTE computes every eligible distance before the outer
    ordering and limit.  Keeping KNN ORDER BY/LIMIT out of the CTE preserves
    exhaustive distance calculation over the eligible population.  The outer
    provision ID key only makes equal-distance ordering deterministic; the
    runner still rejects an unresolved raw-score tie at the top-10 boundary.
    """

    return _dense_search_statement(
        tie_break_by_provision_id=True,
        explain=explain,
    )


def _dense_search_parameters(
    as_of_date: date,
    embedding: str,
    embedding_profile_key: str,
    limit: int,
) -> dict[str, object]:
    return {
        "as_of": as_of_date,
        "embedding": embedding,
        "embedding_profile_key": embedding_profile_key,
        "limit": limit,
    }


async def _corpus_search_status(connection: AsyncConnection) -> CorpusSearchStatus:
    row = (
        (
            await connection.execute(
                text(
                    f"""SELECT /* corpus_search_readiness_check */
                    {CORPUS_SEARCH_READY_SQL} ready,
                    CASE WHEN NOT ({CORPUS_SEARCH_READY_CAPABILITY_SQL})
                      THEN 'schema_capability_missing'
                      ELSE COALESCE(
                        (SELECT value->>'reason' FROM runtime_flags
                         WHERE key=:corpus_ready_key),
                        'runtime_flag_missing'
                      )
                    END reason"""
                ),
                {"corpus_ready_key": CORPUS_SEARCH_READY_FLAG_KEY},
            )
        )
        .mappings()
        .first()
    )
    if row is None:
        return CorpusSearchStatus(ready=False, reason="status_query_empty")
    return CorpusSearchStatus(
        ready=bool(row["ready"]),
        reason=None if row["ready"] else str(row["reason"] or "corpus_unready"),
    )


async def _corpus_temporal_state(
    connection: AsyncConnection,
    supported_through: date,
) -> CorpusTemporalState:
    row = (
        (
            await connection.execute(
                _corpus_temporal_population_statement(),
                {
                    "corpus_ready_key": CORPUS_SEARCH_READY_FLAG_KEY,
                    "supported_through": supported_through,
                },
            )
        )
        .mappings()
        .first()
    )
    if row is None:
        return CorpusTemporalState(
            ready=False,
            reason="status_query_empty",
            supported_as_of_through=supported_through,
        )
    if not bool(row["ready"]):
        return CorpusTemporalState(
            ready=False,
            reason=str(row["reason"] or "corpus_unready"),
            supported_as_of_through=supported_through,
        )
    if int(row["eligible_provision_count"] or 0) == 0:
        return CorpusTemporalState(
            ready=False,
            reason="no_currently_effective_corpus",
            supported_as_of_through=supported_through,
        )

    supported_from = row["supported_from"]
    fingerprint = row["fingerprint_sha256"]
    if not isinstance(supported_from, date) or not isinstance(fingerprint, str):
        return CorpusTemporalState(
            ready=False,
            reason="corpus_temporal_identity_incomplete",
            supported_as_of_through=supported_through,
        )
    eligible_count = int(row["eligible_provision_count"])
    snapshot_id = canonical_corpus_snapshot_id(
        parser_contract_version=PARSER_SCHEMA_VERSION,
        retrieval_unit="provision",
        content_populations=[
            {
                "eligible_provision_count": eligible_count,
                "fingerprint_sha256": fingerprint,
            }
        ],
    )
    return CorpusTemporalState(
        ready=True,
        supported_as_of_from=supported_from,
        supported_as_of_through=supported_through,
        corpus_snapshot_id=snapshot_id,
        eligible_provision_count=eligible_count,
    )


def _corpus_temporal_population_statement():
    """Build the read-only current-population identity query."""

    return text(
        f"""WITH readiness AS MATERIALIZED (
        SELECT {CORPUS_SEARCH_READY_SQL} ready,
        CASE WHEN NOT ({CORPUS_SEARCH_READY_CAPABILITY_SQL})
          THEN 'schema_capability_missing'
          ELSE COALESCE(
            (SELECT value->>'reason' FROM runtime_flags
             WHERE key=:corpus_ready_key),
            'runtime_flag_missing'
          )
        END reason
        ), collected AS MATERIALIZED (
        SELECT p.id provision_id,p.version_id,d.id document_id,
        d.exact_title document_title,d.source_kind,
        v.effective_from,v.effective_to,p.path,p.parent_path,p.heading,
        encode(digest(p.content,'sha256'),'hex') content_sha256
        FROM provisions p
        JOIN document_versions v ON v.id=p.version_id
        JOIN legal_documents d ON d.id=v.document_id
        WHERE {SEARCHABLE_DOCUMENT_VERSION_SQL}
          AND (SELECT ready FROM readiness)
        ), eligible AS MATERIALIZED (
        SELECT * FROM collected
        WHERE effective_from<=:supported_through
          AND (effective_to IS NULL OR effective_to>:supported_through)
        ), population AS (
        SELECT
        (SELECT MIN(effective_from) FROM collected
         WHERE effective_from<=:supported_through) supported_from,
        COUNT(*)::bigint eligible_provision_count,
        encode(digest(
          COALESCE(jsonb_agg(jsonb_build_array(
            '{PARSER_SCHEMA_VERSION}',
            document_id::text,
            version_id::text,
            provision_id::text,
            document_title,
            source_kind::text,
            effective_from::text,
            path,
            parent_path,
            heading,
            content_sha256
          ) ORDER BY provision_id),'[]'::jsonb)::text,
          'sha256'
        ),'hex') fingerprint_sha256
        FROM eligible
        )
        SELECT /* corpus_temporal_population */
        readiness.ready,readiness.reason,
        population.supported_from,population.eligible_provision_count,
        population.fingerprint_sha256
        FROM readiness CROSS JOIN population"""
    )


async def _require_corpus_search_ready(connection: AsyncConnection) -> None:
    status = await _corpus_search_status(connection)
    if not status.ready:
        raise CorpusSearchUnavailableError(status.reason or "corpus_unready")


async def _lock_and_require_supported_corpus_date(
    connection: AsyncConnection,
    requested_date: date,
) -> CorpusTemporalState:
    """Pin one complete corpus generation and revalidate the requested date.

    The lock must be the first statement on this fresh READ COMMITTED connection.
    Corpus writers take the exclusive form of the same transaction lock, so the
    following temporal-state query and retrieval statements cannot straddle two
    completed corpus generations.
    """

    await connection.execute(
        text("SELECT pg_catalog.pg_advisory_xact_lock_shared(:lock_key)"),
        {"lock_key": CORPUS_MUTATION_LOCK_KEY},
    )
    state = await _corpus_temporal_state(connection, korea_today())
    if not state.ready:
        raise CorpusSearchUnavailableError(state.reason or "corpus_unready")
    try:
        require_supported_corpus_date(requested_date, state)
    except UnsupportedCorpusDateError as exc:
        raise CorpusSearchUnavailableError("corpus_temporal_state_changed") from exc
    return state


async def _execute_keyword_search(
    connection: AsyncConnection,
    query: str,
    as_of_date: date,
    limit: int,
) -> list[Mapping[str, Any]]:
    if not query:
        return []
    return list(
        (
            await connection.execute(
                text(
                    f"""WITH valid AS (
                      SELECT p.*,v.document_id,v.mst,v.effective_from,v.effective_to,
                             v.source_url,d.exact_title,d.source_kind,
                             p.tableoid provision_tableoid,p.ctid provision_ctid
                      FROM provisions p
                      JOIN document_versions v ON v.id=p.version_id
                      JOIN legal_documents d ON d.id=v.document_id
                      WHERE (v.effective_from IS NULL OR v.effective_from<=:as_of)
                        AND (v.effective_to IS NULL OR v.effective_to>:as_of)
                        AND {SEARCHABLE_DOCUMENT_VERSION_SQL}
                        AND {CORPUS_SEARCH_READY_SQL}
                    )
                    SELECT v.id provision_id,v.document_id,v.exact_title document_title,
                           v.source_kind,'MST '||v.mst version_label,
                           v.effective_from,v.effective_to,v.path,v.heading,v.content,
                           v.source_url,
                           (CASE WHEN v.exact_title &@~ :query THEN 3.0 ELSE 0.0 END)+
                           (CASE WHEN ARRAY[COALESCE(v.heading,''),v.content] &@~
                             (:query,ARRAY[2,1],'provisions_search_pgroonga')::pgroonga_full_text_search_condition
                             THEN GREATEST(pgroonga_score(v.provision_tableoid,v.provision_ctid),1.0)
                             ELSE 0.0 END) score
                    FROM valid v
                    WHERE v.exact_title &@~ :query
                       OR ARRAY[COALESCE(v.heading,''),v.content] &@~
                         (:query,ARRAY[2,1],'provisions_search_pgroonga')::pgroonga_full_text_search_condition
                    ORDER BY score DESC,v.ordinal LIMIT :limit"""
                ),
                {
                    "query": query,
                    "as_of": as_of_date,
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
    executed_query: str | None,
    strategy: str,
    relaxed: bool,
) -> tuple[list[SearchHit], SearchTrace]:
    selected: list[SearchHit] = []
    for row in _unique_article_rows(rows):
        selected.append(repository._hit(row))
        if len(selected) == limit:
            break
    return selected, SearchTrace(
        strategy=strategy,
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


def _unique_article_rows(rows: list[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    """Keep the highest-ranked leaf for each document/article pair."""
    selected: list[Mapping[str, Any]] = []
    seen: set[tuple[UUID, str]] = set()
    for row in rows:
        path = str(row["path"])
        root = path.split("/", 1)[0]
        # Flat administrative-rule paragraphs do not represent one legal article.
        article = path if root == "본문" else root
        key = (row["document_id"], article)
        if key in seen:
            continue
        seen.add(key)
        selected.append(row)
    return selected
