"""현재 법령 조문에 버전 고정 NVIDIA passage 임베딩을 채운다."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from dataclasses import dataclass

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


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="운영 corpus의 누락·변경 조문만 NVIDIA passage 임베딩으로 backfill"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("status", help="원문 해시 기준 누락·변경 벡터와 인덱스 상태 확인")
    run = subparsers.add_parser("run", help="누락·변경 벡터 생성 후 배치별 upsert")
    run.add_argument("--batch-size", type=int, default=32)
    run.add_argument("--max-items", type=int)
    run.add_argument("--max-retries", type=int, default=5)
    run.add_argument("--retry-base-seconds", type=float, default=2.0)
    return parser.parse_args()


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


async def _run(arguments: argparse.Namespace) -> dict[str, object]:
    settings = get_settings()
    if not settings.database_url:
        raise SystemExit("DATABASE_URL이 필요합니다.")
    repository = PostgresLegalRepository(settings.database_url)
    try:
        if arguments.command == "status":
            return await _database_state(repository)
        if not settings.nvidia_api_key:
            raise SystemExit("NVIDIA_API_KEY가 필요합니다.")
        if arguments.batch_size <= 0:
            raise ValueError("batch size must be positive")
        if arguments.max_items is not None and arguments.max_items <= 0:
            raise ValueError("max items must be positive")
        if arguments.max_retries < 0 or arguments.retry_base_seconds <= 0:
            raise ValueError("retry settings must be positive")

        rows = await _provisions(repository)
        pending, _, _ = _pending(rows)
        if arguments.max_items is not None:
            pending = pending[: arguments.max_items]
        embedder = NvidiaNimEmbedder(
            api_key=settings.nvidia_api_key,
            base_url=settings.nvidia_base_url,
            model=NVIDIA_NEMOTRON_512_PROFILE.model,
            dimensions=NVIDIA_NEMOTRON_512_PROFILE.stored_dimensions,
            timeout_seconds=settings.embedding_timeout_seconds,
            input_type=NVIDIA_NEMOTRON_512_PROFILE.document_input_type,
        )
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
