"""Validated, content-addressed hand-off for one corpus maintenance update."""

from __future__ import annotations

import hashlib
import json
import math
import os
import tempfile
from collections.abc import Mapping, Sequence
from datetime import date, datetime
from pathlib import Path, PurePosixPath
from typing import Annotated, Any, Literal, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from law_rag_core.domain.catalog import SourceKind
from law_rag_core.domain.entities import LegalDocumentRecord, ProvisionRecord

CORPUS_UPDATE_SCHEMA = "corpus-update-v1"
_DOCUMENTS_FILE = "documents.jsonl"
_DELETIONS_FILE = "deletions.json"
_EMBEDDINGS_FILE = "embeddings.jsonl"

Sha256 = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]
BundleState = Literal["unchanged", "needs_embeddings", "ready_to_publish"]

_PUBLISH_BASE_FIELDS = frozenset(
    {
        "document_id",
        "source_id",
        "exact_title",
        "source_kind",
        "version_id",
        "mst",
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
        "provision_id",
        "path",
        "parent_path",
        "heading",
        "content_sha256",
        "ordinal",
    }
)


class _Record(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, populate_by_name=True)


class PreparedProvisionRecord(_Record):
    id: UUID
    path: str = Field(min_length=1)
    heading: str | None = None
    content: str = Field(min_length=1)
    parent_path: str | None = None
    ordinal: int = Field(ge=0)

    @classmethod
    def from_domain(cls, provision: ProvisionRecord) -> Self:
        return cls(
            id=provision.id,
            path=provision.path,
            heading=provision.heading,
            content=provision.content,
            parent_path=provision.parent_path,
            ordinal=provision.ordinal,
        )

    def to_domain(self) -> ProvisionRecord:
        return ProvisionRecord(
            id=self.id,
            path=self.path,
            heading=self.heading,
            content=self.content,
            parent_path=self.parent_path,
            ordinal=self.ordinal,
        )


class PreparedRawRecord(_Record):
    path: str = Field(min_length=1)
    sha256: Sha256
    wire_format: Literal["JSON", "XML"]
    source_url: str = Field(min_length=1)
    fallback_reason: str | None = None

    @model_validator(mode="after")
    def validate_path(self) -> Self:
        _safe_relative_path(self.path, expected_prefix="raw/")
        expected_suffix = f".{self.wire_format.lower()}"
        if not self.path.endswith(expected_suffix):
            raise ValueError(f"raw path must end with {expected_suffix}")
        return self


class PreparedDocumentRecord(_Record):
    source_id: str = Field(min_length=1)
    mst: str = Field(min_length=1)
    title: str = Field(min_length=1)
    source_kind: SourceKind
    promulgation_number: str | None = None
    promulgated_on: date | None = None
    effective_from: date
    effective_to: date | None = None
    ministry: str | None = None
    source_url: str = Field(min_length=1)
    raw_format: Literal["JSON", "XML"]
    raw_sha256: Sha256
    parser_schema_version: str = Field(min_length=1)
    fallback_reason: str | None = None
    raw: PreparedRawRecord
    provisions: list[PreparedProvisionRecord]
    changed: bool
    preview: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_document(self) -> Self:
        if self.effective_to is not None and self.effective_to <= self.effective_from:
            raise ValueError("effective_to must be later than effective_from")
        if self.raw_format != self.raw.wire_format:
            raise ValueError("document and raw wire formats differ")
        if self.raw_sha256 != self.raw.sha256:
            raise ValueError("document and raw SHA-256 values differ")
        if self.source_url != self.raw.source_url:
            raise ValueError("document and raw source URLs differ")
        provision_ids = [item.id for item in self.provisions]
        if len(provision_ids) != len(set(provision_ids)):
            raise ValueError("document contains duplicate provision IDs")
        return self

    @classmethod
    def from_domain(
        cls,
        document: LegalDocumentRecord,
        *,
        effective_to: date | None,
        raw: PreparedRawRecord,
        changed: bool,
        preview: Mapping[str, Any],
    ) -> Self:
        if document.effective_from is None:
            raise ValueError("prepared documents require effective_from")
        return cls(
            source_id=document.source_id,
            mst=document.mst,
            title=document.title,
            source_kind=document.source_kind,
            promulgation_number=document.promulgation_number,
            promulgated_on=document.promulgated_on,
            effective_from=document.effective_from,
            effective_to=effective_to,
            ministry=document.ministry,
            source_url=document.source_url,
            raw_format=document.raw_format,
            raw_sha256=document.raw_sha256,
            parser_schema_version=document.parser_schema_version,
            fallback_reason=document.fallback_reason,
            raw=raw,
            provisions=[PreparedProvisionRecord.from_domain(item) for item in document.provisions],
            changed=changed,
            preview=dict(preview),
        )

    def to_legal_document_record(self) -> LegalDocumentRecord:
        return LegalDocumentRecord(
            source_id=self.source_id,
            mst=self.mst,
            title=self.title,
            source_kind=self.source_kind,
            promulgation_number=self.promulgation_number,
            promulgated_on=self.promulgated_on,
            effective_from=self.effective_from,
            ministry=self.ministry,
            source_url=self.source_url,
            raw_format=self.raw_format,
            raw_sha256=self.raw_sha256,
            parser_schema_version=self.parser_schema_version,
            fallback_reason=self.fallback_reason,
            provisions=[item.to_domain() for item in self.provisions],
        )

    def to_domain(self) -> LegalDocumentRecord:
        """Backward-compatible short alias for internal callers."""

        return self.to_legal_document_record()


class PreparedDeletionRecord(_Record):
    mst: str = Field(min_length=1)
    source_kind: SourceKind
    kind_name: str = Field(min_length=1)
    deleted_on: date
    changed: bool


class PreparedEmbeddingRecord(_Record):
    provision_id: UUID
    embedding_profile_key: str = Field(min_length=1)
    dimensions: int = Field(gt=0)
    source_text_sha256: Sha256
    embedding: list[float]

    @model_validator(mode="after")
    def validate_embedding(self) -> Self:
        if self.dimensions != 512:
            raise ValueError("prepared embeddings must use 512 stored dimensions")
        if len(self.embedding) != self.dimensions:
            raise ValueError("embedding length does not match dimensions")
        if not all(math.isfinite(value) for value in self.embedding):
            raise ValueError("embedding contains a non-finite value")
        norm = math.sqrt(math.fsum(value * value for value in self.embedding))
        if abs(norm - 1.0) > 0.0001:
            raise ValueError("embedding must be L2-normalized")
        return self


class CorpusUpdateCounts(_Record):
    documents: int = Field(ge=0)
    changed_documents: int = Field(ge=0)
    provisions: int = Field(ge=0)
    deletions: int = Field(ge=0)
    changed_deletions: int = Field(ge=0)
    embeddings: int = Field(ge=0)


class CorpusUpdateChanges(_Record):
    documents: list[str] = Field(default_factory=list)
    deletions: list[str] = Field(default_factory=list)
    required_embedding_ids: list[UUID] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_unique_sorted_values(self) -> Self:
        for name in ("documents", "deletions", "required_embedding_ids"):
            values = getattr(self, name)
            if values != sorted(set(values), key=str):
                raise ValueError(f"manifest change list must be sorted and unique: {name}")
        return self


class CorpusUpdateManifest(_Record):
    schema_version: Literal["corpus-update-v1"] = Field(
        default=CORPUS_UPDATE_SCHEMA,
        alias="schema",
    )
    update_id: str = Field(min_length=1, pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
    state: BundleState
    created_at: datetime
    base_snapshot_id: str = Field(pattern=r"^corpus-sha256:[0-9a-f]{64}$")
    parser_version: str = Field(min_length=1)
    embedding_profile_key: str = Field(min_length=1)
    deletion_window_from: date
    deletion_window_to: date
    counts: CorpusUpdateCounts
    changes: CorpusUpdateChanges
    files: dict[str, Sha256]
    bundle_sha256: Sha256

    @model_validator(mode="after")
    def validate_manifest(self) -> Self:
        if self.created_at.tzinfo is None or self.created_at.utcoffset() is None:
            raise ValueError("created_at must include a timezone")
        if self.deletion_window_from > self.deletion_window_to:
            raise ValueError("deletion window is reversed")
        for path in self.files:
            _safe_relative_path(path)
        required = {_DOCUMENTS_FILE, _DELETIONS_FILE}
        if not required.issubset(self.files):
            raise ValueError("manifest is missing required bundle files")
        if self.state == "ready_to_publish" and _EMBEDDINGS_FILE not in self.files:
            raise ValueError("ready bundle is missing embeddings.jsonl")
        if self.state != "ready_to_publish" and _EMBEDDINGS_FILE in self.files:
            raise ValueError("unfinished bundle cannot declare embeddings.jsonl")
        if len(self.changes.documents) != self.counts.changed_documents:
            raise ValueError("changed document count does not match manifest changes")
        if len(self.changes.deletions) != self.counts.changed_deletions:
            raise ValueError("changed deletion count does not match manifest changes")
        has_work = bool(
            self.changes.documents
            or self.changes.deletions
            or self.changes.required_embedding_ids
        )
        if self.state == "unchanged" and has_work:
            raise ValueError("unchanged bundle cannot declare changes")
        if self.state == "needs_embeddings" and not has_work:
            raise ValueError("needs_embeddings bundle must declare pending work")
        return self


class CorpusUpdateBundle(_Record):
    root: Path
    manifest: CorpusUpdateManifest
    documents: list[PreparedDocumentRecord]
    deletions: list[PreparedDeletionRecord]
    embeddings: list[PreparedEmbeddingRecord] = Field(default_factory=list)

    def raw_body(self, document: PreparedDocumentRecord) -> str:
        if document not in self.documents:
            raise ValueError("document is not part of this bundle")
        return (self.root / _safe_relative_path(document.raw.path)).read_text(encoding="utf-8")


def canonical_corpus_population_fingerprint(rows: Sequence[Sequence[object]]) -> str:
    """Hash one provision population using the existing 11-field v1 contract."""

    if any(len(row) != 11 for row in rows):
        raise ValueError("corpus population rows must use the 11-field v1 contract")
    provision_ids = [str(row[3]) for row in rows]
    if len(provision_ids) != len(set(provision_ids)):
        raise ValueError("corpus population provision IDs must be unique")
    normalized = [[_json_scalar(value) for value in row] for row in rows]
    ordered = sorted(normalized, key=lambda row: str(row[3]))
    serialized = json.dumps(ordered, ensure_ascii=False, separators=(", ", ": "))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def canonical_corpus_snapshot_id(
    *,
    parser_contract_version: str,
    retrieval_unit: str,
    content_populations: Sequence[Mapping[str, object]],
) -> str:
    """Identify corpus content without including the date used to select it."""

    if not content_populations:
        raise ValueError("at least one corpus content population is required")
    identities: set[tuple[int, str]] = set()
    for population in content_populations:
        raw_count = population["eligible_provision_count"]
        if isinstance(raw_count, bool):
            raise ValueError("eligible provision count must be a positive integer")
        count = int(raw_count)
        fingerprint = str(population["fingerprint_sha256"])
        if count <= 0:
            raise ValueError("eligible provision count must be positive")
        if not _is_sha256(fingerprint):
            raise ValueError("population fingerprint must be lowercase SHA-256")
        identities.add((count, fingerprint))
    payload = {
        "contract": "corpus-population-content-v1",
        "parser_contract_version": parser_contract_version,
        "retrieval_unit": retrieval_unit,
        "content_populations": [
            {"eligible_provision_count": count, "fingerprint_sha256": fingerprint}
            for count, fingerprint in sorted(identities)
        ],
    }
    digest = _sha256_bytes(_canonical_json(payload).encode("utf-8"))
    return f"corpus-sha256:{digest}"


def canonical_corpus_publish_snapshot_id(
    rows: Sequence[Mapping[str, object]],
) -> str:
    """Hash every mutation-relevant field used as a prepared publish precondition."""

    if not rows:
        raise ValueError("at least one publish base row is required")
    if any(set(row) != _PUBLISH_BASE_FIELDS for row in rows):
        raise ValueError("publish base rows do not match the v1 field contract")
    provision_ids = [str(row["provision_id"]) for row in rows]
    if len(provision_ids) != len(set(provision_ids)):
        raise ValueError("publish base provision IDs must be unique")
    normalized = [
        {key: _json_scalar(row[key]) for key in sorted(_PUBLISH_BASE_FIELDS)}
        for row in rows
    ]
    payload = {
        "contract": "corpus-publish-base-v1",
        "rows": sorted(normalized, key=lambda row: str(row["provision_id"])),
    }
    return f"corpus-sha256:{_sha256_bytes(_canonical_json(payload).encode('utf-8'))}"


def legal_provision_v1_text(
    *, document_title: str, path: str, heading: str | None, content: str
) -> str:
    """Build the shared legal-provision-v1 passage text."""

    return "\n".join(
        part.strip()
        for part in (document_title, path, heading or "", content)
        if part and part.strip()
    )


def embedding_text_sha256(text: str) -> str:
    return _sha256_bytes(text.encode("utf-8"))


def write_corpus_update_bundle(
    root: Path,
    *,
    update_id: str,
    documents: Sequence[PreparedDocumentRecord],
    deletions: Sequence[PreparedDeletionRecord],
    raw_contents: Mapping[str, str],
    base_snapshot_id: str,
    parser_version: str,
    embedding_profile_key: str,
    required_embedding_ids: Sequence[UUID],
    deletion_window: tuple[date, date],
    created_at: datetime,
) -> CorpusUpdateBundle:
    """Write a prepared bundle and publish its manifest as the last filesystem action."""

    if root.exists() and any(root.iterdir()):
        raise FileExistsError(f"bundle directory is not empty: {root}")
    root.mkdir(parents=True, exist_ok=True)
    ordered_documents = sorted(
        documents,
        key=lambda item: (item.source_kind.value, item.source_id, item.effective_from, item.mst),
    )
    ordered_deletions = sorted(
        deletions,
        key=lambda item: (item.source_kind.value, item.mst, item.deleted_on),
    )
    expected_raw_paths = {item.raw.path for item in ordered_documents}
    if set(raw_contents) != expected_raw_paths:
        raise ValueError("raw contents do not exactly match document raw paths")
    files: dict[str, str] = {}
    for document in ordered_documents:
        body = raw_contents[document.raw.path]
        body_sha = _sha256_bytes(body.encode("utf-8"))
        if body_sha != document.raw.sha256:
            raise ValueError(f"raw SHA-256 mismatch: {document.raw.path}")
        destination = root / _safe_relative_path(document.raw.path)
        _atomic_write(destination, body)
        files[document.raw.path] = body_sha

    document_content = _jsonl(ordered_documents)
    deletion_content = _canonical_json(
        [item.model_dump(mode="json") for item in ordered_deletions], pretty=True
    )
    _atomic_write(root / _DOCUMENTS_FILE, document_content)
    _atomic_write(root / _DELETIONS_FILE, deletion_content)
    files[_DOCUMENTS_FILE] = _sha256_bytes(document_content.encode("utf-8"))
    files[_DELETIONS_FILE] = _sha256_bytes(deletion_content.encode("utf-8"))

    changes = _changes(ordered_documents, ordered_deletions, required_embedding_ids)
    changed = bool(changes.documents or changes.deletions or changes.required_embedding_ids)
    counts = _counts(ordered_documents, ordered_deletions, ())
    manifest = _build_manifest(
        update_id=update_id,
        state="needs_embeddings" if changed else "unchanged",
        created_at=created_at,
        base_snapshot_id=base_snapshot_id,
        parser_version=parser_version,
        embedding_profile_key=embedding_profile_key,
        deletion_window=deletion_window,
        counts=counts,
        changes=changes,
        files=files,
    )
    _write_manifest(root, manifest)
    return load_corpus_update_bundle(root)


def finalize_corpus_update_bundle(
    root: Path,
    embeddings: Sequence[PreparedEmbeddingRecord],
) -> CorpusUpdateBundle:
    """Atomically publish embeddings and move a prepared bundle to ready_to_publish."""

    bundle = load_corpus_update_bundle(root, expected_state="needs_embeddings")
    ordered = sorted(embeddings, key=lambda item: str(item.provision_id))
    ids = [item.provision_id for item in ordered]
    if len(ids) != len(set(ids)):
        raise ValueError("embedding records contain duplicate provision IDs")
    if not set(bundle.manifest.changes.required_embedding_ids).issubset(ids):
        raise ValueError("embedding records omit required embedding IDs")
    if any(
        item.embedding_profile_key != bundle.manifest.embedding_profile_key for item in ordered
    ):
        raise ValueError("embedding profile does not match the bundle manifest")

    content = _jsonl(ordered)
    _atomic_write(root / _EMBEDDINGS_FILE, content)
    files = {**bundle.manifest.files, _EMBEDDINGS_FILE: _sha256_bytes(content.encode("utf-8"))}
    manifest = _build_manifest(
        update_id=bundle.manifest.update_id,
        state="ready_to_publish",
        created_at=bundle.manifest.created_at,
        base_snapshot_id=bundle.manifest.base_snapshot_id,
        parser_version=bundle.manifest.parser_version,
        embedding_profile_key=bundle.manifest.embedding_profile_key,
        deletion_window=(
            bundle.manifest.deletion_window_from,
            bundle.manifest.deletion_window_to,
        ),
        counts=_counts(bundle.documents, bundle.deletions, ordered),
        changes=CorpusUpdateChanges(
            documents=bundle.manifest.changes.documents,
            deletions=bundle.manifest.changes.deletions,
            required_embedding_ids=ids,
        ),
        files=files,
    )
    _write_manifest(root, manifest)
    return load_corpus_update_bundle(root, expected_state="ready_to_publish")


def load_corpus_update_bundle(
    root: Path,
    *,
    expected_state: BundleState | None = None,
) -> CorpusUpdateBundle:
    """Load a complete bundle, rejecting partial files, traversal, and tampering."""

    manifest_path = root / "manifest.json"
    if not manifest_path.is_file():
        raise ValueError("bundle manifest is missing")
    try:
        manifest = CorpusUpdateManifest.model_validate_json(
            manifest_path.read_text(encoding="utf-8")
        )
    except (OSError, ValueError) as exc:
        raise ValueError("bundle manifest is invalid") from exc
    if expected_state is not None and manifest.state != expected_state:
        raise ValueError(
            f"bundle state is {manifest.state}, expected {expected_state}"
        )
    expected_bundle_sha = _manifest_bundle_sha(
        manifest.model_dump(mode="json", by_alias=True)
    )
    if manifest.bundle_sha256 != expected_bundle_sha:
        raise ValueError("bundle manifest checksum is invalid")
    for relative_path, expected_sha in manifest.files.items():
        path = root / _safe_relative_path(relative_path)
        if not path.is_file():
            raise ValueError(f"bundle file is missing: {relative_path}")
        if _sha256_path(path) != expected_sha:
            raise ValueError(f"bundle file checksum mismatch: {relative_path}")

    documents = _read_jsonl(root / _DOCUMENTS_FILE, PreparedDocumentRecord)
    deletions_payload = json.loads((root / _DELETIONS_FILE).read_text(encoding="utf-8"))
    if not isinstance(deletions_payload, list):
        raise ValueError("deletions.json must contain an array")
    deletions = [PreparedDeletionRecord.model_validate(item) for item in deletions_payload]
    embeddings = (
        _read_jsonl(root / _EMBEDDINGS_FILE, PreparedEmbeddingRecord)
        if manifest.state == "ready_to_publish"
        else []
    )
    if _counts(documents, deletions, embeddings) != manifest.counts:
        raise ValueError("bundle counts do not match its files")
    if any(item.parser_schema_version != manifest.parser_version for item in documents):
        raise ValueError("document parser version does not match manifest")
    raw_paths = {item.raw.path for item in documents}
    declared_raw_paths = {path for path in manifest.files if path.startswith("raw/")}
    if raw_paths != declared_raw_paths:
        raise ValueError("manifest raw file set does not match documents")
    for document in documents:
        if manifest.files[document.raw.path] != document.raw.sha256:
            raise ValueError("raw manifest checksum does not match document metadata")
    return CorpusUpdateBundle(
        root=root.resolve(),
        manifest=manifest,
        documents=documents,
        deletions=deletions,
        embeddings=embeddings,
    )


def _build_manifest(
    *,
    update_id: str,
    state: BundleState,
    created_at: datetime,
    base_snapshot_id: str,
    parser_version: str,
    embedding_profile_key: str,
    deletion_window: tuple[date, date],
    counts: CorpusUpdateCounts,
    changes: CorpusUpdateChanges,
    files: Mapping[str, str],
) -> CorpusUpdateManifest:
    payload: dict[str, Any] = {
        "schema": CORPUS_UPDATE_SCHEMA,
        "update_id": update_id,
        "state": state,
        "created_at": created_at,
        "base_snapshot_id": base_snapshot_id,
        "parser_version": parser_version,
        "embedding_profile_key": embedding_profile_key,
        "deletion_window_from": deletion_window[0],
        "deletion_window_to": deletion_window[1],
        "counts": counts,
        "changes": changes,
        "files": dict(sorted(files.items())),
    }
    dumped = CorpusUpdateManifest.model_validate(
        {**payload, "bundle_sha256": "0" * 64}
    ).model_dump(mode="json", by_alias=True)
    return CorpusUpdateManifest.model_validate(
        {**payload, "bundle_sha256": _manifest_bundle_sha(dumped)}
    )


def _manifest_bundle_sha(payload: Mapping[str, Any]) -> str:
    without_self = {key: value for key, value in payload.items() if key != "bundle_sha256"}
    return _sha256_bytes(_canonical_json(without_self).encode("utf-8"))


def _counts(
    documents: Sequence[PreparedDocumentRecord],
    deletions: Sequence[PreparedDeletionRecord],
    embeddings: Sequence[PreparedEmbeddingRecord],
) -> CorpusUpdateCounts:
    return CorpusUpdateCounts(
        documents=len(documents),
        changed_documents=sum(item.changed for item in documents),
        provisions=sum(len(item.provisions) for item in documents),
        deletions=len(deletions),
        changed_deletions=sum(item.changed for item in deletions),
        embeddings=len(embeddings),
    )


def _changes(
    documents: Sequence[PreparedDocumentRecord],
    deletions: Sequence[PreparedDeletionRecord],
    required_embedding_ids: Sequence[UUID],
) -> CorpusUpdateChanges:
    return CorpusUpdateChanges(
        documents=sorted(
            f"{item.source_kind.value}:{item.source_id}:{item.mst}:"
            f"{item.effective_from.isoformat()}"
            for item in documents
            if item.changed
        ),
        deletions=sorted(
            f"{item.source_kind.value}:{item.mst}:{item.deleted_on.isoformat()}"
            for item in deletions
            if item.changed
        ),
        required_embedding_ids=sorted(set(required_embedding_ids), key=str),
    )


def _write_manifest(root: Path, manifest: CorpusUpdateManifest) -> None:
    content = _canonical_json(
        manifest.model_dump(mode="json", by_alias=True),
        pretty=True,
    )
    _atomic_write(root / "manifest.json", content)


def _jsonl(records: Sequence[BaseModel]) -> str:
    if not records:
        return ""
    return "".join(
        f"{_canonical_json(record.model_dump(mode='json'))}\n" for record in records
    )


def _read_jsonl[T: BaseModel](path: Path, model: type[T]) -> list[T]:
    records: list[T] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            raise ValueError(f"blank JSONL record at {path.name}:{line_number}")
        try:
            records.append(model.model_validate_json(line))
        except ValueError as exc:
            raise ValueError(f"invalid JSONL record at {path.name}:{line_number}") from exc
    return records


def _canonical_json(value: Any, *, pretty: bool = False) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        indent=2 if pretty else None,
        separators=None if pretty else (",", ":"),
        sort_keys=True,
        default=str,
    ) + ("\n" if pretty else "")


def _atomic_write(destination: Path, content: str) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="\n",
            dir=destination.parent,
            prefix=f".{destination.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temporary = Path(handle.name)
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, destination)
        temporary = None
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def _safe_relative_path(value: str, *, expected_prefix: str | None = None) -> Path:
    pure = PurePosixPath(value)
    if (
        not value
        or pure.is_absolute()
        or "\\" in value
        or any(part in {"", ".", ".."} for part in pure.parts)
    ):
        raise ValueError(f"unsafe bundle path: {value!r}")
    if expected_prefix is not None and not value.startswith(expected_prefix):
        raise ValueError(f"bundle path must start with {expected_prefix}")
    return Path(*pure.parts)


def _json_scalar(value: object) -> object:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def _is_sha256(value: str) -> bool:
    return len(value) == 64 and all(character in "0123456789abcdef" for character in value)


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


__all__ = [
    "CORPUS_UPDATE_SCHEMA",
    "CorpusUpdateBundle",
    "CorpusUpdateChanges",
    "CorpusUpdateManifest",
    "PreparedDeletionRecord",
    "PreparedDocumentRecord",
    "PreparedEmbeddingRecord",
    "PreparedProvisionRecord",
    "PreparedRawRecord",
    "canonical_corpus_population_fingerprint",
    "canonical_corpus_publish_snapshot_id",
    "canonical_corpus_snapshot_id",
    "embedding_text_sha256",
    "finalize_corpus_update_bundle",
    "load_corpus_update_bundle",
    "legal_provision_v1_text",
    "write_corpus_update_bundle",
]
