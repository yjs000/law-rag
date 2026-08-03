"""현재 법령 조문에 버전 고정 NVIDIA passage 임베딩을 채운다."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from collections.abc import Iterator
from contextlib import asynccontextmanager, contextmanager
from dataclasses import dataclass
from datetime import date
from math import fsum, isfinite, sqrt
from pathlib import Path
from typing import Literal
from uuid import UUID

from law_rag_core.persistence import (
    CORPUS_MUTATION_LOCK_KEY,
    CORPUS_SEARCH_READY_CAPABILITY_KEY,
    CORPUS_SEARCH_READY_CAPABILITY_SQL,
    CORPUS_SEARCH_READY_FLAG_KEY,
    CORPUS_SEARCH_READY_SQL,
    CORPUS_SYNC_RUN_LOCK_KEY,
    EMBEDDING_BACKFILL_LOCK_KEY,
    LEGAL_PROVISION_V1_SOURCE_SHA_SQL,
    SEARCHABLE_DOCUMENT_VERSION_SQL,
)
from openai import APIConnectionError, APIStatusError, APITimeoutError, RateLimitError
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from app.adapters.nvidia_nim_embedder import NvidiaNimEmbedder
from app.adapters.postgres_repository import PostgresLegalRepository
from app.domain.embedding_profiles import (
    NVIDIA_NEMOTRON_512_PROFILE,
    embedding_text_sha256,
    legal_provision_embedding_text,
)
from app.domain.vector_index_contract import (
    NEMOTRON_HNSW_INDEX_NAME,
    NEMOTRON_HNSW_READY_SQL,
)
from app.settings import get_settings


@dataclass(frozen=True, slots=True)
class PendingProvision:
    provision_id: object
    text: str
    source_text_sha256: str


@dataclass(frozen=True, slots=True)
class CachedEmbedding:
    provision_id: str
    source_text_sha256: str
    embedding: list[float]


DEFAULT_CACHE_PATH = (
    Path(__file__).resolve().parents[3]
    / ".data"
    / "embeddings"
    / f"{NVIDIA_NEMOTRON_512_PROFILE.key}.jsonl"
)
# Compatibility aliases for callers and tests that imported the historical names.
_HNSW_INDEX_NAME = NEMOTRON_HNSW_INDEX_NAME
_HNSW_READY_SQL = NEMOTRON_HNSW_READY_SQL


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="운영 corpus의 누락·변경 조문만 NVIDIA passage 임베딩으로 backfill"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("status", help="원문 해시 기준 누락·변경 벡터와 인덱스 상태 확인")
    cache_status = subparsers.add_parser(
        "cache-status", help="DB를 변경하지 않고 로컬 벡터 체크포인트 상태 확인"
    )
    cache_status.add_argument("--cache", type=Path, default=DEFAULT_CACHE_PATH)
    generate_cache = subparsers.add_parser(
        "generate-cache", help="NVIDIA passage 벡터를 재개 가능한 로컬 JSONL에 생성"
    )
    generate_cache.add_argument("--cache", type=Path, default=DEFAULT_CACHE_PATH)
    generate_cache.add_argument("--batch-size", type=int, default=32)
    generate_cache.add_argument("--max-items", type=int)
    generate_cache.add_argument("--max-retries", type=int, default=5)
    generate_cache.add_argument("--retry-base-seconds", type=float, default=2.0)
    load_cache = subparsers.add_parser(
        "load-cache", help="완성된 로컬 체크포인트를 마이그레이션된 DB에 적재"
    )
    load_cache.add_argument("--cache", type=Path, default=DEFAULT_CACHE_PATH)
    load_cache.add_argument("--batch-size", type=int, default=100)
    verify = subparsers.add_parser(
        "verify", help="실제 query 임베딩과 dense-only repository 검색을 검증"
    )
    verify.add_argument("--query", required=True)
    verify.add_argument("--as-of", type=date.fromisoformat, default=date.today())
    verify.add_argument("--limit", type=int, default=3)
    run = subparsers.add_parser("run", help="누락·변경 벡터 생성 후 배치별 upsert")
    run.add_argument("--batch-size", type=int, default=32)
    run.add_argument("--max-items", type=int)
    run.add_argument("--max-retries", type=int, default=5)
    run.add_argument("--retry-base-seconds", type=float, default=2.0)
    return parser.parse_args()


async def _source_provisions(repository: PostgresLegalRepository) -> list[dict]:
    """Read the available active/scheduled corpus without using embedding rows."""
    async with repository.engine.connect() as connection:
        rows = (
            (
                await connection.execute(
                    text(
                        f"""SELECT p.id provision_id,d.exact_title document_title,
                        p.path,p.heading,p.content
                        FROM provisions p
                        JOIN document_versions v ON v.id=p.version_id
                        JOIN legal_documents d ON d.id=v.document_id
                        WHERE {SEARCHABLE_DOCUMENT_VERSION_SQL}
                        ORDER BY d.exact_title,v.effective_from,p.ordinal,p.path"""
                    )
                )
            )
            .mappings()
            .all()
        )
    return [dict(row) for row in rows]


def _source_passages(rows: list[dict]) -> list[PendingProvision]:
    passages: list[PendingProvision] = []
    for row in rows:
        passage = legal_provision_embedding_text(
            document_title=row["document_title"],
            path=row["path"],
            heading=row["heading"],
            content=row["content"],
        )
        passages.append(
            PendingProvision(
                provision_id=row["provision_id"],
                text=passage,
                source_text_sha256=embedding_text_sha256(passage),
            )
        )
    return passages


async def _provisions(repository: PostgresLegalRepository) -> list[dict]:
    async with repository.engine.connect() as connection:
        rows = (
            (
                await connection.execute(
                    text(
                        f"""SELECT p.id provision_id,d.exact_title document_title,
                        p.path,p.heading,p.content,e.source_text_sha256 stored_sha256,
                        e.dimensions stored_dimensions,
                        CASE WHEN e.embedding IS NULL THEN NULL
                             ELSE vector_norm(e.embedding) END stored_norm
                        FROM provisions p
                        JOIN document_versions v ON v.id=p.version_id
                        JOIN legal_documents d ON d.id=v.document_id
                        LEFT JOIN provision_embeddings e
                          ON e.provision_id=p.id AND e.profile_key=:profile_key
                        WHERE {SEARCHABLE_DOCUMENT_VERSION_SQL}
                        ORDER BY d.exact_title,v.effective_from,p.ordinal,p.path"""
                    ),
                    {"profile_key": NVIDIA_NEMOTRON_512_PROFILE.key},
                )
            )
            .mappings()
            .all()
        )
    return [dict(row) for row in rows]


def _pending(rows: list[dict]) -> tuple[list[PendingProvision], int, int]:
    pending: list[PendingProvision] = []
    missing = 0
    stale = 0
    for row in rows:
        passage = legal_provision_embedding_text(
            document_title=row["document_title"],
            path=row["path"],
            heading=row["heading"],
            content=row["content"],
        )
        sha256 = embedding_text_sha256(passage)
        stored_norm = row.get("stored_norm")
        vector_is_current = (
            row["stored_sha256"] == sha256
            and row.get("stored_dimensions") == NVIDIA_NEMOTRON_512_PROFILE.stored_dimensions
            and isinstance(stored_norm, int | float)
            and abs(float(stored_norm) - 1.0) <= 0.0001
        )
        if vector_is_current:
            continue
        if row["stored_sha256"] is None:
            missing += 1
        else:
            stale += 1
        pending.append(PendingProvision(row["provision_id"], passage, sha256))
    return pending, missing, stale


def _validated_vector(value: object) -> list[float]:
    dimensions = NVIDIA_NEMOTRON_512_PROFILE.stored_dimensions
    if not isinstance(value, list) or len(value) != dimensions:
        raise ValueError(f"cache vector must contain {dimensions} dimensions")
    if any(
        isinstance(item, bool) or not isinstance(item, int | float) or not isfinite(item)
        for item in value
    ):
        raise ValueError("cache vector contains a non-finite value")
    vector = [float(item) for item in value]
    norm = sqrt(fsum(item * item for item in vector))
    if abs(norm - 1.0) > 0.0001:
        raise ValueError("cache vector must be L2-normalized")
    return vector


def _read_cache(path: Path) -> tuple[dict[str, CachedEmbedding], int]:
    records: dict[str, CachedEmbedding] = {}
    line_count = 0
    if not path.exists():
        return records, line_count
    ends_with_newline = path.stat().st_size == 0
    if not ends_with_newline:
        with path.open("rb") as binary_stream:
            binary_stream.seek(-1, os.SEEK_END)
            ends_with_newline = binary_stream.read(1) == b"\n"
    with path.open(encoding="utf-8") as stream:
        lines = stream.readlines()
        for line_number, line in enumerate(lines, start=1):
            if not line.strip():
                continue
            line_count += 1
            try:
                payload = json.loads(line)
                if payload.get("profile_key") != NVIDIA_NEMOTRON_512_PROFILE.key:
                    raise ValueError("cache profile does not match the active profile")
                if payload.get("dimensions") != NVIDIA_NEMOTRON_512_PROFILE.stored_dimensions:
                    raise ValueError("cache dimensions do not match the active profile")
                provision_id = str(UUID(payload["provision_id"]))
                source_sha = payload["source_text_sha256"]
                if (
                    not isinstance(source_sha, str)
                    or len(source_sha) != 64
                    or any(character not in "0123456789abcdef" for character in source_sha)
                ):
                    raise ValueError("cache source hash is not a lowercase SHA-256")
                vector = _validated_vector(payload["embedding"])
            except json.JSONDecodeError as exc:
                if line_number == len(lines) and not ends_with_newline:
                    # A process can stop between writing a JSON record and the
                    # batch fsync. The next append truncates this partial tail.
                    line_count -= 1
                    continue
                raise ValueError(f"invalid cache record at line {line_number}: {exc}") from exc
            except (KeyError, TypeError, ValueError) as exc:
                raise ValueError(f"invalid cache record at line {line_number}: {exc}") from exc
            records[provision_id] = CachedEmbedding(provision_id, source_sha, vector)
    return records, line_count


def _cache_pending(
    passages: list[PendingProvision], records: dict[str, CachedEmbedding]
) -> tuple[list[PendingProvision], int, int]:
    pending: list[PendingProvision] = []
    missing = 0
    stale = 0
    for passage in passages:
        record = records.get(str(passage.provision_id))
        if record is not None and record.source_text_sha256 == passage.source_text_sha256:
            continue
        if record is None:
            missing += 1
        else:
            stale += 1
        pending.append(passage)
    return pending, missing, stale


def _reusable_cache_vectors(
    pending: list[PendingProvision], records: dict[str, CachedEmbedding]
) -> tuple[list[PendingProvision], list[list[float]]]:
    """Reuse a vector when only the deterministic provision ID changed."""
    by_source_sha256: dict[str, list[float]] = {}
    for record in sorted(records.values(), key=lambda item: item.provision_id):
        by_source_sha256.setdefault(record.source_text_sha256, record.embedding)

    reusable_passages: list[PendingProvision] = []
    reusable_vectors: list[list[float]] = []
    for passage in pending:
        vector = by_source_sha256.get(passage.source_text_sha256)
        if vector is None:
            continue
        reusable_passages.append(passage)
        reusable_vectors.append(vector)
    return reusable_passages, reusable_vectors


def _cache_batch_values(
    batch: list[PendingProvision], records: dict[str, CachedEmbedding]
) -> list[tuple[UUID, str, list[float]]]:
    values: list[tuple[UUID, str, list[float]]] = []
    for item in batch:
        record = records.get(str(item.provision_id))
        if record is None or record.source_text_sha256 != item.source_text_sha256:
            raise RuntimeError(
                "cache became stale relative to the locked database corpus; regenerate it"
            )
        values.append(
            (
                UUID(str(item.provision_id)),
                item.source_text_sha256,
                record.embedding,
            )
        )
    return values


def _append_cache(path: Path, batch: list[PendingProvision], vectors: list[list[float]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    _prepare_cache_tail_for_append(path)
    with path.open("a", encoding="utf-8", newline="\n") as stream:
        for passage, vector in zip(batch, vectors, strict=True):
            validated = _validated_vector(vector)
            stream.write(
                json.dumps(
                    {
                        "profile_key": NVIDIA_NEMOTRON_512_PROFILE.key,
                        "dimensions": NVIDIA_NEMOTRON_512_PROFILE.stored_dimensions,
                        "provision_id": str(passage.provision_id),
                        "source_text_sha256": passage.source_text_sha256,
                        "embedding": validated,
                    },
                    ensure_ascii=False,
                    separators=(",", ":"),
                )
                + "\n"
            )
        stream.flush()
        os.fsync(stream.fileno())


def _prepare_cache_tail_for_append(path: Path) -> None:
    if not path.exists() or path.stat().st_size == 0:
        return
    with path.open("r+b") as stream:
        stream.seek(-1, os.SEEK_END)
        if stream.read(1) == b"\n":
            return

        end = stream.tell()
        cursor = end
        tail_start = 0
        while cursor > 0:
            chunk_start = max(0, cursor - 65_536)
            stream.seek(chunk_start)
            chunk = stream.read(cursor - chunk_start)
            newline = chunk.rfind(b"\n")
            if newline >= 0:
                tail_start = chunk_start + newline + 1
                break
            cursor = chunk_start
        stream.seek(tail_start)
        tail = stream.read(end - tail_start)
        try:
            json.loads(tail.decode("utf-8"))
        except UnicodeDecodeError, json.JSONDecodeError:
            stream.truncate(tail_start)
        else:
            stream.seek(0, os.SEEK_END)
            stream.write(b"\n")
        stream.flush()
        os.fsync(stream.fileno())


@contextmanager
def _cache_file_lock(path: Path) -> Iterator[None]:
    """Prevent concurrent processes from reading or appending one checkpoint."""
    path.parent.mkdir(parents=True, exist_ok=True)
    lock_path = path.with_name(f"{path.name}.lock")
    stream = lock_path.open("a+b")
    try:
        stream.seek(0, os.SEEK_END)
        if stream.tell() == 0:
            stream.write(b"0")
            stream.flush()
        stream.seek(0)
        try:
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            raise RuntimeError(f"embedding cache is already in use: {path}") from exc
        try:
            yield
        finally:
            stream.seek(0)
            if os.name == "nt":
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)
    finally:
        stream.close()


def _cache_state(
    path: Path,
    passages: list[PendingProvision],
    records: dict[str, CachedEmbedding],
    line_count: int,
) -> dict[str, object]:
    pending, missing, stale = _cache_pending(passages, records)
    current = len(passages) - len(pending)
    return {
        "profile_key": NVIDIA_NEMOTRON_512_PROFILE.key,
        "model": NVIDIA_NEMOTRON_512_PROFILE.model,
        "dimensions": NVIDIA_NEMOTRON_512_PROFILE.stored_dimensions,
        "cache_path": str(path.resolve()),
        "cache_line_count": line_count,
        "provision_count": len(passages),
        "current_count": current,
        "missing_count": missing,
        "stale_count": stale,
        "pending_count": len(pending),
        "complete": not pending,
    }


async def _acquire_corpus_mutation_lock(connection: AsyncConnection) -> None:
    await connection.execute(
        text("SELECT pg_catalog.pg_advisory_xact_lock(:lock_key)"),
        {"lock_key": CORPUS_MUTATION_LOCK_KEY},
    )


async def _acquire_corpus_sync_run_lock(connection: AsyncConnection) -> None:
    await connection.execute(
        text("SELECT pg_catalog.pg_advisory_xact_lock(:lock_key)"),
        {"lock_key": CORPUS_SYNC_RUN_LOCK_KEY},
    )


async def _set_corpus_search_ready(
    connection: AsyncConnection,
    *,
    ready: bool,
    reason: str,
) -> None:
    schema_ready = (
        await connection.execute(text(f"SELECT {CORPUS_SEARCH_READY_CAPABILITY_SQL}"))
    ).scalar_one()
    if not schema_ready:
        raise RuntimeError("database must be migrated to revision 0010 or later")
    await connection.execute(
        text(
            """INSERT INTO runtime_flags(key,value,updated_at)
            VALUES(:key,CAST(:value AS jsonb),now())
            ON CONFLICT(key) DO UPDATE SET value=excluded.value,updated_at=now()"""
        ),
        {
            "key": CORPUS_SEARCH_READY_FLAG_KEY,
            "value": json.dumps({"ready": ready, "reason": reason}),
        },
    )


@asynccontextmanager
async def _embedding_backfill_run_lock(repository: PostgresLegalRepository):
    """Hold a direct-session lock across a complete DB-writing backfill run."""
    async with repository.engine.connect() as connection:
        acquired = (
            await connection.execute(
                text("SELECT pg_try_advisory_lock(:lock_key)"),
                {"lock_key": EMBEDDING_BACKFILL_LOCK_KEY},
            )
        ).scalar_one()
        await connection.commit()
        if not acquired:
            raise RuntimeError("another embedding backfill is already running")
        try:
            yield
        finally:
            await connection.execute(
                text("SELECT pg_advisory_unlock(:lock_key)"),
                {"lock_key": EMBEDDING_BACKFILL_LOCK_KEY},
            )
            await connection.commit()


async def _deactivate_embedding_profile(repository: PostgresLegalRepository) -> None:
    """Commit the fail-closed state before any multi-batch vector write."""
    async with repository.engine.begin() as connection:
        await _acquire_corpus_mutation_lock(connection)
        profile_key = (
            await connection.execute(
                text(
                    """UPDATE embedding_profiles SET active=false
                    WHERE profile_key=:profile_key RETURNING profile_key"""
                ),
                {"profile_key": NVIDIA_NEMOTRON_512_PROFILE.key},
            )
        ).scalar_one_or_none()
        await _set_corpus_search_ready(
            connection,
            ready=False,
            reason="embedding_backfill_started",
        )
    if profile_key is None:
        raise RuntimeError("database does not contain the required embedding profile")


async def _profile_gate_state(connection: AsyncConnection) -> dict[str, object] | None:
    row = (
        (
            await connection.execute(
                text(
                    f"""WITH eligible AS (
                      SELECT p.id provision_id,
                        {LEGAL_PROVISION_V1_SOURCE_SHA_SQL} source_text_sha256
                      FROM provisions p
                      JOIN document_versions v ON v.id=p.version_id
                      JOIN legal_documents d ON d.id=v.document_id
                      WHERE {SEARCHABLE_DOCUMENT_VERSION_SQL}
                    ), coverage AS (
                      SELECT COUNT(*) provision_count,
                        COUNT(e.provision_id) FILTER (
                          WHERE e.source_text_sha256=eligible.source_text_sha256
                            AND e.dimensions=:dimensions
                        ) current_count,
                        COUNT(e.provision_id) FILTER (
                          WHERE e.dimensions<>:dimensions
                        ) wrong_dimensions_count,
                        COUNT(e.provision_id) FILTER (
                          WHERE abs(vector_norm(e.embedding)-1.0)>0.0001
                        ) non_unit_count
                      FROM eligible
                      LEFT JOIN provision_embeddings e
                        ON e.provision_id=eligible.provision_id
                       AND e.profile_key=:profile_key
                    )
                    SELECT ep.active profile_active,ep.provider,ep.model,
                      ep.native_dimensions,ep.stored_dimensions,
                      ep.document_input_type,ep.query_input_type,ep.truncation,
                      ep.normalization,ep.text_template_version,ep.profile_version,
                      coverage.provision_count,coverage.current_count,
                      coverage.wrong_dimensions_count,coverage.non_unit_count,
                      {_HNSW_READY_SQL} hnsw_ready
                    FROM embedding_profiles ep CROSS JOIN coverage
                    WHERE ep.profile_key=:profile_key"""
                ),
                {
                    "profile_key": NVIDIA_NEMOTRON_512_PROFILE.key,
                    "dimensions": NVIDIA_NEMOTRON_512_PROFILE.stored_dimensions,
                },
            )
        )
        .mappings()
        .one_or_none()
    )
    return dict(row) if row is not None else None


def _profile_gate_failure(state: dict[str, object] | None) -> str | None:
    if state is None:
        return "required embedding profile is missing"
    profile = NVIDIA_NEMOTRON_512_PROFILE
    expected_contract = {
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
    }
    if any(state[key] != value for key, value in expected_contract.items()):
        return "embedding profile contract does not match the runtime profile"
    if state["provision_count"] == 0:
        return "eligible corpus is empty"
    if state["current_count"] != state["provision_count"]:
        return "embedding coverage or source hashes are incomplete"
    if state["wrong_dimensions_count"]:
        return "embedding dimensions do not match the active profile"
    if state["non_unit_count"]:
        return "one or more embeddings are not L2-normalized"
    if not state["hnsw_ready"]:
        return "profile HNSW index is not ready"
    return None


async def _promote_embedding_profile(
    repository: PostgresLegalRepository,
) -> dict[str, object]:
    """Atomically verify the complete index and expose it to dense retrieval."""
    failure: str | None = None
    state: dict[str, object] | None = None
    async with repository.engine.begin() as connection:
        # Lock order matches collector: whole-run gate, then per-mutation gate.
        await _acquire_corpus_sync_run_lock(connection)
        await _acquire_corpus_mutation_lock(connection)
        await connection.execute(
            text(
                """UPDATE embedding_profiles SET active=false
                WHERE profile_key=:profile_key"""
            ),
            {"profile_key": NVIDIA_NEMOTRON_512_PROFILE.key},
        )
        await _set_corpus_search_ready(
            connection,
            ready=False,
            reason="embedding_profile_verification",
        )
        state = await _profile_gate_state(connection)
        failure = _profile_gate_failure(state)
        if failure is None:
            await connection.execute(
                text(
                    """UPDATE embedding_profiles SET active=true
                    WHERE profile_key=:profile_key"""
                ),
                {"profile_key": NVIDIA_NEMOTRON_512_PROFILE.key},
            )
            await _set_corpus_search_ready(
                connection,
                ready=True,
                reason="embedding_profile_verified",
            )
            assert state is not None
            state["profile_active"] = True
            state["corpus_search_ready"] = True
    if failure is not None:
        raise RuntimeError(f"embedding profile activation refused: {failure}")
    assert state is not None
    return state


async def _database_state(repository: PostgresLegalRepository) -> dict[str, object]:
    rows = await _provisions(repository)
    pending, missing, stale = _pending(rows)
    async with repository.engine.connect() as connection:
        state = (
            (
                await connection.execute(
                    text(
                        f"""SELECT
                        (SELECT version_num FROM alembic_version LIMIT 1) db_revision,
                        EXISTS(
                          SELECT 1 FROM pg_proc WHERE proname='hybrid_search'
                        ) hybrid_function_exists,
                        {_HNSW_READY_SQL} hnsw_ready,
                        COALESCE((
                          SELECT active FROM embedding_profiles
                          WHERE profile_key=:profile_key
                        ),false) profile_active,
                        {CORPUS_SEARCH_READY_SQL} corpus_search_ready,
                        {CORPUS_SEARCH_READY_CAPABILITY_SQL}
                          corpus_search_capability,
                        (SELECT COUNT(*) FROM provision_embeddings
                          WHERE profile_key=:profile_key) stored_count,
                        (SELECT COUNT(*) FROM provision_embeddings e
                          JOIN provisions p ON p.id=e.provision_id
                          JOIN document_versions v ON v.id=p.version_id
                          WHERE e.profile_key=:profile_key
                            AND {SEARCHABLE_DOCUMENT_VERSION_SQL}
                            AND abs(vector_norm(e.embedding)-1.0)>0.0001
                        ) non_unit_count"""
                    ),
                    {"profile_key": NVIDIA_NEMOTRON_512_PROFILE.key},
                )
            )
            .mappings()
            .one()
        )
    longest = max((len(item.text) for item in pending), default=0)
    return {
        "profile_key": NVIDIA_NEMOTRON_512_PROFILE.key,
        "model": NVIDIA_NEMOTRON_512_PROFILE.model,
        "dimensions": NVIDIA_NEMOTRON_512_PROFILE.stored_dimensions,
        "db_revision": state["db_revision"],
        "provision_count": len(rows),
        "stored_count": state["stored_count"],
        "current_count": len(rows) - len(pending),
        "missing_count": missing,
        "stale_count": stale,
        "pending_count": len(pending),
        "longest_pending_characters": longest,
        "non_unit_vector_count": state["non_unit_count"],
        "hnsw_ready": state["hnsw_ready"],
        "profile_active": state["profile_active"],
        "corpus_search_ready": state["corpus_search_ready"],
        "corpus_search_capability": state["corpus_search_capability"],
        "hybrid_function_exists": state["hybrid_function_exists"],
    }


def _retryable(exc: Exception) -> bool:
    return isinstance(exc, RateLimitError | APIConnectionError | APITimeoutError) or (
        isinstance(exc, APIStatusError) and exc.status_code >= 500
    )


async def _embed_with_retry(
    embedder: NvidiaNimEmbedder,
    passages: list[str],
    *,
    max_retries: int,
    retry_base_seconds: float,
) -> list[list[float]]:
    attempt = 0
    while True:
        try:
            return await embedder.embed(passages)
        except Exception as exc:
            if not _retryable(exc) or attempt >= max_retries:
                raise
            delay = min(retry_base_seconds * (2**attempt), 30.0)
            attempt += 1
            await asyncio.sleep(delay)


def _validate_batch_arguments(arguments: argparse.Namespace) -> None:
    if arguments.batch_size <= 0:
        raise ValueError("batch size must be positive")
    if getattr(arguments, "max_items", None) is not None and arguments.max_items <= 0:
        raise ValueError("max items must be positive")
    if hasattr(arguments, "max_retries") and (
        arguments.max_retries < 0 or arguments.retry_base_seconds <= 0
    ):
        raise ValueError("retry settings must be positive")


def _embedder(
    settings, *, input_type: Literal["query", "passage"] = "passage"
) -> NvidiaNimEmbedder:
    if not settings.nvidia_api_key:
        raise SystemExit("NVIDIA_API_KEY가 필요합니다.")
    return NvidiaNimEmbedder(
        api_key=settings.nvidia_api_key,
        base_url=settings.nvidia_base_url,
        model=NVIDIA_NEMOTRON_512_PROFILE.model,
        dimensions=NVIDIA_NEMOTRON_512_PROFILE.stored_dimensions,
        timeout_seconds=settings.embedding_timeout_seconds,
        input_type=input_type,
    )


async def _generate_cache(
    arguments: argparse.Namespace,
    repository: PostgresLegalRepository,
    settings,
) -> dict[str, object]:
    _validate_batch_arguments(arguments)
    passages = _source_passages(await _source_provisions(repository))
    records, line_count = _read_cache(arguments.cache)
    initial_pending, _, _ = _cache_pending(passages, records)
    reusable_passages, reusable_vectors = _reusable_cache_vectors(initial_pending, records)
    if reusable_passages:
        _append_cache(arguments.cache, reusable_passages, reusable_vectors)
        records, _ = _read_cache(arguments.cache)
        print(
            json.dumps(
                {
                    "event": "cache_vectors_reused",
                    "reused": len(reusable_passages),
                },
                ensure_ascii=False,
            ),
            flush=True,
        )
    pending, _, _ = _cache_pending(passages, records)
    if arguments.max_items is not None:
        pending = pending[: arguments.max_items]
    embedder = _embedder(settings) if pending else None
    generated = 0
    for start in range(0, len(pending), arguments.batch_size):
        batch = pending[start : start + arguments.batch_size]
        assert embedder is not None
        vectors = await _embed_with_retry(
            embedder,
            [item.text for item in batch],
            max_retries=arguments.max_retries,
            retry_base_seconds=arguments.retry_base_seconds,
        )
        _append_cache(arguments.cache, batch, vectors)
        generated += len(batch)
        print(
            json.dumps(
                {
                    "event": "cache_batch_committed",
                    "generated": generated,
                    "selected_target": len(pending),
                },
                ensure_ascii=False,
            ),
            flush=True,
        )
    final_records, final_line_count = _read_cache(arguments.cache)
    return {
        "generated_count": generated,
        "reused_count": len(reusable_passages),
        "initial_cache_line_count": line_count,
        "state": _cache_state(arguments.cache, passages, final_records, final_line_count),
    }


async def _load_cache(
    arguments: argparse.Namespace, repository: PostgresLegalRepository
) -> dict[str, object]:
    _validate_batch_arguments(arguments)
    async with repository.engine.connect() as connection:
        schema_ready = (
            await connection.execute(
                text(
                    """SELECT to_regclass('embedding_profiles') IS NOT NULL
                    AND to_regclass('provision_embeddings') IS NOT NULL
                    AND EXISTS(
                      SELECT 1 FROM information_schema.columns
                      WHERE table_name='document_versions'
                        AND column_name='source_record_state'
                    )
                    AND EXISTS(
                      SELECT 1 FROM runtime_flags
                      WHERE key=:corpus_capability_key
                        AND value->>'enabled'='true'
                    )"""
                ),
                {"corpus_capability_key": CORPUS_SEARCH_READY_CAPABILITY_KEY},
            )
        ).scalar_one()
        if not schema_ready:
            raise RuntimeError("database must be migrated to revision 0010 or later")
    passages = _source_passages(await _source_provisions(repository))
    records, line_count = _read_cache(arguments.cache)
    state = _cache_state(arguments.cache, passages, records, line_count)
    if not state["complete"]:
        raise RuntimeError("cache is incomplete or stale; generate it before loading")

    await _deactivate_embedding_profile(repository)
    pending, _, _ = _pending(await _provisions(repository))
    loaded = 0
    for start in range(0, len(pending), arguments.batch_size):
        batch = pending[start : start + arguments.batch_size]
        await repository.upsert_embeddings(
            _cache_batch_values(batch, records),
            NVIDIA_NEMOTRON_512_PROFILE.key,
            NVIDIA_NEMOTRON_512_PROFILE.stored_dimensions,
        )
        loaded += len(batch)
        print(
            json.dumps(
                {"event": "db_batch_committed", "loaded": loaded, "target": len(pending)},
                ensure_ascii=False,
            ),
            flush=True,
        )
    await _promote_embedding_profile(repository)
    return {"loaded_count": loaded, "state": await _database_state(repository)}


async def _verify_dense_search(
    arguments: argparse.Namespace,
    repository: PostgresLegalRepository,
    settings,
) -> dict[str, object]:
    query = arguments.query.strip()
    if not query:
        raise ValueError("query must not be empty")
    if arguments.limit < 1 or arguments.limit > 20:
        raise ValueError("limit must be between 1 and 20")
    state = await _database_state(repository)
    if (
        state["pending_count"]
        or not state["hnsw_ready"]
        or not state["profile_active"]
        or not state["corpus_search_capability"]
        or not state["corpus_search_ready"]
    ):
        raise RuntimeError("dense index is not ready for verification")
    vector = (
        await _embedder(settings, input_type=NVIDIA_NEMOTRON_512_PROFILE.query_input_type).embed(
            [query]
        )
    )[0]
    hits, trace = await repository.search_with_trace(
        query,
        arguments.as_of,
        arguments.limit,
        vector,
        NVIDIA_NEMOTRON_512_PROFILE.key,
    )
    if trace.strategy != "dense_only":
        raise RuntimeError(f"unexpected retrieval strategy: {trace.strategy}")
    return {
        "query": query,
        "as_of_date": arguments.as_of.isoformat(),
        "profile_key": NVIDIA_NEMOTRON_512_PROFILE.key,
        "query_dimensions": len(vector),
        "retrieval_strategy": trace.strategy,
        "candidate_count": trace.candidate_count,
        "hnsw_ready": state["hnsw_ready"],
        "profile_active": state["profile_active"],
        "corpus_search_capability": state["corpus_search_capability"],
        "corpus_search_ready": state["corpus_search_ready"],
        "hybrid_function_exists": state["hybrid_function_exists"],
        "results": [
            {
                "rank": rank,
                "document_title": hit.document_title,
                "path": hit.path,
                "heading": hit.heading,
                "score": hit.score,
            }
            for rank, hit in enumerate(hits, start=1)
        ],
    }


async def _backfill_database(
    arguments: argparse.Namespace,
    repository: PostgresLegalRepository,
    settings,
) -> dict[str, object]:
    _validate_batch_arguments(arguments)
    await _deactivate_embedding_profile(repository)
    rows = await _provisions(repository)
    pending, _, _ = _pending(rows)
    if arguments.max_items is not None:
        pending = pending[: arguments.max_items]
    embedder = _embedder(settings) if pending else None
    generated = 0
    for start in range(0, len(pending), arguments.batch_size):
        batch = pending[start : start + arguments.batch_size]
        assert embedder is not None
        vectors = await _embed_with_retry(
            embedder,
            [item.text for item in batch],
            max_retries=arguments.max_retries,
            retry_base_seconds=arguments.retry_base_seconds,
        )
        await repository.upsert_embeddings(
            [
                (item.provision_id, item.source_text_sha256, vector)
                for item, vector in zip(batch, vectors, strict=True)
            ],
            NVIDIA_NEMOTRON_512_PROFILE.key,
            NVIDIA_NEMOTRON_512_PROFILE.stored_dimensions,
        )
        generated += len(batch)
        print(
            json.dumps(
                {"event": "batch_committed", "generated": generated, "target": len(pending)},
                ensure_ascii=False,
            ),
            flush=True,
        )
    await _promote_embedding_profile(repository)
    final = await _database_state(repository)
    return {"generated_count": generated, "state": final}


async def _run(arguments: argparse.Namespace) -> dict[str, object]:
    settings = get_settings()
    database_url = settings.database_url or settings.direct_url
    if not database_url:
        raise SystemExit("DATABASE_URL이 필요합니다.")
    writes_database = arguments.command in {"load-cache", "run"}
    if writes_database and not settings.direct_url:
        raise SystemExit("load-cache와 run에는 session-mode DIRECT_URL이 필요합니다.")
    repository = PostgresLegalRepository(settings.direct_url if writes_database else database_url)
    try:
        if arguments.command == "status":
            return await _database_state(repository)
        if arguments.command == "verify":
            return await _verify_dense_search(arguments, repository, settings)
        if arguments.command in {"cache-status", "generate-cache", "load-cache"}:
            passages = _source_passages(await _source_provisions(repository))
            if arguments.command == "cache-status":
                records, line_count = _read_cache(arguments.cache)
                return _cache_state(arguments.cache, passages, records, line_count)
            if arguments.command == "generate-cache":
                with _cache_file_lock(arguments.cache):
                    return await _generate_cache(arguments, repository, settings)
            with _cache_file_lock(arguments.cache):
                async with _embedding_backfill_run_lock(repository):
                    return await _load_cache(arguments, repository)

        async with _embedding_backfill_run_lock(repository):
            return await _backfill_database(arguments, repository, settings)
    finally:
        await repository.engine.dispose()


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    result = asyncio.run(_run(_arguments()))
    print(json.dumps(result, ensure_ascii=False, indent=2))
