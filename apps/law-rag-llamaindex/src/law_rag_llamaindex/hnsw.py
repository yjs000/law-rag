"""Explicit, operator-controlled lifecycle for the v2 pgvector HNSW index."""

from __future__ import annotations

import argparse
import asyncio
import re
from collections.abc import Sequence

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from law_rag_llamaindex.config import get_settings

_TABLE_NAME_PATTERN = re.compile(r"[a-z0-9_]+")
_COMMANDS = ("enable", "disable", "status", "ensure")


def _validate_table_name(table_name: str) -> str:
    if not isinstance(table_name, str) or _TABLE_NAME_PATTERN.fullmatch(table_name) is None:
        raise ValueError("table_name은 영문 소문자·숫자·밑줄만 사용할 수 있습니다.")
    return table_name


class HnswIndexManager:
    """Manage the optional v2 HNSW index without coupling it to ingestion."""

    def __init__(self, engine: AsyncEngine, table_name: str) -> None:
        self._engine = engine
        self._table_name = _validate_table_name(table_name)
        self._physical_table_name = f"data_{self._table_name}"
        self._index_name = f"{self._physical_table_name}_embedding_hnsw_idx"

    async def status(self) -> bool:
        """Return whether the exact v2 index exists in the public catalog."""
        query = text(
            "SELECT EXISTS (SELECT 1 FROM pg_class AS c "
            "JOIN pg_namespace AS n ON n.oid = c.relnamespace "
            "WHERE n.nspname = 'public' AND c.relname = :index_name)"
        )
        async with self._engine.connect() as connection:
            result = await connection.execute(query, {"index_name": self._index_name})
        return bool(result.scalar_one())

    async def ensure(self) -> bool:
        """Create the index if it is absent and report whether creation was requested."""
        if await self.status():
            return False
        await self.enable()
        return True

    async def enable(self) -> None:
        """Create the v2 cosine HNSW index using a non-transactional connection."""
        ddl = text(
            f"CREATE INDEX CONCURRENTLY IF NOT EXISTS {self._index_name} "
            f"ON {self._physical_table_name} USING hnsw "
            "(embedding vector_cosine_ops) WITH (m = 16, ef_construction = 128)"
        )
        async with self._engine.connect() as connection:
            await connection.execution_options(isolation_level="AUTOCOMMIT")
            await connection.execute(ddl)

    async def disable(self) -> None:
        """Drop the v2 HNSW index using a non-transactional connection."""
        ddl = text(f"DROP INDEX CONCURRENTLY IF EXISTS {self._index_name}")
        async with self._engine.connect() as connection:
            await connection.execution_options(isolation_level="AUTOCOMMIT")
            await connection.execute(ddl)


async def _run_command(command: str) -> bool | None:
    settings = get_settings()
    if not settings.database_url:
        raise SystemExit("DATABASE_URL이 필요합니다.")

    engine = create_async_engine(settings.database_url)
    try:
        manager = HnswIndexManager(engine, settings.vector_table_name)
        result = await getattr(manager, command)()
    finally:
        await engine.dispose()
    return result if command in {"status", "ensure"} else None


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="v2 HNSW 인덱스 상태 및 수동 lifecycle 관리")
    parser.add_argument("command", choices=_COMMANDS)
    args = parser.parse_args(argv)

    result = asyncio.run(_run_command(args.command))
    if result is not None:
        print(str(result).lower())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["HnswIndexManager", "main"]
