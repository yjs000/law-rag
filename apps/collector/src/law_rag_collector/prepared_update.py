"""Read-only helpers used while preparing a maintenance corpus bundle."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import date
from typing import Protocol
from uuid import UUID

from law_rag_core.corpus_update_bundle import (
    PreparedDeletionRecord,
    PreparedDocumentRecord,
    canonical_corpus_publish_snapshot_id,
    embedding_text_sha256,
    legal_provision_v1_text,
)
from law_rag_core.domain.catalog import SourceKind
from law_rag_core.persistence import (
    CORPUS_PUBLISH_BASE_SELECT_SQL,
    CORPUS_SEARCH_READY_CAPABILITY_SQL,
    SEARCHABLE_DOCUMENT_VERSION_SQL,
)
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from law_rag_collector.deletions import DeletionRecord


class PreparedUpdateRepository(Protocol):
    engine: AsyncEngine


@dataclass(frozen=True, slots=True)
class SearchableCorpusSnapshot:
    snapshot_id: str
    searchable_provision_count: int
    fingerprint_sha256: str


@dataclass(frozen=True, slots=True)
class CurrentEmbeddingSource:
    provision_id: UUID
    source_kind: SourceKind
    source_id: str
    mst: str
    effective_from: date
    document_title: str
    path: str
    heading: str | None
    content: str
    source_text_sha256: str | None
    dimensions: int | None
    norm: float | None
    expected_dimensions: int | None


async def read_searchable_corpus_snapshot(
    repository: PreparedUpdateRepository,
) -> SearchableCorpusSnapshot:
    """Fingerprint every stored version that can participate in retrieval."""

    async with repository.engine.connect() as connection:
        schema_ready = (
            await connection.execute(text(f"SELECT {CORPUS_SEARCH_READY_CAPABILITY_SQL}"))
        ).scalar_one()
        if not schema_ready:
            raise RuntimeError("DB migration 0010 이상이 필요합니다")
        rows = (
            (
                await connection.execute(
                    text(
                        f"""SELECT {CORPUS_PUBLISH_BASE_SELECT_SQL}
                        FROM provisions p
                        JOIN document_versions v ON v.id=p.version_id
                        JOIN legal_documents d ON d.id=v.document_id
                        WHERE {SEARCHABLE_DOCUMENT_VERSION_SQL}
                        ORDER BY p.id"""
                    )
                )
            )
            .mappings()
            .all()
        )
    if not rows:
        raise RuntimeError("현재 검색 가능한 조문이 없습니다")
    snapshot_id = canonical_corpus_publish_snapshot_id(rows)
    fingerprint = snapshot_id.removeprefix("corpus-sha256:")
    return SearchableCorpusSnapshot(snapshot_id, len(rows), fingerprint)


async def preview_source_deletions(
    repository: PreparedUpdateRepository,
    records: Sequence[DeletionRecord],
) -> list[PreparedDeletionRecord]:
    """Mark deletion records that would change a stored version, without writing."""

    earliest: dict[tuple[str, str], DeletionRecord] = {}
    for record in records:
        key = (record.source_kind.value, record.mst)
        previous = earliest.get(key)
        if previous is None or record.deleted_on < previous.deleted_on:
            earliest[key] = record
    if not earliest:
        return []

    kinds = sorted({key[0] for key in earliest})
    msts = sorted({key[1] for key in earliest})
    async with repository.engine.connect() as connection:
        rows = (
            (
                await connection.execute(
                    text(
                        """SELECT d.source_kind::text source_kind,v.mst,
                        v.source_record_state,v.source_deleted_on
                        FROM document_versions v
                        JOIN legal_documents d ON d.id=v.document_id
                        WHERE d.source_kind=ANY(CAST(:source_kinds AS text[]))
                          AND v.mst=ANY(CAST(:msts AS text[]))"""
                    ),
                    {"source_kinds": kinds, "msts": msts},
                )
            )
            .mappings()
            .all()
        )
    existing: dict[tuple[str, str], list[Mapping[str, object]]] = {}
    for row in rows:
        existing.setdefault((str(row["source_kind"]), str(row["mst"])), []).append(row)
    prepared: list[PreparedDeletionRecord] = []
    for key, record in sorted(earliest.items()):
        changed = any(
            row["source_record_state"] != "deleted"
            or row["source_deleted_on"] is None
            or row["source_deleted_on"] > record.deleted_on
            for row in existing.get(key, [])
        )
        prepared.append(
            PreparedDeletionRecord(
                mst=record.mst,
                source_kind=record.source_kind,
                kind_name=record.kind_name,
                deleted_on=record.deleted_on,
                changed=changed,
            )
        )
    return prepared


async def read_current_embedding_sources(
    repository: PreparedUpdateRepository,
    *,
    embedding_profile_key: str,
) -> dict[UUID, CurrentEmbeddingSource]:
    """Read the full searchable passage and target-profile vector provenance."""

    async with repository.engine.connect() as connection:
        rows = (
            (
                await connection.execute(
                text(
                    f"""SELECT p.id,d.source_kind::text source_kind,d.source_id,v.mst,
                    v.effective_from,d.exact_title document_title,
                    p.path,p.heading,p.content,e.source_text_sha256,e.dimensions,
                    CASE WHEN e.embedding IS NULL THEN NULL
                         ELSE vector_norm(e.embedding) END norm,
                    ep.stored_dimensions expected_dimensions
                    FROM provisions p
                    JOIN document_versions v ON v.id=p.version_id
                    JOIN legal_documents d ON d.id=v.document_id
                    LEFT JOIN embedding_profiles ep
                      ON ep.profile_key=:embedding_profile_key
                    LEFT JOIN provision_embeddings e
                      ON e.provision_id=p.id
                     AND e.profile_key=:embedding_profile_key
                    WHERE {SEARCHABLE_DOCUMENT_VERSION_SQL}
                    ORDER BY p.id"""
                ),
                    {"embedding_profile_key": embedding_profile_key},
                )
            )
            .mappings()
            .all()
        )
    return {
        UUID(str(row["id"])): CurrentEmbeddingSource(
            provision_id=UUID(str(row["id"])),
            source_kind=SourceKind(str(row["source_kind"])),
            source_id=str(row["source_id"]),
            mst=str(row["mst"]),
            effective_from=row["effective_from"],
            document_title=str(row["document_title"]),
            path=str(row["path"]),
            heading=str(row["heading"]) if row["heading"] is not None else None,
            content=str(row["content"]),
            source_text_sha256=(
                str(row["source_text_sha256"])
                if row["source_text_sha256"] is not None
                else None
            ),
            dimensions=int(row["dimensions"]) if row["dimensions"] is not None else None,
            norm=float(row["norm"]) if row["norm"] is not None else None,
            expected_dimensions=(
                int(row["expected_dimensions"])
                if row["expected_dimensions"] is not None
                else None
            ),
        )
        for row in rows
    }


def required_embedding_ids_for_prospective_corpus(
    documents: Sequence[PreparedDocumentRecord],
    deletions: Sequence[PreparedDeletionRecord],
    current: Mapping[UUID, CurrentEmbeddingSource],
) -> list[UUID]:
    """Overlay prepared changes on the full stored corpus and find exact vector gaps."""

    prospective = dict(current)
    for document in documents:
        document_key = (document.source_kind, document.source_id)
        for provision_id, source in list(prospective.items()):
            if (source.source_kind, source.source_id) == document_key:
                prospective[provision_id] = replace(
                    source,
                    document_title=document.title,
                )
        incoming_ids = {provision.id for provision in document.provisions}
        for provision_id, source in list(prospective.items()):
            if (
                (source.source_kind, source.source_id) == document_key
                and source.mst == document.mst
                and source.effective_from == document.effective_from
                and provision_id not in incoming_ids
            ):
                del prospective[provision_id]
        for provision in document.provisions:
            stored = current.get(provision.id)
            prospective[provision.id] = CurrentEmbeddingSource(
                provision_id=provision.id,
                source_kind=document.source_kind,
                source_id=document.source_id,
                mst=document.mst,
                effective_from=document.effective_from,
                document_title=document.title,
                path=provision.path,
                heading=provision.heading,
                content=provision.content,
                source_text_sha256=(stored.source_text_sha256 if stored else None),
                dimensions=stored.dimensions if stored else None,
                norm=stored.norm if stored else None,
                expected_dimensions=(stored.expected_dimensions if stored else None),
            )

    deleted_keys = {
        (item.source_kind, item.mst) for item in deletions if item.changed
    }
    prospective = {
        provision_id: source
        for provision_id, source in prospective.items()
        if (source.source_kind, source.mst) not in deleted_keys
    }
    required: list[UUID] = []
    for provision_id, source in prospective.items():
            source_sha = embedding_text_sha256(
                legal_provision_v1_text(
                    document_title=source.document_title,
                    path=source.path,
                    heading=source.heading,
                    content=source.content,
                )
            )
            valid = bool(
                source.source_text_sha256 == source_sha
                and source.expected_dimensions is not None
                and source.dimensions == source.expected_dimensions
                and source.norm is not None
                and abs(source.norm - 1.0) <= 0.00001
            )
            if not valid:
                required.append(provision_id)
    return sorted(required, key=str)


def preview_has_corpus_changes(preview: Mapping[str, object]) -> bool:
    """Interpret the existing repository's read-only document diff."""

    return any(
        (
            bool(preview.get("new_document")),
            bool(preview.get("new_version")),
            bool(preview.get("version_changed")),
            bool(preview.get("title_changed")),
            int(preview.get("would_close_versions") or 0) > 0,
            int(preview.get("new_provisions") or 0) > 0,
            int(preview.get("updated_provisions") or 0) > 0,
            int(preview.get("removed_provisions") or 0) > 0,
            bool(preview.get("embedding_revalidation_required")),
        )
    )


__all__ = [
    "CurrentEmbeddingSource",
    "PreparedUpdateRepository",
    "preview_has_corpus_changes",
    "preview_source_deletions",
    "SearchableCorpusSnapshot",
    "read_current_embedding_sources",
    "read_searchable_corpus_snapshot",
    "required_embedding_ids_for_prospective_corpus",
]
