import asyncio
from dataclasses import dataclass

from llama_index.core.schema import TextNode
from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from law_rag_llamaindex.passage import (
    ProvisionRecord,
    build_node_metadata,
    build_passage_text,
    compute_source_text_sha256,
)


@dataclass(frozen=True)
class IngestionResult:
    total_provisions: int
    embedded_count: int
    skipped_count: int


async def _start_ingestion_run(engine) -> str:
    query = text(
        """
        INSERT INTO law_rag_llamaindex_ingestion_runs (started_at, status)
        VALUES (CURRENT_TIMESTAMP, :status)
        RETURNING id
        """
    )
    async with engine.begin() as connection:
        result = await connection.execute(query, {"status": "running"})
    return result.scalar_one()


async def _finish_ingestion_run(
    engine, run_id: str, status: str, *, node_count: int | None = None
) -> None:
    if node_count is None:
        query = text(
            """
            UPDATE law_rag_llamaindex_ingestion_runs
            SET status = :status, finished_at = CURRENT_TIMESTAMP
            WHERE id = :run_id
            """
        )
        parameters = {"status": status, "run_id": run_id}
    else:
        query = text(
            """
            UPDATE law_rag_llamaindex_ingestion_runs
            SET status = :status, finished_at = CURRENT_TIMESTAMP, node_count = :node_count
            WHERE id = :run_id
            """
        )
        parameters = {"status": status, "node_count": node_count, "run_id": run_id}
    async with engine.begin() as connection:
        await connection.execute(query, parameters)


def changed_provision_ids(
    provisions: list[ProvisionRecord], existing_hashes: dict[str, str]
) -> set[str]:
    changed: set[str] = set()
    for record in provisions:
        current_hash = compute_source_text_sha256(build_passage_text(record))
        if existing_hashes.get(record["provision_id"]) != current_hash:
            changed.add(record["provision_id"])
    return changed


def build_nodes(provisions: list[ProvisionRecord]) -> list[TextNode]:
    nodes = []
    for record in provisions:
        passage_text = build_passage_text(record)
        sha256 = compute_source_text_sha256(passage_text)
        nodes.append(
            TextNode(
                id_=record["provision_id"],
                text=passage_text,
                metadata=build_node_metadata(record, sha256),
            )
        )
    return nodes


async def existing_hashes(engine: AsyncEngine, table_name: str) -> dict[str, str]:
    physical_table = f"data_{table_name}"
    async with engine.connect() as connection:
        table_exists = await connection.run_sync(
            lambda sync_conn: inspect(sync_conn).has_table(physical_table)
        )
        if not table_exists:
            return {}
        query = text(
            f'SELECT node_id, metadata_->>\'source_text_sha256\' AS sha FROM "{physical_table}"'
        )
        result = await connection.execute(query)
        return {row.node_id: row.sha for row in result}


async def delete_nodes(engine: AsyncEngine, table_name: str, node_ids: set[str]) -> None:
    if not node_ids:
        return
    physical_table = f"data_{table_name}"
    query = text(f'DELETE FROM "{physical_table}" WHERE node_id = ANY(:ids)')
    async with engine.begin() as connection:
        await connection.execute(query, {"ids": list(node_ids)})


async def run_ingestion(engine, vector_store, embedder, table_name: str) -> IngestionResult:
    from law_rag_llamaindex.source import fetch_provisions

    run_id = await _start_ingestion_run(engine)
    try:
        provisions = await fetch_provisions(engine)
        current_hashes = await existing_hashes(engine, table_name)
        changed_ids = changed_provision_ids(provisions, current_hashes)
        changed_records = [p for p in provisions if p["provision_id"] in changed_ids]

        ids_to_delete = changed_ids & current_hashes.keys()
        await delete_nodes(engine, table_name, ids_to_delete)

        if changed_records:
            nodes = build_nodes(changed_records)
            texts = [node.text for node in nodes]
            embeddings = embedder.get_text_embedding_batch(texts)
            for node, embedding in zip(nodes, embeddings, strict=True):
                node.embedding = embedding
            vector_store.add(nodes)

        ingestion_result = IngestionResult(
            total_provisions=len(provisions),
            embedded_count=len(changed_records),
            skipped_count=len(provisions) - len(changed_records),
        )
        await _finish_ingestion_run(
            engine,
            run_id,
            "completed",
            node_count=ingestion_result.embedded_count,
        )
        return ingestion_result
    except Exception:
        try:
            await _finish_ingestion_run(engine, run_id, "failed")
        except Exception:
            pass
        raise


def _async_database_url(database_url: str) -> str:
    """SQLAlchemy's async engine requires an async driver in the URL scheme.
    apps/api's DATABASE_URL is typically a plain `postgresql://` value (the
    driver-agnostic form Supabase/Alembic use); normalize it to asyncpg here
    the same way apps/api's own engine construction does."""
    if database_url.startswith("postgresql+asyncpg://"):
        return database_url
    if database_url.startswith("postgresql://"):
        return database_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return database_url


async def main() -> None:
    """CLI entrypoint: `python -m law_rag_llamaindex.ingest`.

    Reads DATABASE_URL/NVIDIA_API_KEY the same way apps/api does (via
    Settings' .env/.env.local lookup), so it must be run with a working
    directory that has those configured (apps/api's .env.local in this repo).
    """
    from law_rag_llamaindex.config import get_settings
    from law_rag_llamaindex.embedding import build_embedder
    from law_rag_llamaindex.store import build_vector_store

    settings = get_settings()
    if not settings.database_url:
        raise SystemExit("DATABASE_URL is not configured")
    if not settings.nvidia_api_key:
        raise SystemExit("NVIDIA_API_KEY is not configured")

    engine = create_async_engine(_async_database_url(settings.database_url))
    try:
        vector_store = build_vector_store(settings)
        embedder = build_embedder(settings)
        result = await run_ingestion(engine, vector_store, embedder, settings.vector_table_name)
        print(
            f"ingestion complete: total={result.total_provisions} "
            f"embedded={result.embedded_count} skipped={result.skipped_count}"
        )
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
