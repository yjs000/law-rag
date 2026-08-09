import json
from collections.abc import AsyncIterator, Mapping, Sequence
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import date, timedelta
from urllib.parse import quote
from uuid import UUID

import httpx
from law_rag_core.domain.catalog import MVP_CATALOG
from law_rag_core.domain.entities import LegalDocumentRecord, ProvisionRecord
from law_rag_core.persistence import (
    CORPUS_MUTATION_LOCK_KEY,
    CORPUS_SEARCH_READY_CAPABILITY_SQL,
    CORPUS_SEARCH_READY_FLAG_KEY,
    CORPUS_SYNC_RUN_LOCK_KEY,
    EMBEDDING_BACKFILL_LOCK_KEY,
)
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlalchemy.pool import NullPool

from law_rag_collector.activation import validate_for_activation
from law_rag_collector.client import RawResponse
from law_rag_collector.deletions import DeletionRecord

_DELETION_SYNC_FLAG_KEY = "collector.deletion_sync"

_VERSION_FIELDS = (
    "promulgation_number",
    "promulgated_on",
    "effective_from",
    "effective_to",
    "ministry",
    "source_url",
    "raw_format",
    "raw_sha256",
    "raw_storage_path",
    "parser_schema_version",
    "fallback_reason",
    "lifecycle_state",
    "source_record_state",
    "source_deleted_on",
    "has_supplementary_provisions",
)


@dataclass(frozen=True, slots=True)
class ProvisionSyncPlan:
    new_ids: frozenset[UUID]
    updated_ids: frozenset[UUID]
    removed_ids: frozenset[UUID]
    stale_embedding_ids: frozenset[UUID]

    @property
    def changed(self) -> bool:
        return bool(self.new_ids or self.updated_ids or self.removed_ids)

    @property
    def stale_derived_ids(self) -> frozenset[UUID]:
        return self.updated_ids | self.removed_ids

    @property
    def requires_embedding_revalidation(self) -> bool:
        return bool(self.new_ids or self.updated_ids)


def plan_provision_sync(
    existing: Sequence[Mapping[str, object]],
    incoming: Sequence[ProvisionRecord],
) -> ProvisionSyncPlan:
    existing_by_id = {UUID(str(item["id"])): item for item in existing}
    if len(existing_by_id) != len(existing):
        raise ValueError("existing provisions contain duplicate IDs")
    incoming_by_id = {item.id: item for item in incoming}
    if len(incoming_by_id) != len(incoming):
        raise ValueError("incoming provisions contain duplicate IDs")

    existing_ids = set(existing_by_id)
    incoming_ids = set(incoming_by_id)
    shared_ids = existing_ids & incoming_ids
    updated: set[UUID] = set()
    stale_embeddings: set[UUID] = set()
    for provision_id in shared_ids:
        before = existing_by_id[provision_id]
        after = incoming_by_id[provision_id]
        if any(
            before[field] != getattr(after, field)
            for field in ("path", "parent_path", "heading", "content", "ordinal")
        ):
            updated.add(provision_id)
        if any(
            before[field] != getattr(after, field)
            for field in ("path", "heading", "content")
        ):
            stale_embeddings.add(provision_id)

    return ProvisionSyncPlan(
        new_ids=frozenset(incoming_ids - existing_ids),
        updated_ids=frozenset(updated),
        removed_ids=frozenset(existing_ids - incoming_ids),
        stale_embedding_ids=frozenset(stale_embeddings),
    )


def _version_values(
    document: LegalDocumentRecord,
    *,
    effective_to: date | None,
    lifecycle_state: str,
    source_record_state: str,
    has_supplementary_provisions: bool,
) -> dict[str, object]:
    return {
        "promulgation_number": document.promulgation_number,
        "promulgated_on": document.promulgated_on,
        "effective_from": document.effective_from,
        "effective_to": effective_to,
        "ministry": document.ministry,
        "source_url": document.source_url,
        "raw_format": document.raw_format,
        "raw_sha256": document.raw_sha256,
        "raw_storage_path": document.raw_storage_path,
        "parser_schema_version": document.parser_schema_version,
        "fallback_reason": document.fallback_reason,
        "lifecycle_state": lifecycle_state,
        "source_record_state": source_record_state,
        "source_deleted_on": None,
        "has_supplementary_provisions": has_supplementary_provisions,
    }


def version_record_changed(
    existing: Mapping[str, object] | None,
    incoming: Mapping[str, object],
) -> bool:
    return existing is None or any(existing[field] != incoming[field] for field in _VERSION_FIELDS)


def _embedding_eligible_version(
    *, lifecycle_state: object, source_record_state: object, effective_to: object
) -> bool:
    return source_record_state == "available" and (
        lifecycle_state in {"active", "scheduled"}
        or (lifecycle_state == "abolished" and isinstance(effective_to, date))
    )


def _ordered_ids(values: Sequence[UUID] | frozenset[UUID]) -> list[UUID]:
    return sorted(values, key=str)


def _batches[T](values: Sequence[T], batch_size: int | None) -> list[Sequence[T]]:
    if not values:
        return []
    if batch_size is None:
        return [values]
    if batch_size <= 0:
        raise ValueError("batch size must be positive")
    return [values[start : start + batch_size] for start in range(0, len(values), batch_size)]


async def _set_corpus_search_ready(
    connection,
    *,
    ready: bool,
    reason: str,
    update_id: str | None = None,
) -> None:
    schema_ready = (
        await connection.execute(text(f"SELECT {CORPUS_SEARCH_READY_CAPABILITY_SQL}"))
    ).scalar_one()
    if not schema_ready:
        raise RuntimeError("DB migration 0010 이상이 필요합니다")
    value: dict[str, object] = {"ready": ready, "reason": reason}
    if update_id is not None:
        value["update_id"] = update_id
    await connection.execute(
        text(
            """INSERT INTO runtime_flags(key,value,updated_at)
            VALUES(:key,CAST(:value AS jsonb),now())
            ON CONFLICT(key) DO UPDATE SET value=excluded.value,updated_at=now()"""
        ),
        {
            "key": CORPUS_SEARCH_READY_FLAG_KEY,
            "value": json.dumps(value),
        },
    )


async def _mark_corpus_search_unready(connection, *, reason: str) -> None:
    await _set_corpus_search_ready(connection, ready=False, reason=reason)


def resolve_effective_to(
    existing_versions: Sequence[Mapping[str, object]],
    *,
    incoming_mst: str,
    incoming_effective_from: date,
    requested_effective_to: date | None,
) -> date | None:
    same_day_other_msts = {
        str(item["mst"])
        for item in existing_versions
        if item["effective_from"] == incoming_effective_from
        and str(item["mst"]) != incoming_mst
    }
    if same_day_other_msts:
        values = ", ".join(sorted(same_day_other_msts))
        raise ValueError(f"동일 시행일의 다른 MST가 이미 있습니다: {values}")

    later_dates = {
        item["effective_from"]
        for item in existing_versions
        if isinstance(item["effective_from"], date)
        and item["effective_from"] > incoming_effective_from
    }
    next_effective_from = min(later_dates) if later_dates else None
    if (
        requested_effective_to is not None
        and next_effective_from is not None
        and requested_effective_to != next_effective_from
    ):
        raise ValueError("요청한 효력 종료일이 다음 저장 버전의 시행일과 다릅니다")
    resolved = requested_effective_to or next_effective_from
    if resolved is not None and resolved <= incoming_effective_from:
        raise ValueError("효력 종료일은 시행일보다 뒤여야 합니다")
    return resolved


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
        self.bucket = bucket
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

    @asynccontextmanager
    async def sync_run_lock(self) -> AsyncIterator[None]:
        """Open API fetch부터 마지막 DB 반영까지 collector 실행을 하나로 직렬화한다."""
        async with self.engine.connect() as connection:
            acquired = (
                await connection.execute(
                    text("SELECT pg_try_advisory_lock(:lock_key)"),
                    {"lock_key": CORPUS_SYNC_RUN_LOCK_KEY},
                )
            ).scalar_one()
            # Session advisory locks survive COMMIT. End SQLAlchemy's implicit
            # transaction before yielding across slow Open API network calls.
            await connection.commit()
            if not acquired:
                raise RuntimeError("다른 collector sync-current 실행이 진행 중입니다")
            try:
                yield
            finally:
                await connection.execute(
                    text("SELECT pg_advisory_unlock(:lock_key)"),
                    {"lock_key": CORPUS_SYNC_RUN_LOCK_KEY},
                )
                await connection.commit()

    @asynccontextmanager
    async def prepared_publish_session(self) -> AsyncIterator[object]:
        """직렬화된 prepared publish가 사용할 session 연결을 대여한다.

        느린 Open API/NIM 준비 단계에서는 이 lock을 잡지 않는다. 검증된 원문이
        Storage에 올라간 뒤부터 최종 DB transaction이 끝날 때까지만 기존 writer
        lock 두 개를 고정 순서로 보유한다.
        """

        lock_keys = (EMBEDDING_BACKFILL_LOCK_KEY, CORPUS_SYNC_RUN_LOCK_KEY)
        acquired: list[int] = []
        async with self.engine.connect() as connection:
            try:
                for lock_key in lock_keys:
                    locked = (
                        await connection.execute(
                            text("SELECT pg_try_advisory_lock(:lock_key)"),
                            {"lock_key": lock_key},
                        )
                    ).scalar_one()
                    await connection.commit()
                    if not locked:
                        raise RuntimeError("다른 corpus writer 실행이 진행 중입니다")
                    acquired.append(lock_key)
                yield connection
            finally:
                for lock_key in reversed(acquired):
                    await connection.execute(
                        text("SELECT pg_advisory_unlock(:lock_key)"),
                        {"lock_key": lock_key},
                    )
                    await connection.commit()

    async def preview(
        self,
        document: LegalDocumentRecord,
        raw: RawResponse,
        *,
        effective_to: date | None,
    ) -> dict[str, object]:
        """원문이나 DB를 바꾸지 않고 현재 저장 상태와의 동기화 차이를 계산한다."""
        activation = validate_for_activation(document, raw, today=date.today())
        if document.source_url != raw.source_url:
            raise ValueError("파서 출처 URL과 원문 출처 URL이 다릅니다")
        if document.effective_from is None:
            raise ValueError("시행일이 없습니다")
        async with self.engine.connect() as connection:
            existing_document = (
                (
                    await connection.execute(
                        text(
                            "SELECT id,exact_title FROM legal_documents "
                            "WHERE source_kind=:kind AND source_id=:source_id"
                        ),
                        {
                            "kind": document.source_kind.value,
                            "source_id": document.source_id,
                        },
                    )
                )
                .mappings()
                .first()
            )
            title_owners = (
                (
                    await connection.execute(
                        text(
                            "SELECT id,source_kind,source_id FROM legal_documents "
                            "WHERE exact_title=:title"
                        ),
                        {"title": document.title},
                    )
                )
                .mappings()
                .all()
            )
            if any(
                owner["source_kind"] != document.source_kind.value
                or owner["source_id"] != document.source_id
                for owner in title_owners
            ):
                raise ValueError("같은 정확 명칭이 다른 출처 ID에 연결되어 있습니다")

            document_id = existing_document["id"] if existing_document else None
            existing_versions: list[Mapping[str, object]] = []
            previous_version: Mapping[str, object] | None = None
            existing_provisions: list[Mapping[str, object]] = []
            document_embedding_count = 0
            if document_id is not None:
                existing_versions = list(
                    (
                        await connection.execute(
                            text(
                                """SELECT id,mst,promulgation_number,promulgated_on,
                                effective_from,effective_to,ministry,source_url,raw_format,
                                raw_sha256,raw_storage_path,parser_schema_version,fallback_reason,
                                lifecycle_state,source_record_state,source_deleted_on,
                                has_supplementary_provisions
                                FROM document_versions WHERE document_id=:document_id
                                ORDER BY effective_from,mst"""
                            ),
                            {"document_id": document_id},
                        )
                    )
                    .mappings()
                    .all()
                )
                previous_version = next(
                    (
                        item
                        for item in existing_versions
                        if item["mst"] == document.mst
                        and item["effective_from"] == document.effective_from
                    ),
                    None,
                )
                if previous_version is not None:
                    existing_provisions = list(
                        (
                            await connection.execute(
                                text(
                                    """SELECT id,path,parent_path,heading,content,ordinal
                                    FROM provisions WHERE version_id=:version_id"""
                                ),
                                {"version_id": previous_version["id"]},
                            )
                        )
                        .mappings()
                        .all()
                    )
                if existing_document["exact_title"] != document.title:
                    document_embedding_count = (
                        await connection.execute(
                            text(
                                """SELECT COUNT(*) FROM provision_embeddings e
                                JOIN provisions p ON p.id=e.provision_id
                                JOIN document_versions v ON v.id=p.version_id
                                WHERE v.document_id=:document_id"""
                            ),
                            {"document_id": document_id},
                        )
                    ).scalar_one()

            resolved_effective_to = resolve_effective_to(
                existing_versions,
                incoming_mst=document.mst,
                incoming_effective_from=document.effective_from,
                requested_effective_to=effective_to,
            )
            preview_version_values = _version_values(
                document,
                effective_to=resolved_effective_to,
                lifecycle_state=activation.lifecycle_state,
                source_record_state=activation.source_record_state,
                has_supplementary_provisions=activation.has_supplementary_provisions,
            )
            preview_version_values["raw_storage_path"] = (
                f"{self.bucket}/{raw_object_path(document, raw)}"
            )
            changed_version_fields = [
                field
                for field in _VERSION_FIELDS
                if previous_version is None
                or previous_version[field] != preview_version_values[field]
            ]
            plan = plan_provision_sync(existing_provisions, document.provisions)
            eligibility_changed = bool(
                previous_version is not None
                and _embedding_eligible_version(
                    lifecycle_state=previous_version["lifecycle_state"],
                    source_record_state=previous_version["source_record_state"],
                    effective_to=previous_version["effective_to"],
                )
                != _embedding_eligible_version(
                    lifecycle_state=activation.lifecycle_state,
                    source_record_state=activation.source_record_state,
                    effective_to=resolved_effective_to,
                )
            )
            incoming_ids = _ordered_ids([item.id for item in document.provisions])
            version_id = previous_version["id"] if previous_version else None
            id_collisions = (
                (
                    await connection.execute(
                        text(
                            """SELECT id,version_id FROM provisions
                            WHERE id=ANY(CAST(:provision_ids AS uuid[]))
                              AND (CAST(:version_id AS uuid) IS NULL
                                   OR version_id<>CAST(:version_id AS uuid))"""
                        ),
                        {"provision_ids": incoming_ids, "version_id": version_id},
                    )
                )
                .mappings()
                .all()
            )
            if id_collisions:
                raise ValueError("조문 ID가 다른 법령 버전에 이미 속해 있습니다")
            would_close_versions = sum(
                item["effective_from"] < document.effective_from
                and (item["effective_to"] is None or item["effective_to"] > document.effective_from)
                for item in existing_versions
            )
        return {
            "title": document.title,
            "source_id": document.source_id,
            "mst": document.mst,
            "effective_from": document.effective_from.isoformat(),
            "effective_to": (
                resolved_effective_to.isoformat() if resolved_effective_to else None
            ),
            "raw_format": document.raw_format,
            "fallback_reason": document.fallback_reason,
            "parser_schema_version": document.parser_schema_version,
            "lifecycle_state": activation.lifecycle_state,
            "source_record_state": activation.source_record_state,
            "new_document": existing_document is None,
            "new_version": previous_version is None,
            "raw_changed": bool(
                previous_version is None
                or previous_version["raw_sha256"] != document.raw_sha256
            ),
            "parser_changed": bool(
                previous_version is None
                or previous_version["parser_schema_version"]
                != document.parser_schema_version
            ),
            "version_changed": bool(changed_version_fields),
            "changed_version_fields": changed_version_fields,
            "title_changed": bool(
                existing_document and existing_document["exact_title"] != document.title
            ),
            "would_close_versions": would_close_versions,
            "incoming_provisions": len(document.provisions),
            "existing_provisions": len(existing_provisions),
            "new_provisions": len(plan.new_ids),
            "missing_embeddings": len(plan.new_ids),
            "updated_provisions": len(plan.updated_ids),
            "removed_provisions": len(plan.removed_ids),
            "stale_embeddings": (
                document_embedding_count
                if existing_document and existing_document["exact_title"] != document.title
                else len(plan.stale_embedding_ids)
            ),
            "embedding_revalidation_required": bool(
                existing_document and existing_document["exact_title"] != document.title
            )
            or plan.requires_embedding_revalidation
            or eligibility_changed,
        }

    async def upsert(
        self,
        document: LegalDocumentRecord,
        raw: RawResponse,
        *,
        effective_to: date | None,
        batch_size: int | None = None,
    ) -> bool:
        activation = validate_for_activation(document, raw, today=date.today())
        if document.source_url != raw.source_url:
            raise ValueError("파서 출처 URL과 원문 출처 URL이 다릅니다")
        if document.effective_from is None:
            raise ValueError("시행일이 없습니다")
        path = raw_object_path(document, raw)
        document.raw_storage_path = await self.storage.put_immutable(path, raw)
        async with self.engine.begin() as connection:
            await connection.execute(
                text("SELECT pg_advisory_xact_lock(:lock_key)"),
                {"lock_key": CORPUS_MUTATION_LOCK_KEY},
            )
            existing_document = (
                (
                    await connection.execute(
                        text(
                            "SELECT id,exact_title FROM legal_documents "
                            "WHERE source_kind=:kind AND source_id=:source_id FOR UPDATE"
                        ),
                        {
                            "kind": document.source_kind.value,
                            "source_id": document.source_id,
                        },
                    )
                )
                .mappings()
                .first()
            )
            document_title_changed = bool(
                existing_document is not None
                and existing_document["exact_title"] != document.title
            )
            title_owners = (
                (
                    await connection.execute(
                        text(
                            "SELECT id,source_kind,source_id FROM legal_documents "
                            "WHERE exact_title=:title FOR UPDATE"
                        ),
                        {"title": document.title},
                    )
                )
                .mappings()
                .all()
            )
            if any(
                owner["source_kind"] != document.source_kind.value
                or owner["source_id"] != document.source_id
                for owner in title_owners
            ):
                raise ValueError("같은 정확 명칭이 다른 출처 ID에 연결되어 있습니다")
            document_id = (
                await connection.execute(
                    text(
                        """INSERT INTO legal_documents(
                        source_id,exact_title,source_kind,law_type_name,law_type_code)
                        VALUES(:source_id,:title,:kind,:law_type_name,:law_type_code)
                        ON CONFLICT(source_kind,source_id) DO UPDATE
                        SET exact_title=excluded.exact_title,
                        law_type_name=excluded.law_type_name,
                        law_type_code=excluded.law_type_code
                        RETURNING id"""
                    ),
                    {
                        "source_id": document.source_id,
                        "title": document.title,
                        "kind": document.source_kind.value,
                        "law_type_name": document.law_type_name,
                        "law_type_code": document.law_type_code,
                    },
                )
            ).scalar_one()
            existing_versions = (
                (
                    await connection.execute(
                        text(
                            """SELECT id,mst,promulgation_number,promulgated_on,
                            effective_from,effective_to,ministry,source_url,raw_format,
                            raw_sha256,raw_storage_path,parser_schema_version,fallback_reason,
                            lifecycle_state,source_record_state,source_deleted_on,
                            has_supplementary_provisions
                            FROM document_versions WHERE document_id=:document_id
                            ORDER BY effective_from,mst FOR UPDATE"""
                        ),
                        {"document_id": document_id},
                    )
                )
                .mappings()
                .all()
            )
            previous_version = next(
                (
                    item
                    for item in existing_versions
                    if item["mst"] == document.mst
                    and item["effective_from"] == document.effective_from
                ),
                None,
            )
            resolved_effective_to = resolve_effective_to(
                existing_versions,
                incoming_mst=document.mst,
                incoming_effective_from=document.effective_from,
                requested_effective_to=effective_to,
            )
            version_values = _version_values(
                document,
                effective_to=resolved_effective_to,
                lifecycle_state=activation.lifecycle_state,
                source_record_state=activation.source_record_state,
                has_supplementary_provisions=activation.has_supplementary_provisions,
            )
            closed_versions = (
                await connection.execute(
                    text(
                        """UPDATE document_versions SET effective_to=:effective_from
                        WHERE document_id=:document_id
                          AND effective_from<:effective_from
                          AND (effective_to IS NULL OR effective_to>:effective_from)
                        RETURNING id"""
                    ),
                    {
                        "document_id": document_id,
                        "effective_from": document.effective_from,
                    },
                )
            ).all()
            version_id = (
                await connection.execute(
                    text(
                        """INSERT INTO document_versions(
                        document_id,mst,promulgation_number,promulgated_on,effective_from,
                        effective_to,ministry,source_url,raw_format,raw_sha256,raw_storage_path,
                        parser_schema_version,fallback_reason,lifecycle_state,
                        source_record_state,source_deleted_on,has_supplementary_provisions,
                        collected_at)
                        VALUES(:document_id,:mst,:number,:promulgated,:effective_from,:effective_to,
                        :ministry,:url,:format,:hash,:storage,:schema,:fallback,
                        :lifecycle_state,:source_record_state,:source_deleted_on,
                        :has_supplementary_provisions,now())
                        ON CONFLICT(document_id,mst,effective_from) DO UPDATE SET
                        promulgation_number=excluded.promulgation_number,
                        promulgated_on=excluded.promulgated_on,
                        effective_to=excluded.effective_to,
                        ministry=excluded.ministry,source_url=excluded.source_url,
                        raw_format=excluded.raw_format,raw_sha256=excluded.raw_sha256,
                        raw_storage_path=excluded.raw_storage_path,
                        parser_schema_version=excluded.parser_schema_version,
                        fallback_reason=excluded.fallback_reason,
                        lifecycle_state=excluded.lifecycle_state,
                        source_record_state=excluded.source_record_state,
                        source_deleted_on=excluded.source_deleted_on,
                        has_supplementary_provisions=excluded.has_supplementary_provisions,
                        collected_at=now()
                        RETURNING id"""
                    ),
                    {
                        "document_id": document_id,
                        "mst": document.mst,
                        "number": document.promulgation_number,
                        "promulgated": document.promulgated_on,
                        "effective_from": document.effective_from,
                        "effective_to": resolved_effective_to,
                        "ministry": document.ministry,
                        "url": document.source_url,
                        "format": document.raw_format,
                        "hash": document.raw_sha256,
                        "storage": document.raw_storage_path,
                        "schema": document.parser_schema_version,
                        "fallback": document.fallback_reason,
                        "lifecycle_state": activation.lifecycle_state,
                        "source_record_state": activation.source_record_state,
                        "source_deleted_on": None,
                        "has_supplementary_provisions": (
                            activation.has_supplementary_provisions
                        ),
                    },
                )
            ).scalar_one()
            existing_provisions = (
                (
                    await connection.execute(
                        text(
                            """SELECT id,path,parent_path,heading,content,ordinal
                            FROM provisions WHERE version_id=:version_id"""
                        ),
                        {"version_id": version_id},
                    )
                )
                .mappings()
                .all()
            )
            sync_plan = plan_provision_sync(
                existing_provisions,
                document.provisions,
            )
            version_changed = version_record_changed(previous_version, version_values)
            search_state_changed = bool(
                document_title_changed
                or closed_versions
                or version_changed
                or sync_plan.changed
            )
            eligibility_changed = bool(
                previous_version is not None
                and _embedding_eligible_version(
                    lifecycle_state=previous_version["lifecycle_state"],
                    source_record_state=previous_version["source_record_state"],
                    effective_to=previous_version["effective_to"],
                )
                != _embedding_eligible_version(
                    lifecycle_state=activation.lifecycle_state,
                    source_record_state=activation.source_record_state,
                    effective_to=resolved_effective_to,
                )
            )
            incoming_ids = _ordered_ids([item.id for item in document.provisions])
            id_collisions: list[Mapping[str, object]] = []
            for incoming_batch in _batches(incoming_ids, batch_size):
                id_collisions.extend(
                    (
                        await connection.execute(
                            text(
                                """SELECT id,version_id FROM provisions
                                WHERE id=ANY(CAST(:provision_ids AS uuid[]))
                                  AND version_id<>:version_id FOR UPDATE"""
                            ),
                            {"provision_ids": incoming_batch, "version_id": version_id},
                        )
                    )
                    .mappings()
                    .all()
                )
            if id_collisions:
                raise ValueError("조문 ID가 다른 법령 버전에 이미 속해 있습니다")

            if search_state_changed:
                await _mark_corpus_search_unready(
                    connection,
                    reason="collector_corpus_change",
                )
            if (
                document_title_changed
                or sync_plan.requires_embedding_revalidation
                or eligibility_changed
            ):
                await connection.execute(
                    text("UPDATE embedding_profiles SET active=false WHERE active"),
                )
            if document_title_changed:
                await connection.execute(
                    text(
                        """DELETE FROM provision_embeddings e USING provisions p,
                        document_versions v WHERE e.provision_id=p.id
                          AND p.version_id=v.id AND v.document_id=:document_id"""
                    ),
                    {"document_id": document_id},
                )
            elif sync_plan.stale_embedding_ids:
                for stale_batch in _batches(
                    _ordered_ids(sync_plan.stale_embedding_ids), batch_size
                ):
                    await connection.execute(
                        text(
                            """DELETE FROM provision_embeddings
                            WHERE provision_id=ANY(CAST(:provision_ids AS uuid[]))"""
                        ),
                        {"provision_ids": stale_batch},
                    )
            if sync_plan.stale_derived_ids:
                stale_derived_ids = _ordered_ids(sync_plan.stale_derived_ids)
                for stale_batch in _batches(stale_derived_ids, batch_size):
                    await connection.execute(
                        text(
                            """DELETE FROM legal_relationships
                            WHERE from_provision_id=ANY(CAST(:provision_ids AS uuid[]))
                               OR to_provision_id=ANY(CAST(:provision_ids AS uuid[]))"""
                        ),
                        {"provision_ids": stale_batch},
                    )
                    await connection.execute(
                        text(
                            """DELETE FROM derived_obligations
                            WHERE provision_id=ANY(CAST(:provision_ids AS uuid[]))"""
                        ),
                        {"provision_ids": stale_batch},
                    )
            if sync_plan.removed_ids:
                for removed_batch in _batches(
                    _ordered_ids(sync_plan.removed_ids), batch_size
                ):
                    await connection.execute(
                        text(
                            """DELETE FROM provisions
                            WHERE id=ANY(CAST(:provision_ids AS uuid[]))
                              AND version_id=:version_id"""
                        ),
                        {
                            "provision_ids": removed_batch,
                            "version_id": version_id,
                        },
                    )
            changed_ids = sync_plan.new_ids | sync_plan.updated_ids
            changed_provisions = [
                item for item in document.provisions if item.id in changed_ids
            ]
            if changed_provisions:
                for provision_batch in _batches(changed_provisions, batch_size):
                    await connection.execute(
                        text(
                            """INSERT INTO provisions(
                            id,version_id,path,parent_path,heading,content,ordinal)
                            VALUES(:id,:version_id,:path,:parent_path,:heading,:content,:ordinal)
                            ON CONFLICT(id) DO UPDATE SET
                            path=excluded.path,parent_path=excluded.parent_path,
                            heading=excluded.heading,content=excluded.content,
                            ordinal=excluded.ordinal
                            WHERE provisions.version_id=excluded.version_id"""
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
                            for item in provision_batch
                        ],
                    )
            persisted_provisions = (
                (
                    await connection.execute(
                        text(
                            """SELECT id,path,parent_path,heading,content,ordinal
                            FROM provisions WHERE version_id=:version_id"""
                        ),
                        {"version_id": version_id},
                    )
                )
                .mappings()
                .all()
            )
            if plan_provision_sync(persisted_provisions, document.provisions).changed:
                raise RuntimeError("조문 동기화 후 저장 상태가 입력과 다릅니다")
        return bool(
            document_title_changed
            or closed_versions
            or version_changed
            or sync_plan.changed
        )

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

    async def deletion_window(self, *, today: date) -> tuple[date, date]:
        """Return a seven-day first window and one-day overlap after a completed run."""
        async with self.engine.connect() as connection:
            completed = (
                await connection.execute(
                    text(
                        """SELECT value->>'completed_on' FROM runtime_flags
                        WHERE key=:key"""
                    ),
                    {"key": _DELETION_SYNC_FLAG_KEY},
                )
            ).scalar_one_or_none()
        if not completed:
            return today - timedelta(days=7), today
        completed_on = min(date.fromisoformat(str(completed)), today)
        return completed_on - timedelta(days=1), today

    async def apply_source_deletions(
        self,
        records: list[DeletionRecord],
        *,
        completed_on: date,
    ) -> dict[str, dict[str, int]]:
        """Quarantine source-deleted versions and advance the checkpoint after all records."""
        earliest: dict[tuple[str, str], date] = {}
        for record in records:
            key = (record.source_kind.value, record.mst)
            earliest[key] = min(earliest.get(key, record.deleted_on), record.deleted_on)

        stats = {
            "law": {"matched": 0, "changed": 0},
            "administrative_rule": {"matched": 0, "changed": 0},
        }
        for (source_kind, mst), deleted_on in sorted(earliest.items()):
            async with self.engine.begin() as connection:
                await connection.execute(
                    text("SELECT pg_advisory_xact_lock(:lock_key)"),
                    {"lock_key": CORPUS_MUTATION_LOCK_KEY},
                )
                matching = (
                    (
                        await connection.execute(
                            text(
                                """SELECT v.id,v.source_record_state,v.source_deleted_on
                                FROM document_versions v
                                JOIN legal_documents d ON d.id=v.document_id
                                WHERE d.source_kind=:source_kind AND v.mst=:mst
                                FOR UPDATE"""
                            ),
                            {"source_kind": source_kind, "mst": mst},
                        )
                    )
                    .mappings()
                    .all()
                )
                stats[source_kind]["matched"] += len(matching)
                changed_ids = [
                    UUID(str(item["id"]))
                    for item in matching
                    if item["source_record_state"] != "deleted"
                    or item["source_deleted_on"] is None
                    or item["source_deleted_on"] > deleted_on
                ]
                if not changed_ids:
                    continue
                changed_rows = (
                    await connection.execute(
                        text(
                            """UPDATE document_versions
                            SET source_record_state='deleted',
                              source_deleted_on=CASE
                                WHEN source_deleted_on IS NULL THEN :deleted_on
                                ELSE LEAST(source_deleted_on,:deleted_on)
                              END
                            WHERE id=ANY(CAST(:version_ids AS uuid[]))
                            RETURNING id"""
                        ),
                        {
                            "deleted_on": deleted_on,
                            "version_ids": _ordered_ids(changed_ids),
                        },
                    )
                ).all()
                if len(changed_rows) != len(changed_ids):
                    raise RuntimeError("출처 삭제 상태를 일부 법령 버전에 반영하지 못했습니다")
                stats[source_kind]["changed"] += len(changed_rows)
                await _mark_corpus_search_unready(
                    connection,
                    reason="collector_source_deletion",
                )
                await connection.execute(
                    text("UPDATE embedding_profiles SET active=false WHERE active")
                )

        checkpoint = json.dumps(
            {
                "completed_on": completed_on.isoformat(),
                "record_count": len(records),
                "deduplicated_record_count": len(earliest),
            },
            ensure_ascii=False,
        )
        # Per-document commits are intentionally replayable. The checkpoint moves only
        # after every record succeeds, so a failed run replays the one-day overlap.
        async with self.engine.begin() as connection:
            await connection.execute(
                text("SELECT pg_advisory_xact_lock(:lock_key)"),
                {"lock_key": CORPUS_MUTATION_LOCK_KEY},
            )
            await connection.execute(
                text(
                    """INSERT INTO runtime_flags(key,value,updated_at)
                    VALUES(:key,CAST(:value AS jsonb),now())
                    ON CONFLICT(key) DO UPDATE SET value=excluded.value,updated_at=now()
                    WHERE NULLIF(runtime_flags.value->>'completed_on','') IS NULL
                       OR (runtime_flags.value->>'completed_on')::date<=:completed_on"""
                ),
                {
                    "key": _DELETION_SYNC_FLAG_KEY,
                    "value": checkpoint,
                    "completed_on": completed_on,
                },
            )
        return stats

    async def close(self) -> None:
        await self.storage.close()
        await self.engine.dispose()
