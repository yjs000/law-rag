"""Publish one validated local corpus bundle during a bounded maintenance window."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Awaitable, Callable, Mapping, Sequence
from contextlib import AbstractAsyncContextManager
from datetime import datetime, timedelta, timezone
from math import fsum
from pathlib import Path
from uuid import UUID

from law_rag_core.corpus_update_bundle import (
    CorpusUpdateBundle,
    PreparedEmbeddingRecord,
    canonical_corpus_publish_snapshot_id,
    embedding_text_sha256,
    legal_provision_v1_text,
    load_corpus_update_bundle,
)
from law_rag_core.domain.identifiers import PARSER_SCHEMA_VERSION
from law_rag_core.persistence import (
    CORPUS_MUTATION_LOCK_KEY,
    CORPUS_PUBLISH_BASE_SELECT_SQL,
    CORPUS_SEARCH_READY_CAPABILITY_SQL,
    CORPUS_SEARCH_READY_FLAG_KEY,
    LEGAL_PROVISION_V1_SOURCE_SHA_SQL,
    SEARCHABLE_DOCUMENT_VERSION_SQL,
)
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from law_rag_collector.client import RawResponse
from law_rag_collector.deletions import DeletionRecord
from law_rag_collector.supabase_repository import (
    SupabaseCurrentCorpusRepository,
    _set_corpus_search_ready,
    raw_object_path,
)

DEFAULT_DRAIN_SECONDS = 65.0
PUBLISH_BATCH_SIZE = 100
SEOUL_TIME_ZONE = timezone(timedelta(hours=9), name="Asia/Seoul")
EXPECTED_PROFILE = {
    "provider": "nvidia",
    "model": "nvidia/nemotron-3-embed-1b",
    "native_dimensions": 2048,
    "stored_dimensions": 512,
    "document_input_type": "passage",
    "query_input_type": "query",
    "truncation": "first_512",
    "normalization": "l2",
    "text_template_version": "legal-provision-v1",
    "profile_version": "1",
}
EXPECTED_PROFILE_KEY = "nvidia-nemotron-3-embed-1b-512-v1"

SnapshotReader = Callable[[AsyncConnection, str], Awaitable[str]]
Sleeper = Callable[[float], Awaitable[None]]


class _BoundTransactionContext(AbstractAsyncContextManager[AsyncConnection]):
    """Let legacy writer methods join the publisher's already-open transaction."""

    def __init__(self, connection: AsyncConnection) -> None:
        self.connection = connection

    async def __aenter__(self) -> AsyncConnection:
        return self.connection

    async def __aexit__(self, *_: object) -> None:
        return None


class _BoundEngine:
    def __init__(self, connection: AsyncConnection) -> None:
        self.connection = connection

    def begin(self) -> _BoundTransactionContext:
        return _BoundTransactionContext(self.connection)


class _UploadedRawStorage:
    """Resolve pre-uploaded immutable objects without network I/O inside Tx B."""

    def __init__(self, paths: Mapping[str, str]) -> None:
        self.paths = dict(paths)

    async def put_immutable(self, path: str, _raw: RawResponse) -> str:
        try:
            return self.paths[path]
        except KeyError as exc:
            raise RuntimeError(f"prepared raw was not uploaded: {path}") from exc

    async def close(self) -> None:
        return None


async def current_corpus_snapshot_id(
    connection: AsyncConnection,
    parser_version: str,
) -> str:
    """Read the same current 11-field population identity used during preparation."""

    if parser_version != PARSER_SCHEMA_VERSION:
        raise RuntimeError("bundle parser version does not match the runtime parser")
    capability_ready = (
        await connection.execute(text(f"SELECT {CORPUS_SEARCH_READY_CAPABILITY_SQL}"))
    ).scalar_one()
    if not capability_ready:
        raise RuntimeError("corpus search readiness capability is unavailable")
    rows = (
        (
            await connection.execute(
                text(
                    f"""SELECT {CORPUS_PUBLISH_BASE_SELECT_SQL}
                    FROM provisions p
                    JOIN document_versions v ON v.id=p.version_id
                    JOIN legal_documents d ON d.id=v.document_id
                    WHERE {SEARCHABLE_DOCUMENT_VERSION_SQL}
                    ORDER BY p.id"""
                )
            )
        )
        .mappings()
        .all()
    )
    if not rows:
        raise RuntimeError("current corpus contains no searchable provisions")
    return canonical_corpus_publish_snapshot_id(rows)


async def _require_publishable_gate(connection: AsyncConnection) -> None:
    row = (
        (
            await connection.execute(
                text(
                    f"""SELECT {CORPUS_SEARCH_READY_CAPABILITY_SQL} capability_ready,
                    COALESCE((SELECT (value->>'ready')::boolean FROM runtime_flags
                              WHERE key=:gate_key),false) ready,
                    COALESCE((SELECT value->>'reason' FROM runtime_flags
                              WHERE key=:gate_key),'runtime_flag_missing') reason"""
                ),
                {"gate_key": CORPUS_SEARCH_READY_FLAG_KEY},
            )
        )
        .mappings()
        .one()
    )
    if not bool(row["capability_ready"]):
        raise RuntimeError("corpus search readiness capability is unavailable")
    if not bool(row["ready"]) and row["reason"] != "corpus_publish":
        raise RuntimeError(f"corpus gate is closed for another reason: {row['reason']}")


def _embedding_source_sha256(
    *, document_title: str, path: str, heading: str | None, content: str
) -> str:
    return embedding_text_sha256(
        legal_provision_v1_text(
            document_title=document_title,
            path=path,
            heading=heading,
            content=content,
        )
    )


async def _require_complete_prospective_embeddings(
    connection: AsyncConnection,
    bundle: CorpusUpdateBundle,
) -> None:
    """Fail before maintenance unless the bundle closes every prospective vector gap."""

    stored_rows = (
        (
            await connection.execute(
                text(
                    f"""SELECT p.id provision_id,d.source_kind,d.source_id,v.mst,
                    v.effective_from,d.exact_title document_title,p.path,p.heading,p.content,
                    e.source_text_sha256 stored_sha256,e.dimensions stored_dimensions,
                    CASE WHEN e.embedding IS NULL THEN NULL
                         ELSE vector_norm(e.embedding) END stored_norm
                    FROM provisions p
                    JOIN document_versions v ON v.id=p.version_id
                    JOIN legal_documents d ON d.id=v.document_id
                    LEFT JOIN provision_embeddings e
                      ON e.provision_id=p.id AND e.profile_key=:profile_key
                    WHERE {SEARCHABLE_DOCUMENT_VERSION_SQL}
                    ORDER BY p.id"""
                ),
                {"profile_key": bundle.manifest.embedding_profile_key},
            )
        )
        .mappings()
        .all()
    )
    bundle_versions = {
        (
            item.source_kind.value,
            item.source_id,
            item.mst,
            item.effective_from,
        )
        for item in bundle.documents
    }
    titles = {
        (item.source_kind.value, item.source_id): item.title for item in bundle.documents
    }
    deleted_versions = {
        (item.source_kind.value, item.mst) for item in bundle.deletions if item.changed
    }
    vector_state = {UUID(str(row["provision_id"])): row for row in stored_rows}
    prospective: dict[UUID, tuple[str, str, str | None, str]] = {}
    for row in stored_rows:
        source_kind = str(row["source_kind"])
        source_id = str(row["source_id"])
        mst = str(row["mst"])
        if (source_kind, mst) in deleted_versions:
            continue
        if (
            source_kind,
            source_id,
            mst,
            row["effective_from"],
        ) in bundle_versions:
            continue
        provision_id = UUID(str(row["provision_id"]))
        prospective[provision_id] = (
            titles.get((source_kind, source_id), str(row["document_title"])),
            str(row["path"]),
            None if row["heading"] is None else str(row["heading"]),
            str(row["content"]),
        )
    for document in bundle.documents:
        if (document.source_kind.value, document.mst) in deleted_versions:
            continue
        for provision in document.provisions:
            prospective[provision.id] = (
                document.title,
                provision.path,
                provision.heading,
                provision.content,
            )

    prepared = {item.provision_id: item for item in bundle.embeddings}
    expected_hashes: dict[UUID, str] = {}
    for provision_id, (title, path, heading, content) in prospective.items():
        expected_sha = _embedding_source_sha256(
            document_title=title,
            path=path,
            heading=heading,
            content=content,
        )
        expected_hashes[provision_id] = expected_sha
        existing = vector_state.get(provision_id)
        existing_valid = bool(
            existing is not None
            and existing["stored_sha256"] == expected_sha
            and existing["stored_dimensions"] == 512
            and existing["stored_norm"] is not None
            and abs(float(existing["stored_norm"]) - 1.0) <= 1e-5
        )
        if existing_valid:
            continue
        replacement = prepared.get(provision_id)
        if replacement is None or replacement.source_text_sha256 != expected_sha:
            raise RuntimeError("prepared bundle does not cover prospective embedding gaps")

    prepared_ids = set(prepared)
    if set(bundle.manifest.changes.required_embedding_ids) != prepared_ids:
        raise RuntimeError("bundle required embedding IDs do not match prepared records")
    if any(
        provision_id not in expected_hashes
        or prepared[provision_id].source_text_sha256 != expected_hashes[provision_id]
        for provision_id in prepared_ids
    ):
        raise RuntimeError("prepared bundle contains extra or stale embedding records")


def _raw_response(bundle: CorpusUpdateBundle, document) -> RawResponse:
    return RawResponse(
        body=bundle.raw_body(document),
        wire_format=document.raw.wire_format,
        source_url=document.raw.source_url,
        fallback_reason=document.raw.fallback_reason,
    )


async def _upload_changed_raws(
    repository: SupabaseCurrentCorpusRepository,
    bundle: CorpusUpdateBundle,
) -> dict[str, str]:
    uploaded: dict[str, str] = {}
    for document in bundle.documents:
        if not document.changed:
            continue
        raw = _raw_response(bundle, document)
        path = raw_object_path(document.to_legal_document_record(), raw)
        uploaded[path] = await repository.storage.put_immutable(path, raw)
    return uploaded


def _transaction_repository(
    repository: SupabaseCurrentCorpusRepository,
    connection: AsyncConnection,
    uploaded_paths: Mapping[str, str],
) -> SupabaseCurrentCorpusRepository:
    return SupabaseCurrentCorpusRepository(
        database_url="postgresql://prepared-publish.invalid",
        supabase_url="https://prepared-publish.invalid",
        supabase_secret_key="unused",
        bucket=repository.bucket,
        engine=_BoundEngine(connection),  # type: ignore[arg-type]
        storage=_UploadedRawStorage(uploaded_paths),  # type: ignore[arg-type]
    )


def _chunks[T](values: Sequence[T], size: int = PUBLISH_BATCH_SIZE) -> list[Sequence[T]]:
    return [values[start : start + size] for start in range(0, len(values), size)]


async def _upsert_embedding_batch(
    connection: AsyncConnection,
    embeddings: Sequence[PreparedEmbeddingRecord],
) -> None:
    if not embeddings:
        return
    await connection.execute(
        text(
            """INSERT INTO provision_embeddings(
            provision_id,profile_key,dimensions,source_text_sha256,embedding,embedded_at)
            VALUES(:provision_id,:profile_key,:dimensions,:source_text_sha256,
                   CAST(:embedding AS vector),now())
            ON CONFLICT(provision_id,profile_key) DO UPDATE SET
            dimensions=excluded.dimensions,
            source_text_sha256=excluded.source_text_sha256,
            embedding=excluded.embedding,embedded_at=now()"""
        ),
        [
            {
                "provision_id": item.provision_id,
                "profile_key": item.embedding_profile_key,
                "dimensions": item.dimensions,
                "source_text_sha256": item.source_text_sha256,
                "embedding": json.dumps(item.embedding, separators=(",", ":")),
            }
            for item in embeddings
        ],
    )


async def _verify_publish_state(
    connection: AsyncConnection,
    bundle: CorpusUpdateBundle,
) -> dict[str, object]:
    temporal = (
        (
            await connection.execute(
                text(
                    """WITH candidate_versions AS MATERIALIZED (
                    SELECT id,document_id,effective_from,effective_to,parser_schema_version
                    FROM document_versions
                    WHERE source_record_state='available'
                      AND (lifecycle_state IN ('active','scheduled')
                           OR (lifecycle_state='abolished' AND effective_to IS NOT NULL))
                    ), overlap_pairs AS (
                    SELECT COUNT(*)::bigint overlap_count
                    FROM candidate_versions left_version
                    JOIN candidate_versions right_version
                      ON right_version.document_id=left_version.document_id
                     AND right_version.id>left_version.id
                     AND left_version.effective_from
                         < COALESCE(right_version.effective_to,'infinity'::date)
                     AND right_version.effective_from
                         < COALESCE(left_version.effective_to,'infinity'::date)
                    ), current_population AS (
                    SELECT COUNT(p.id)::bigint provision_count,
                           MIN(v.effective_from) supported_from
                    FROM candidate_versions v
                    JOIN provisions p ON p.version_id=v.id
                    WHERE v.effective_from<=:today
                      AND (v.effective_to IS NULL OR v.effective_to>:today)
                    )
                    SELECT COUNT(*) FILTER (
                      WHERE effective_from IS NULL
                         OR (effective_to IS NOT NULL AND effective_to<=effective_from)
                    )::bigint invalid_period_count,
                    COUNT(*) FILTER (
                      WHERE parser_schema_version<>:parser_version
                    )::bigint parser_mismatch_count,
                    (SELECT COUNT(*) FROM (
                      SELECT document_id FROM candidate_versions
                      WHERE effective_to IS NULL GROUP BY document_id HAVING COUNT(*)>1
                    ) duplicate_open)::bigint duplicate_open_count,
                    (SELECT overlap_count FROM overlap_pairs)::bigint overlap_count
                    ,(SELECT provision_count FROM current_population)::bigint
                      current_eligible_provision_count
                    ,(SELECT supported_from FROM current_population) supported_from
                    FROM candidate_versions"""
                ),
                {
                    "parser_version": bundle.manifest.parser_version,
                    "today": datetime.now(SEOUL_TIME_ZONE).date(),
                },
            )
        )
        .mappings()
        .one()
    )
    if any(
        int(temporal[field])
        for field in (
            "invalid_period_count",
            "parser_mismatch_count",
            "duplicate_open_count",
            "overlap_count",
        )
    ):
        raise RuntimeError("corpus temporal or parser contract is invalid")
    if (
        int(temporal["current_eligible_provision_count"]) <= 0
        or temporal["supported_from"] is None
    ):
        raise RuntimeError("published corpus has no currently eligible provisions")

    profile = (
        (
            await connection.execute(
                text(
                    f"""WITH coverage AS (
                    SELECT COUNT(*)::bigint provision_count,
                      COUNT(e.provision_id)::bigint current_count,
                      COUNT(*) FILTER (
                        WHERE e.provision_id IS NOT NULL
                          AND (e.dimensions<>512 OR abs(vector_norm(e.embedding)-1.0)>1e-5)
                      )::bigint invalid_vector_count,
                      COUNT(*) FILTER (
                        WHERE e.provision_id IS NOT NULL
                          AND e.source_text_sha256<>{LEGAL_PROVISION_V1_SOURCE_SHA_SQL}
                      )::bigint stale_hash_count
                    FROM provisions p
                    JOIN document_versions v ON v.id=p.version_id
                    JOIN legal_documents d ON d.id=v.document_id
                    LEFT JOIN provision_embeddings e
                      ON e.provision_id=p.id AND e.profile_key=:profile_key
                    WHERE {SEARCHABLE_DOCUMENT_VERSION_SQL}
                    )
                    SELECT ep.provider,ep.model,ep.native_dimensions,ep.stored_dimensions,
                    ep.document_input_type,ep.query_input_type,ep.truncation,
                    ep.normalization,ep.text_template_version,ep.profile_version,
                    coverage.*
                    FROM embedding_profiles ep CROSS JOIN coverage
                    WHERE ep.profile_key=:profile_key"""
                ),
                {"profile_key": bundle.manifest.embedding_profile_key},
            )
        )
        .mappings()
        .one_or_none()
    )
    if profile is None:
        raise RuntimeError("prepared embedding profile is missing")
    for field, expected in EXPECTED_PROFILE.items():
        if profile[field] != expected:
            raise RuntimeError(f"embedding profile contract mismatch: {field}")
    provision_count = int(profile["provision_count"])
    current_count = int(profile["current_count"])
    if provision_count == 0 or current_count != provision_count:
        raise RuntimeError("embedding coverage is incomplete after prepared publish")
    if int(profile["invalid_vector_count"]) or int(profile["stale_hash_count"]):
        raise RuntimeError("prepared publish contains invalid or stale embeddings")

    changed_documents = [item for item in bundle.documents if item.changed]
    for document in changed_documents:
        persisted_sha = (
            await connection.execute(
                text(
                    """SELECT v.raw_sha256 FROM document_versions v
                    JOIN legal_documents d ON d.id=v.document_id
                    WHERE d.source_kind=:source_kind AND d.source_id=:source_id
                      AND v.mst=:mst AND v.effective_from=:effective_from"""
                ),
                {
                    "source_kind": document.source_kind.value,
                    "source_id": document.source_id,
                    "mst": document.mst,
                    "effective_from": document.effective_from,
                },
            )
        ).scalar_one_or_none()
        if persisted_sha != document.raw_sha256:
            raise RuntimeError("prepared document SHA was not persisted")
    return {
        "provision_count": provision_count,
        "embedding_count": current_count,
        "changed_document_count": len(changed_documents),
        "changed_deletion_count": bundle.manifest.counts.changed_deletions,
    }


async def _apply_prepared_transaction(
    connection: AsyncConnection,
    repository: SupabaseCurrentCorpusRepository,
    bundle: CorpusUpdateBundle,
    uploaded_paths: Mapping[str, str],
) -> dict[str, object]:
    transactional = _transaction_repository(repository, connection, uploaded_paths)
    for prepared in bundle.documents:
        if not prepared.changed:
            continue
        changed = await transactional.upsert(
            prepared.to_legal_document_record(),
            _raw_response(bundle, prepared),
            effective_to=prepared.effective_to,
            batch_size=PUBLISH_BATCH_SIZE,
        )
        if not changed:
            raise RuntimeError("prepared document no longer changes the locked corpus")

    changed_deletions = [item for item in bundle.deletions if item.changed]
    await transactional.apply_source_deletions(
        [
            DeletionRecord(
                mst=item.mst,
                source_kind=item.source_kind,
                kind_name=item.kind_name,
                deleted_on=item.deleted_on,
            )
            for item in changed_deletions
        ],
        completed_on=bundle.manifest.deletion_window_to,
    )

    await connection.execute(
        text("UPDATE embedding_profiles SET active=false WHERE active")
    )
    for batch in _chunks(bundle.embeddings):
        await _upsert_embedding_batch(connection, batch)
    state = await _verify_publish_state(connection, bundle)
    activated = (
        await connection.execute(
            text(
                """UPDATE embedding_profiles SET active=true
                WHERE profile_key=:profile_key RETURNING profile_key"""
            ),
            {"profile_key": bundle.manifest.embedding_profile_key},
        )
    ).scalar_one_or_none()
    if activated is None:
        raise RuntimeError("prepared embedding profile could not be activated")
    await connection.execute(
        text(
            """INSERT INTO ingestion_runs(completed_at,state,stats,error_code)
            VALUES(now(),'completed',CAST(:stats AS jsonb),NULL)"""
        ),
        {
            "stats": json.dumps(
                {
                    "command": "apply-prepared",
                    "update_id": bundle.manifest.update_id,
                    **state,
                },
                ensure_ascii=False,
            )
        },
    )
    await _set_corpus_search_ready(
        connection,
        ready=True,
        reason="corpus_publish_verified",
        update_id=bundle.manifest.update_id,
    )
    return state


async def publish_prepared_bundle(
    repository: SupabaseCurrentCorpusRepository,
    bundle_path: Path,
    *,
    drain_seconds: float = DEFAULT_DRAIN_SECONDS,
    sleeper: Sleeper = asyncio.sleep,
    snapshot_reader: SnapshotReader = current_corpus_snapshot_id,
) -> dict[str, object]:
    """Validate, gate, drain and atomically publish a prepared corpus update."""

    if drain_seconds < 0:
        raise ValueError("drain seconds cannot be negative")
    bundle = load_corpus_update_bundle(bundle_path)
    if bundle.manifest.state == "unchanged":
        return {
            "update_id": bundle.manifest.update_id,
            "state": "unchanged",
            "published": False,
        }
    if bundle.manifest.state != "ready_to_publish":
        raise ValueError("bundle must be ready_to_publish before publication")
    if bundle.manifest.parser_version != PARSER_SCHEMA_VERSION:
        raise ValueError("bundle parser version does not match the runtime parser")
    if bundle.manifest.embedding_profile_key != EXPECTED_PROFILE_KEY:
        raise ValueError("bundle embedding profile does not match the runtime profile")
    required_ids = set(bundle.manifest.changes.required_embedding_ids)
    embedding_ids = {item.provision_id for item in bundle.embeddings}
    if not required_ids.issubset(embedding_ids):
        raise ValueError("bundle is missing required prepared embeddings")
    for item in bundle.embeddings:
        if item.embedding_profile_key != EXPECTED_PROFILE_KEY or item.dimensions != 512:
            raise ValueError("prepared embeddings do not match the 512D runtime profile")
        squared_norm = fsum(value * value for value in item.embedding)
        if abs(squared_norm - 1.0) > 2e-5:
            raise ValueError("prepared embeddings must be L2-normalized")

    uploaded_paths = await _upload_changed_raws(repository, bundle)
    async with repository.prepared_publish_session() as connection:
        await _require_publishable_gate(connection)
        current_snapshot = await snapshot_reader(
            connection,
            bundle.manifest.parser_version,
        )
        if current_snapshot != bundle.manifest.base_snapshot_id:
            raise RuntimeError("prepared bundle base snapshot no longer matches the database")
        await _require_complete_prospective_embeddings(connection, bundle)
        # The read above starts SQLAlchemy's implicit transaction. End it before Tx A.
        await connection.commit()

        async with connection.begin():
            await connection.execute(
                text("SELECT pg_advisory_xact_lock(:lock_key)"),
                {"lock_key": CORPUS_MUTATION_LOCK_KEY},
            )
            current_snapshot = await snapshot_reader(
                connection,
                bundle.manifest.parser_version,
            )
            if current_snapshot != bundle.manifest.base_snapshot_id:
                raise RuntimeError("prepared bundle base snapshot changed before maintenance")
            await _require_publishable_gate(connection)
            await _set_corpus_search_ready(
                connection,
                ready=False,
                reason="corpus_publish",
                update_id=bundle.manifest.update_id,
            )

        await sleeper(drain_seconds)

        async with connection.begin():
            await connection.execute(
                text("SELECT pg_advisory_xact_lock(:lock_key)"),
                {"lock_key": CORPUS_MUTATION_LOCK_KEY},
            )
            state = await _apply_prepared_transaction(
                connection,
                repository,
                bundle,
                uploaded_paths,
            )

    return {
        "update_id": bundle.manifest.update_id,
        "state": "published",
        "published": True,
        "drain_seconds": drain_seconds,
        **state,
    }


__all__ = [
    "DEFAULT_DRAIN_SECONDS",
    "PUBLISH_BATCH_SIZE",
    "current_corpus_snapshot_id",
    "publish_prepared_bundle",
]
