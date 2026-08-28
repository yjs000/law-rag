"""Database reader for canonical legal provisions."""

from collections.abc import Awaitable, Callable
from typing import Protocol

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from law_rag_llamaindex.passage import ProvisionRecord

_PROVISIONS_QUERY = text(
    """
    SELECT p.id AS provision_id, d.id AS document_id, d.exact_title AS document_title,
           d.source_kind, d.law_type_code,
           'MST ' || v.mst AS version_label,
           v.effective_from, v.effective_to,
           p.path, p.heading, p.content, v.source_url
    FROM provisions p
    JOIN document_versions v ON v.id = p.version_id
    JOIN legal_documents d ON d.id = v.document_id
    """
)

ProvisionFetcher = Callable[[AsyncEngine], Awaitable[list[ProvisionRecord]]]


class ProvisionReader(Protocol):
    """Read the validated provision snapshot used by an ingestion run."""

    async def read(self) -> list[ProvisionRecord]:
        """Return all provisions in the canonical corpus snapshot."""


async def fetch_provisions(engine: AsyncEngine) -> list[ProvisionRecord]:
    """Load canonical provisions and normalize database values at the boundary."""

    async with engine.connect() as connection:
        result = await connection.execute(_PROVISIONS_QUERY)
        rows = result.mappings().all()
    return [
        {
            "provision_id": str(row["provision_id"]),
            "document_id": str(row["document_id"]),
            "document_title": row["document_title"],
            "source_kind": row["source_kind"],
            "law_type_code": row["law_type_code"],
            "version_label": row["version_label"],
            "effective_from": row["effective_from"].isoformat() if row["effective_from"] else None,
            "effective_to": row["effective_to"].isoformat() if row["effective_to"] else None,
            "path": row["path"],
            "heading": row["heading"],
            "content": row["content"],
            "source_url": row["source_url"],
        }
        for row in rows
    ]


class DatabaseProvisionReader:
    """Adapt the async database function to the reader port consumed by services."""

    def __init__(self, engine: AsyncEngine, fetcher: ProvisionFetcher | None = None) -> None:
        self._engine = engine
        self._fetcher = fetcher

    async def read(self) -> list[ProvisionRecord]:
        if self._fetcher is not None:
            return await self._fetcher(self._engine)

        # Keep the established source-module seam: callers and tests may replace
        # ``source.fetch_provisions`` without reaching into the service package.
        from law_rag_llamaindex.source import fetch_provisions

        fetcher = fetch_provisions
        return await fetcher(self._engine)
