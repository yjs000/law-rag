from dataclasses import dataclass, field
from datetime import date
from uuid import UUID

from law_rag_core.domain.catalog import SourceKind


@dataclass(slots=True)
class ProvisionRecord:
    id: UUID
    path: str
    heading: str | None
    content: str
    parent_path: str | None = None
    ordinal: int = 0


@dataclass(slots=True)
class LegalDocumentRecord:
    source_id: str
    mst: str
    title: str
    source_kind: SourceKind
    promulgation_number: str | None
    promulgated_on: date | None
    effective_from: date | None
    ministry: str | None
    source_url: str
    raw_format: str
    raw_sha256: str
    parser_schema_version: str = "1"
    fallback_reason: str | None = None
    raw_storage_path: str | None = None
    provisions: list[ProvisionRecord] = field(default_factory=list)

