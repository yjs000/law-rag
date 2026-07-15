import json
from datetime import date, datetime
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlalchemy.pool import NullPool

from app.domain.catalog import MVP_CATALOG, SourceKind
from app.domain.entities import LegalDocumentRecord
from app.domain.provision_queries import parse_provision_reference
from app.domain.schemas import CorpusItemStatus, SearchHit


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
        embedding = str(query_embedding) if query_embedding else None
        reference = parse_provision_reference(query)
        async with self.engine.connect() as connection:
            path_rows = []
            if reference is not None:
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
            rows = []
            if reference is None:
                rows = (
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
        merged = []
        seen = set()
        for row in [*path_rows, *rows]:
            if row["provision_id"] in seen:
                continue
            seen.add(row["provision_id"])
            merged.append(self._hit(row))
        return merged[:limit]

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
