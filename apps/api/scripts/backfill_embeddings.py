"""현재 법령 조문에 버전 고정 NVIDIA passage 임베딩을 채운다."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from dataclasses import dataclass
from math import fsum, isfinite, sqrt
from pathlib import Path
from uuid import UUID

from openai import APIConnectionError, APIStatusError, APITimeoutError, RateLimitError
from sqlalchemy import text

from app.adapters.nvidia_nim_embedder import NvidiaNimEmbedder
from app.adapters.postgres_repository import PostgresLegalRepository
from app.domain.embedding_profiles import (
    NVIDIA_NEMOTRON_512_PROFILE,
    embedding_text_sha256,
    legal_provision_embedding_text,
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
    run = subparsers.add_parser("run", help="누락·변경 벡터 생성 후 배치별 upsert")
    run.add_argument("--batch-size", type=int, default=32)
    run.add_argument("--max-items", type=int)
    run.add_argument("--max-retries", type=int, default=5)
    run.add_argument("--retry-base-seconds", type=float, default=2.0)
    return parser.parse_args()


async def _source_provisions(repository: PostgresLegalRepository) -> list[dict]:
    """Read embedding inputs without depending on the post-0008 embedding schema."""
    async with repository.engine.connect() as connection:
        rows = (
            (
                await connection.execute(
                    text(
                        """SELECT p.id provision_id,d.exact_title document_title,
                        p.path,p.heading,p.content
                        FROM provisions p
                        JOIN document_versions v ON v.id=p.version_id
                        JOIN legal_documents d ON d.id=v.document_id
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
                        """SELECT p.id provision_id,d.exact_title document_title,
                        p.path,p.heading,p.content,e.source_text_sha256 stored_sha256
                        FROM provisions p
                        JOIN document_versions v ON v.id=p.version_id
                        JOIN legal_documents d ON d.id=v.document_id
                        LEFT JOIN provision_embeddings e
                          ON e.provision_id=p.id AND e.profile_key=:profile_key
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
        if row["stored_sha256"] == sha256:
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
        isinstance(item, bool)
        or not isinstance(item, int | float)
        or not isfinite(item)
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
    with path.open(encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, start=1):
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
            except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
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


def _append_cache(
    path: Path, batch: list[PendingProvision], vectors: list[list[float]]
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
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


async def _database_state(repository: PostgresLegalRepository) -> dict[str, object]:
    rows = await _provisions(repository)
    pending, missing, stale = _pending(rows)
    async with repository.engine.connect() as connection:
        state = (
            (
                await connection.execute(
                    text(
                        """SELECT
                        (SELECT version_num FROM alembic_version LIMIT 1) db_revision,
                        EXISTS(
                          SELECT 1 FROM pg_proc WHERE proname='hybrid_search'
                        ) hybrid_function_exists,
                        EXISTS(
                          SELECT 1 FROM pg_class c JOIN pg_index i ON i.indexrelid=c.oid
                          WHERE c.relname='provision_embeddings_nemotron_512_hnsw'
                            AND i.indisvalid AND i.indisready
                        ) hnsw_ready,
                        (SELECT COUNT(*) FROM provision_embeddings
                          WHERE profile_key=:profile_key) stored_count,
                        (SELECT COUNT(*) FROM provision_embeddings
                          WHERE profile_key=:profile_key
                            AND abs(vector_norm(embedding)-1.0)>0.0001) non_unit_count"""
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


def _embedder(settings) -> NvidiaNimEmbedder:
    if not settings.nvidia_api_key:
        raise SystemExit("NVIDIA_API_KEY가 필요합니다.")
    return NvidiaNimEmbedder(
        api_key=settings.nvidia_api_key,
        base_url=settings.nvidia_base_url,
        model=NVIDIA_NEMOTRON_512_PROFILE.model,
        dimensions=NVIDIA_NEMOTRON_512_PROFILE.stored_dimensions,
        timeout_seconds=settings.embedding_timeout_seconds,
        input_type=NVIDIA_NEMOTRON_512_PROFILE.document_input_type,
    )


async def _generate_cache(
    arguments: argparse.Namespace,
    repository: PostgresLegalRepository,
    settings,
) -> dict[str, object]:
    _validate_batch_arguments(arguments)
    passages = _source_passages(await _source_provisions(repository))
    records, line_count = _read_cache(arguments.cache)
    pending, _, _ = _cache_pending(passages, records)
    if arguments.max_items is not None:
        pending = pending[: arguments.max_items]
    embedder = _embedder(settings)
    generated = 0
    for start in range(0, len(pending), arguments.batch_size):
        batch = pending[start : start + arguments.batch_size]
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
        "initial_cache_line_count": line_count,
        "state": _cache_state(
            arguments.cache, passages, final_records, final_line_count
        ),
    }


async def _load_cache(
    arguments: argparse.Namespace, repository: PostgresLegalRepository
) -> dict[str, object]:
    _validate_batch_arguments(arguments)
    passages = _source_passages(await _source_provisions(repository))
    records, line_count = _read_cache(arguments.cache)
    state = _cache_state(arguments.cache, passages, records, line_count)
    if not state["complete"]:
        raise RuntimeError("cache is incomplete or stale; generate it before loading")
    async with repository.engine.connect() as connection:
        schema_ready = (
            await connection.execute(
                text(
                    """SELECT to_regclass('embedding_profiles') IS NOT NULL
                    AND to_regclass('provision_embeddings') IS NOT NULL"""
                )
            )
        ).scalar_one()
        if not schema_ready:
            raise RuntimeError("database must be migrated to revision 0008 or later")
        profile_exists = (
            await connection.execute(
                text(
                    "SELECT EXISTS(SELECT 1 FROM embedding_profiles WHERE profile_key=:key)"
                ),
                {"key": NVIDIA_NEMOTRON_512_PROFILE.key},
            )
        ).scalar_one()
    if not profile_exists:
        raise RuntimeError("database does not contain the required embedding profile")
    loaded = 0
    for start in range(0, len(passages), arguments.batch_size):
        batch = passages[start : start + arguments.batch_size]
        await repository.upsert_embeddings(
            [
                (
                    UUID(str(item.provision_id)),
                    item.source_text_sha256,
                    records[str(item.provision_id)].embedding,
                )
                for item in batch
            ],
            NVIDIA_NEMOTRON_512_PROFILE.key,
            NVIDIA_NEMOTRON_512_PROFILE.stored_dimensions,
        )
        loaded += len(batch)
        print(
            json.dumps(
                {"event": "db_batch_committed", "loaded": loaded, "target": len(passages)},
                ensure_ascii=False,
            ),
            flush=True,
        )
    return {"loaded_count": loaded, "state": await _database_state(repository)}


async def _run(arguments: argparse.Namespace) -> dict[str, object]:
    settings = get_settings()
    if not settings.database_url:
        raise SystemExit("DATABASE_URL이 필요합니다.")
    repository = PostgresLegalRepository(settings.database_url)
    try:
        if arguments.command == "status":
            return await _database_state(repository)
        if arguments.command in {"cache-status", "generate-cache", "load-cache"}:
            passages = _source_passages(await _source_provisions(repository))
            if arguments.command == "cache-status":
                records, line_count = _read_cache(arguments.cache)
                return _cache_state(arguments.cache, passages, records, line_count)
            if arguments.command == "generate-cache":
                return await _generate_cache(arguments, repository, settings)
            return await _load_cache(arguments, repository)

        _validate_batch_arguments(arguments)

        rows = await _provisions(repository)
        pending, _, _ = _pending(rows)
        if arguments.max_items is not None:
            pending = pending[: arguments.max_items]
        embedder = _embedder(settings)
        generated = 0
        for start in range(0, len(pending), arguments.batch_size):
            batch = pending[start : start + arguments.batch_size]
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
        final = await _database_state(repository)
        return {"generated_count": generated, "state": final}
    finally:
        await repository.engine.dispose()


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    result = asyncio.run(_run(_arguments()))
    print(json.dumps(result, ensure_ascii=False, indent=2))
