"""Current-parser corpus records used by Experiment D validation and retrieval."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from law_rag_core.persistence import SEARCHABLE_DOCUMENT_VERSION_SQL
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from app.adapters.postgres_repository import PostgresLegalRepository
from app.domain.embedding_profiles import embedding_text_sha256


@dataclass(frozen=True, slots=True)
class SourceProvision:
    provision_id: str
    version_id: str
    document_id: str
    document_title: str
    source_kind: str
    mst: str
    effective_from: date
    effective_to: date | None
    source_url: str
    path: str
    parent_path: str | None
    heading: str | None
    content: str
    ordinal: int

    @property
    def content_sha256(self) -> str:
        return embedding_text_sha256(self.content)


async def load_provisions_from_connection(
    connection: AsyncConnection,
) -> list[SourceProvision]:
    rows = (
        (
            await connection.execute(
                text(
                    f"""SELECT p.id provision_id,p.version_id,d.id document_id,
                    d.exact_title document_title,d.source_kind,v.mst,v.effective_from,
                    v.effective_to,v.source_url,p.path,p.parent_path,p.heading,p.content,p.ordinal
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
    return [
        SourceProvision(
            provision_id=str(row["provision_id"]),
            version_id=str(row["version_id"]),
            document_id=str(row["document_id"]),
            document_title=row["document_title"],
            source_kind=row["source_kind"],
            mst=row["mst"],
            effective_from=row["effective_from"],
            effective_to=row["effective_to"],
            source_url=row["source_url"],
            path=row["path"],
            parent_path=row["parent_path"],
            heading=row["heading"],
            content=row["content"],
            ordinal=row["ordinal"],
        )
        for row in rows
    ]


async def load_provisions(repository: PostgresLegalRepository) -> list[SourceProvision]:
    async with repository.engine.connect() as connection:
        return await load_provisions_from_connection(connection)


__all__ = ["SourceProvision", "load_provisions", "load_provisions_from_connection"]
