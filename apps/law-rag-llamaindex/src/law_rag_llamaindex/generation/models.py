"""Pure generation catalog values and transformation fingerprints."""

import hashlib
import json
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True)
class RetrievalGeneration:
    """A candidate or published immutable vector generation."""

    id: UUID
    table_name: str
    source_fingerprint: str
    transform_fingerprint: str
    status: str
    source_count: int | None
    node_count: int | None
    failure_code: str | None
    created_at: datetime
    verified_at: datetime | None
    published_at: datetime | None


@dataclass(frozen=True)
class GenerationSource:
    """One source row retained to audit and reuse a generation's vectors."""

    provision_id: str
    source_fingerprint: str
    node_count: int
    copied_from_generation_id: UUID | None = None


def generation_table_name(generation_id: UUID) -> str:
    """Return the server-derived, SQL-identifier-safe vector table name."""

    return f"law_rag_li_{generation_id.hex}"


def _sha256_json(value: object) -> str:
    encoded = json.dumps(
        value, ensure_ascii=False, separators=(",", ":"), sort_keys=True
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def provision_fingerprint(record: Mapping[str, object]) -> str:
    """Fingerprint every canonical field that can affect search or citation."""

    return _sha256_json(
        {
            "provision_id": record["provision_id"],
            "document_id": record["document_id"],
            "document_title": record["document_title"],
            "source_kind": record["source_kind"],
            "law_type_code": record.get("law_type_code"),
            "version_label": record["version_label"],
            "effective_from": record.get("effective_from"),
            "effective_to": record.get("effective_to"),
            "path": record["path"],
            "heading": record.get("heading"),
            "content": record["content"],
            "source_url": record["source_url"],
        }
    )


def source_fingerprint(records: Iterable[Mapping[str, object]]) -> str:
    """Fingerprint a source snapshot independently of database return order."""

    entries = [
        {"provision_id": str(record["provision_id"]), "fingerprint": provision_fingerprint(record)}
        for record in records
    ]
    return _sha256_json(sorted(entries, key=lambda entry: entry["provision_id"]))


def generation_source_records(
    records: Iterable[Mapping[str, object]],
    *,
    node_counts: Mapping[str, int],
    copied_provision_ids: set[str] | None = None,
    copied_from_generation_id: UUID | None = None,
) -> list[dict[str, object]]:
    """Return one auditable source-lineage row for each provision in a generation."""

    if copied_provision_ids and copied_from_generation_id is None:
        raise ValueError("copied generation sources require their origin generation")
    sources = []
    for record in records:
        provision_id = str(record["provision_id"])
        node_count = node_counts.get(provision_id)
        if node_count is None or node_count < 0:
            raise ValueError("each generation source requires a non-negative node count")
        sources.append(
            {
                "provision_id": provision_id,
                "source_fingerprint": provision_fingerprint(record),
                "node_count": node_count,
                "copied_from_generation_id": (
                    copied_from_generation_id
                    if copied_provision_ids and provision_id in copied_provision_ids
                    else None
                ),
            }
        )
    return sources


def transform_fingerprint(
    *,
    chunker_version: str,
    embedding_provider: str,
    embedding_model: str,
    embed_dim: int,
    embedding_profile: str = "default",
) -> str:
    """Fingerprint the transformation contract that defines vector compatibility."""

    if (
        not chunker_version
        or not embedding_provider
        or not embedding_model
        or not embedding_profile
        or embed_dim < 1
    ):
        raise ValueError("transform fingerprint requires a complete transformation contract")
    return _sha256_json(
        {
            "chunker_version": chunker_version,
            "embedding_provider": embedding_provider,
            "embedding_model": embedding_model,
            "embedding_profile": embedding_profile,
            "embed_dim": embed_dim,
        }
    )
