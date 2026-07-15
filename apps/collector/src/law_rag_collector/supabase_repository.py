import json
from datetime import date
from urllib.parse import quote

import httpx
from law_rag_core.domain.catalog import MVP_CATALOG
from law_rag_core.domain.entities import LegalDocumentRecord
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlalchemy.pool import NullPool

from law_rag_collector.activation import validate_for_activation
from law_rag_collector.client import RawResponse


def _async_url(url: str) -> str:
    if url.startswith("postgresql+asyncpg://"):
        return url
    return url.replace("postgresql://", "postgresql+asyncpg://", 1)


def raw_object_path(document: LegalDocumentRecord, raw: RawResponse) -> str:
    effective = document.effective_from.isoformat() if document.effective_from else "unknown"
    extension = raw.wire_format.casefold()
    return (
        f"{document.source_kind.value}/{document.source_id}/"
        f"{document.mst}-{effective}-{document.raw_sha256}.{extension}"
    )


class SupabaseRawStorage:
    def __init__(self, *, url: str, secret_key: str, bucket: str) -> None:
        self.url = url.rstrip("/")
        self.secret_key = secret_key
        self.bucket = bucket
        self.client = httpx.AsyncClient(timeout=30)
        self._bucket_ready = False

    @property
    def headers(self) -> dict[str, str]:
        # sb_secret_ keys are opaque API keys, not JWT bearer tokens.
        return {"apikey": self.secret_key}

    async def ensure_bucket(self) -> None:
        if self._bucket_ready:
            return
        target = f"{self.url}/storage/v1/bucket/{quote(self.bucket)}"
        response = await self.client.get(target, headers=self.headers)
        missing_bucket = response.status_code == 404
        if response.status_code == 400:
            try:
                error = response.json()
            except ValueError:
                error = {}
            missing_bucket = (
                str(error.get("statusCode")) == "404" and error.get("message") == "Bucket not found"
            )
        if missing_bucket:
            response = await self.client.post(
                f"{self.url}/storage/v1/bucket",
                headers={**self.headers, "Content-Type": "application/json"},
                json={"id": self.bucket, "name": self.bucket, "public": False},
            )
            if response.status_code != 409:
                response.raise_for_status()
        else:
            response.raise_for_status()
        self._bucket_ready = True

    async def put_immutable(self, path: str, raw: RawResponse) -> str:
        await self.ensure_bucket()
        target = f"{self.url}/storage/v1/object/{quote(self.bucket)}/{quote(path, safe='/')}"
        response = await self.client.post(
            target,
            content=raw.body.encode("utf-8"),
            headers={
                **self.headers,
                "x-upsert": "false",
                "Content-Type": (
                    "application/json" if raw.wire_format == "JSON" else "application/xml"
                ),
            },
        )
        duplicate = response.status_code == 409
        if response.status_code == 400:
            try:
                error = response.json()
            except ValueError:
                error = {}
            duplicate = (
                str(error.get("statusCode")) == "409"
                and error.get("message") == "The resource already exists"
            )
        if not duplicate:
            response.raise_for_status()
        return f"{self.bucket}/{path}"

    async def close(self) -> None:
        await self.client.aclose()


class SupabaseCurrentCorpusRepository:
    """검증된 현재 버전을 Supabase Storage와 PostgreSQL에 적재한다."""

    def __init__(
        self,
        *,
        database_url: str,
        supabase_url: str,
        supabase_secret_key: str,
        bucket: str,
        engine: AsyncEngine | None = None,
        storage: SupabaseRawStorage | None = None,
    ) -> None:
        self.engine = engine or create_async_engine(
            _async_url(database_url),
            poolclass=NullPool,
            connect_args={"statement_cache_size": 0},
        )
        self.storage = storage or SupabaseRawStorage(
            url=supabase_url,
            secret_key=supabase_secret_key,
            bucket=bucket,
        )

    async def upsert(
        self,
        document: LegalDocumentRecord,
        raw: RawResponse,
        *,
        effective_to: date | None,
    ) -> bool:
        validate_for_activation(document, raw, today=date.today())
        path = raw_object_path(document, raw)
        document.raw_storage_path = await self.storage.put_immutable(path, raw)
        async with self.engine.begin() as connection:
            document_id = (
                await connection.execute(
                    text(
                        """INSERT INTO legal_documents(source_id,exact_title,source_kind)
                        VALUES(:source_id,:title,:kind)
                        ON CONFLICT(source_kind,source_id) DO UPDATE
                        SET exact_title=excluded.exact_title
                        RETURNING id"""
                    ),
                    {
                        "source_id": document.source_id,
                        "title": document.title,
                        "kind": document.source_kind.value,
                    },
                )
            ).scalar_one()
            previous_hash = (
                await connection.execute(
                    text(
                        "SELECT raw_sha256 FROM document_versions "
                        "WHERE document_id=:document_id AND mst=:mst"
                    ),
                    {"document_id": document_id, "mst": document.mst},
                )
            ).scalar_one_or_none()
            version_id = (
                await connection.execute(
                    text(
                        """INSERT INTO document_versions(
                        document_id,mst,promulgation_number,promulgated_on,effective_from,
                        effective_to,ministry,source_url,raw_format,raw_sha256,raw_storage_path,
                        parser_schema_version,fallback_reason,collected_at)
                        VALUES(:document_id,:mst,:number,:promulgated,:effective_from,:effective_to,
                        :ministry,:url,:format,:hash,:storage,:schema,:fallback,now())
                        ON CONFLICT(document_id,mst) DO UPDATE SET
                        promulgation_number=excluded.promulgation_number,
                        promulgated_on=excluded.promulgated_on,
                        effective_from=excluded.effective_from,effective_to=excluded.effective_to,
                        ministry=excluded.ministry,source_url=excluded.source_url,
                        raw_format=excluded.raw_format,raw_sha256=excluded.raw_sha256,
                        raw_storage_path=excluded.raw_storage_path,
                        parser_schema_version=excluded.parser_schema_version,
                        fallback_reason=excluded.fallback_reason,collected_at=now()
                        RETURNING id"""
                    ),
                    {
                        "document_id": document_id,
                        "mst": document.mst,
                        "number": document.promulgation_number,
                        "promulgated": document.promulgated_on,
                        "effective_from": document.effective_from,
                        "effective_to": effective_to,
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
            if document.provisions:
                await connection.execute(
                    text(
                        """INSERT INTO provisions(
                        id,version_id,path,parent_path,heading,content,ordinal)
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
        return previous_hash != document.raw_sha256

    async def record_run(self, command: str, results: list[dict]) -> None:
        failed = [item for item in results if item["state"] == "failed"]
        stats = {
            "command": command,
            "ready": sum(item["state"] == "ready" for item in results),
            "unchanged": sum(item["state"] == "unchanged" for item in results),
            "failed": len(failed),
        }
        async with self.engine.begin() as connection:
            await connection.execute(
                text(
                    """INSERT INTO ingestion_runs(completed_at,state,stats,error_code)
                    VALUES(now(),:state,CAST(:stats AS jsonb),:error_code)"""
                ),
                {
                    "state": "failed" if failed else "completed",
                    "stats": json.dumps(stats, ensure_ascii=False),
                    "error_code": "document_failure" if failed else None,
                },
            )

    async def status(self) -> dict:
        async with self.engine.connect() as connection:
            rows = (
                await connection.execute(
                    text(
                        """SELECT d.exact_title,COUNT(v.id) versions,MAX(v.effective_from) latest
                        FROM legal_documents d JOIN document_versions v ON v.document_id=d.id
                        GROUP BY d.exact_title"""
                    )
                )
            ).all()
            last_run = (
                (
                    await connection.execute(
                        text(
                            "SELECT completed_at,state,stats,error_code FROM ingestion_runs "
                            "ORDER BY started_at DESC LIMIT 1"
                        )
                    )
                )
                .mappings()
                .first()
            )
        ready = {row[0]: {"versions": row[1], "latest": row[2]} for row in rows}
        return {
            "storage": "supabase",
            "last_run": dict(last_run) if last_run else None,
            "documents": sum(item["versions"] for item in ready.values()),
            "items": [
                {
                    "title": entry.title,
                    "source_kind": entry.source_kind.value,
                    "state": "ready" if entry.title in ready else "missing",
                    "versions": ready.get(entry.title, {}).get("versions", 0),
                    "latest_effective_date": ready.get(entry.title, {}).get("latest"),
                }
                for entry in MVP_CATALOG
            ],
        }

    def deletion_window(self, *, today: date):
        raise RuntimeError("Supabase 연혁·삭제 동기화는 아직 활성화되지 않았습니다")

    def apply_source_deletions(self, records, *, completed_on: date):
        raise RuntimeError("Supabase 연혁·삭제 동기화는 아직 활성화되지 않았습니다")

    async def close(self) -> None:
        await self.storage.close()
        await self.engine.dispose()
