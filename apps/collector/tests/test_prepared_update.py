import hashlib
from datetime import date
from pathlib import Path
from uuid import UUID

import pytest
from law_rag_core.corpus_update_bundle import (
    PreparedDocumentRecord,
    PreparedRawRecord,
    embedding_text_sha256,
    legal_provision_v1_text,
)
from law_rag_core.domain.catalog import CatalogEntry, SourceKind
from law_rag_core.domain.entities import LegalDocumentRecord, ProvisionRecord
from law_rag_core.domain.identifiers import canonical_provision_id

from law_rag_collector.client import ParsedResponse, RawResponse, SearchRecord
from law_rag_collector.deletions import DeletionRecord
from law_rag_collector.prepared_update import (
    CurrentEmbeddingSource,
    preview_source_deletions,
    required_embedding_ids_for_prospective_corpus,
)
from law_rag_collector.service import CollectorService

_RAW_BODY = '{"법령":"본문"}'
_RAW_SHA = hashlib.sha256(_RAW_BODY.encode()).hexdigest()
_DOCUMENT_ID = "11111111-1111-4111-8111-111111111111"
_VERSION_ID = "22222222-2222-4222-8222-222222222222"
_PROVISION_ID = UUID("33333333-3333-4333-8333-333333333333")


class _Result:
    def __init__(self, *, scalar=None, rows=()):
        self._scalar = scalar
        self._rows = list(rows)

    def scalar_one(self):
        return self._scalar

    def all(self):
        return self._rows

    def mappings(self):
        return self


class _Connection:
    def __init__(self, engine):
        self.engine = engine

    async def execute(self, statement, params=None):
        sql = str(statement)
        self.engine.calls.append((sql, params))
        if "schema.corpus_search_ready_v1" in sql:
            return _Result(scalar=True)
        if "LEFT JOIN embedding_profiles" in sql:
            return _Result(rows=self.engine.repair_rows)
        if "content_sha256" in sql and "FROM provisions" in sql:
            index = self.engine.population_reads
            self.engine.population_reads += 1
            rows = self.engine.population_versions[
                min(index, len(self.engine.population_versions) - 1)
            ]
            return _Result(rows=rows)
        if "v.source_deleted_on" in sql:
            return _Result(rows=self.engine.deletion_rows)
        raise AssertionError(f"unexpected SQL: {sql}")


class _ConnectionContext:
    def __init__(self, connection):
        self.connection = connection

    async def __aenter__(self):
        return self.connection

    async def __aexit__(self, *_):
        return False


class _Engine:
    def __init__(self, *, population_versions=None, repair_rows=(), deletion_rows=()):
        base_row = {
            "document_id": _DOCUMENT_ID,
            "source_id": "001",
            "exact_title": "전기사업법",
            "source_kind": "law",
            "version_id": _VERSION_ID,
            "mst": "1000",
            "promulgation_number": "1",
            "promulgated_on": date(2020, 1, 1),
            "effective_from": date(2020, 1, 1),
            "effective_to": None,
            "ministry": "산업통상자원부",
            "source_url": "https://example.test/law",
            "raw_format": "JSON",
            "raw_sha256": _RAW_SHA,
            "raw_storage_path": f"law/1000-{_RAW_SHA}.json",
            "parser_schema_version": "3",
            "fallback_reason": None,
            "lifecycle_state": "active",
            "source_record_state": "available",
            "source_deleted_on": None,
            "has_supplementary_provisions": False,
            "provision_id": str(_PROVISION_ID),
            "path": "제1조",
            "parent_path": None,
            "heading": "목적",
            "content_sha256": "a" * 64,
            "ordinal": 0,
        }
        self.population_versions = population_versions or [[base_row]]
        self.repair_rows = list(repair_rows)
        self.deletion_rows = list(deletion_rows)
        self.population_reads = 0
        self.calls = []

    def connect(self):
        return _ConnectionContext(_Connection(self))


class _Repository:
    def __init__(self, engine: _Engine, *, changed: bool):
        self.engine = engine
        self.changed = changed
        self.preview_calls = 0

    async def preview(self, document, raw, *, effective_to):
        self.preview_calls += 1
        return {
            "title": document.title,
            "source_id": document.source_id,
            "mst": document.mst,
            "effective_from": document.effective_from.isoformat(),
            "effective_to": effective_to,
            "new_document": self.changed,
            "new_version": self.changed,
            "version_changed": self.changed,
            "title_changed": False,
            "would_close_versions": 0,
            "new_provisions": int(self.changed),
            "updated_provisions": 0,
            "removed_provisions": 0,
            "embedding_revalidation_required": self.changed,
        }

    async def deletion_window(self, *, today):
        return today, today


class _Client:
    def __init__(self, document: LegalDocumentRecord):
        self.document_value = document
        self.raw = RawResponse(_RAW_BODY, "JSON", document.source_url)

    async def search(self, title, source_kind):
        return ParsedResponse(
            [
                SearchRecord(
                    title=title,
                    source_id=self.document_value.source_id,
                    mst=self.document_value.mst,
                    effective_date="20200101",
                    detail_link="",
                )
            ],
            self.raw,
        )

    async def document(self, **_):
        return ParsedResponse(self.document_value, self.raw)

    async def deleted_records(self, **_):
        return ParsedResponse([], self.raw)


def _document() -> LegalDocumentRecord:
    effective_from = date(2020, 1, 1)
    return LegalDocumentRecord(
        source_id="001",
        mst="1000",
        title="전기사업법",
        source_kind=SourceKind.LAW,
        promulgation_number="1",
        promulgated_on=effective_from,
        effective_from=effective_from,
        ministry="산업통상자원부",
        source_url="https://example.test/law",
        raw_format="JSON",
        raw_sha256=_RAW_SHA,
        provisions=[
            ProvisionRecord(
                id=canonical_provision_id(
                    source_kind=SourceKind.LAW,
                    source_id="001",
                    mst="1000",
                    effective_from=effective_from,
                    path="제1조",
                ),
                path="제1조",
                heading="목적",
                content="목적 본문",
            )
        ],
    )


@pytest.mark.asyncio
async def test_prepare_current_only_reads_db_and_writes_local_bundle(tmp_path: Path) -> None:
    engine = _Engine()
    repository = _Repository(engine, changed=True)
    document = _document()
    service = CollectorService(
        _Client(document),  # type: ignore[arg-type]
        repository,  # type: ignore[arg-type]
        today=lambda: date(2026, 8, 4),
    )

    bundle = await service.prepare_current(
        output=tmp_path / "update-1",
        embedding_profile_key="profile-v1",
        entries=[CatalogEntry(document.title, SourceKind.LAW, 1)],
    )

    assert bundle.manifest.state == "needs_embeddings"
    assert bundle.manifest.counts.documents == 1
    assert bundle.manifest.changes.documents == ["law:001:1000:2020-01-01"]
    assert bundle.manifest.changes.required_embedding_ids == [document.provisions[0].id]
    assert repository.preview_calls == 1
    normalized = [sql.lstrip().upper() for sql, _ in engine.calls]
    assert all(sql.startswith("SELECT") for sql in normalized)
    assert not any("ADVISORY" in sql for sql in normalized)


@pytest.mark.asyncio
async def test_prepare_current_rejects_a_changed_base_snapshot(tmp_path: Path) -> None:
    first = _Engine().population_versions[0][0]
    changed = {**first, "effective_to": date(2026, 8, 4)}
    engine = _Engine(population_versions=[[first], [changed]])
    document = _document()
    service = CollectorService(
        _Client(document),  # type: ignore[arg-type]
        _Repository(engine, changed=False),  # type: ignore[arg-type]
        today=lambda: date(2026, 8, 4),
    )

    with pytest.raises(RuntimeError, match="기준 코퍼스가 변경"):
        await service.prepare_current(
            output=tmp_path / "update-2",
            embedding_profile_key="profile-v1",
            entries=[CatalogEntry(document.title, SourceKind.LAW, 1)],
        )

    assert not (tmp_path / "update-2" / "manifest.json").exists()


@pytest.mark.asyncio
async def test_deletion_preview_marks_only_rows_that_would_change() -> None:
    deleted_on = date(2026, 8, 4)
    engine = _Engine(
        deletion_rows=[
            {
                "source_kind": "law",
                "mst": "1000",
                "source_record_state": "available",
                "source_deleted_on": None,
            },
            {
                "source_kind": "law",
                "mst": "2000",
                "source_record_state": "deleted",
                "source_deleted_on": deleted_on,
            },
        ]
    )
    repository = _Repository(engine, changed=False)

    prepared = await preview_source_deletions(
        repository,  # type: ignore[arg-type]
        [
            DeletionRecord("1000", SourceKind.LAW, "법령", deleted_on),
            DeletionRecord("2000", SourceKind.LAW, "법령", deleted_on),
        ],
    )

    assert [(item.mst, item.changed) for item in prepared] == [
        ("1000", True),
        ("2000", False),
    ]


def test_title_change_requires_vectors_for_current_and_historical_versions() -> None:
    domain = _document()
    domain.title = "전기사업법 새 명칭"
    incoming = PreparedDocumentRecord.from_domain(
        domain,
        effective_to=None,
        raw=PreparedRawRecord(
            path=f"raw/law/001/1000-{_RAW_SHA}.json",
            sha256=_RAW_SHA,
            wire_format="JSON",
            source_url=domain.source_url,
        ),
        changed=True,
        preview={"title_changed": True},
    )
    historic_id = UUID("44444444-4444-4444-8444-444444444444")

    def source(provision_id, *, mst, effective_from, path, heading, content):
        old_sha = embedding_text_sha256(
            legal_provision_v1_text(
                document_title="전기사업법",
                path=path,
                heading=heading,
                content=content,
            )
        )
        return CurrentEmbeddingSource(
            provision_id=provision_id,
            source_kind=SourceKind.LAW,
            source_id="001",
            mst=mst,
            effective_from=effective_from,
            document_title="전기사업법",
            path=path,
            heading=heading,
            content=content,
            source_text_sha256=old_sha,
            dimensions=512,
            norm=1.0,
            expected_dimensions=512,
        )

    current = {
        domain.provisions[0].id: source(
            domain.provisions[0].id,
            mst=domain.mst,
            effective_from=domain.effective_from,
            path=domain.provisions[0].path,
            heading=domain.provisions[0].heading,
            content=domain.provisions[0].content,
        ),
        historic_id: source(
            historic_id,
            mst="900",
            effective_from=date(2019, 1, 1),
            path="제1조",
            heading="목적",
            content="과거 목적 본문",
        ),
    }

    required = required_embedding_ids_for_prospective_corpus([incoming], [], current)

    assert required == sorted([domain.provisions[0].id, historic_id], key=str)
