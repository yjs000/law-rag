import hashlib
from datetime import UTC, date, datetime
from pathlib import Path
from uuid import UUID

import pytest

from law_rag_core.corpus_update_bundle import (
    PreparedDeletionRecord,
    PreparedDocumentRecord,
    PreparedEmbeddingRecord,
    PreparedRawRecord,
    canonical_corpus_population_fingerprint,
    canonical_corpus_snapshot_id,
    finalize_corpus_update_bundle,
    load_corpus_update_bundle,
    write_corpus_update_bundle,
)
from law_rag_core.domain.catalog import SourceKind
from law_rag_core.domain.entities import LegalDocumentRecord, ProvisionRecord

_PROVISION_ID = UUID("11111111-1111-4111-8111-111111111111")
_RAW = '{"법령":"본문"}'
_RAW_SHA = hashlib.sha256(_RAW.encode()).hexdigest()
_BASE_SNAPSHOT = f"corpus-sha256:{'a' * 64}"


def _document(*, changed: bool = True) -> PreparedDocumentRecord:
    domain = LegalDocumentRecord(
        source_id="001",
        mst="1000",
        title="전기사업법",
        source_kind=SourceKind.LAW,
        promulgation_number="1",
        promulgated_on=date(2020, 1, 1),
        effective_from=date(2020, 2, 1),
        ministry="산업통상자원부",
        source_url="https://example.test/law",
        raw_format="JSON",
        raw_sha256=_RAW_SHA,
        provisions=[
            ProvisionRecord(
                id=_PROVISION_ID,
                path="제1조",
                heading="목적",
                content="이 법의 목적",
                ordinal=0,
            )
        ],
    )
    return PreparedDocumentRecord.from_domain(
        domain,
        effective_to=None,
        raw=PreparedRawRecord(
            path=f"raw/law/001/1000-{_RAW_SHA}.json",
            sha256=_RAW_SHA,
            wire_format="JSON",
            source_url=domain.source_url,
        ),
        changed=changed,
        preview={"new_provisions": int(changed)},
    )


def _write(root: Path, *, changed: bool = True):
    document = _document(changed=changed)
    return write_corpus_update_bundle(
        root,
        update_id="update-20260804",
        documents=[document],
        deletions=[
            PreparedDeletionRecord(
                mst="999",
                source_kind=SourceKind.LAW,
                kind_name="법령",
                deleted_on=date(2026, 8, 4),
                changed=False,
            )
        ],
        raw_contents={document.raw.path: _RAW},
        base_snapshot_id=_BASE_SNAPSHOT,
        parser_version="3",
        embedding_profile_key="profile-v1",
        required_embedding_ids=[_PROVISION_ID] if changed else [],
        deletion_window=(date(2026, 8, 3), date(2026, 8, 4)),
        created_at=datetime(2026, 8, 4, tzinfo=UTC),
    )


def test_write_load_and_finalize_bundle(tmp_path: Path) -> None:
    prepared = _write(tmp_path / "bundle")

    assert prepared.manifest.state == "needs_embeddings"
    assert prepared.manifest.changes.required_embedding_ids == [_PROVISION_ID]
    assert prepared.raw_body(prepared.documents[0]) == _RAW
    assert prepared.documents[0].to_legal_document_record().provisions[0].path == "제1조"

    ready = finalize_corpus_update_bundle(
        prepared.root,
        [
            PreparedEmbeddingRecord(
                provision_id=_PROVISION_ID,
                embedding_profile_key="profile-v1",
                dimensions=512,
                source_text_sha256="b" * 64,
                embedding=[1.0, *([0.0] * 511)],
            )
        ],
    )

    assert ready.manifest.state == "ready_to_publish"
    assert ready.manifest.counts.embeddings == 1
    assert ready.embeddings[0].provision_id == _PROVISION_ID


def test_unchanged_bundle_does_not_allow_embedding_finalization(tmp_path: Path) -> None:
    bundle = _write(tmp_path / "bundle", changed=False)

    assert bundle.manifest.state == "unchanged"
    with pytest.raises(ValueError, match="expected needs_embeddings"):
        finalize_corpus_update_bundle(bundle.root, [])


def test_embedding_repair_alone_requires_the_embedding_stage(tmp_path: Path) -> None:
    document = _document(changed=False)
    bundle = write_corpus_update_bundle(
        tmp_path / "repair",
        update_id="repair-20260804",
        documents=[document],
        deletions=[],
        raw_contents={document.raw.path: _RAW},
        base_snapshot_id=_BASE_SNAPSHOT,
        parser_version="3",
        embedding_profile_key="profile-v1",
        required_embedding_ids=[_PROVISION_ID],
        deletion_window=(date(2026, 8, 4), date(2026, 8, 4)),
        created_at=datetime(2026, 8, 4, tzinfo=UTC),
    )

    assert bundle.manifest.state == "needs_embeddings"
    assert bundle.manifest.counts.changed_documents == 0
    assert bundle.manifest.changes.required_embedding_ids == [_PROVISION_ID]


def test_loader_rejects_tampered_and_partial_bundles(tmp_path: Path) -> None:
    bundle = _write(tmp_path / "bundle")
    documents_path = bundle.root / "documents.jsonl"
    documents_path.write_text(documents_path.read_text(encoding="utf-8") + " ", encoding="utf-8")

    with pytest.raises(ValueError, match="checksum mismatch"):
        load_corpus_update_bundle(bundle.root)

    partial = tmp_path / "partial"
    partial.mkdir()
    (partial / "documents.jsonl").write_text("", encoding="utf-8")
    with pytest.raises(ValueError, match="manifest is missing"):
        load_corpus_update_bundle(partial)


def test_snapshot_helpers_are_order_independent_and_date_free() -> None:
    first = [
        "3",
        "document",
        "version",
        "b-provision",
        "전기사업법",
        "law",
        "2020-01-01",
        "제2조",
        None,
        "정의",
        "a" * 64,
    ]
    second = [
        "3",
        "document",
        "version",
        "a-provision",
        "전기사업법",
        "law",
        "2020-01-01",
        "제1조",
        None,
        "목적",
        "b" * 64,
    ]

    fingerprint = canonical_corpus_population_fingerprint([first, second])
    assert fingerprint == canonical_corpus_population_fingerprint([second, first])
    snapshot = canonical_corpus_snapshot_id(
        parser_contract_version="3",
        retrieval_unit="provision",
        content_populations=[
            {"eligible_provision_count": 2, "fingerprint_sha256": fingerprint}
        ],
    )

    assert snapshot.startswith("corpus-sha256:")
    assert len(snapshot) == len("corpus-sha256:") + 64


def test_paths_and_embedding_shapes_are_rejected_before_manifest_publish(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="must start with raw"):
        PreparedRawRecord(
            path="outside.json",
            sha256=_RAW_SHA,
            wire_format="JSON",
            source_url="https://example.test",
        )
    with pytest.raises(ValueError, match="512 stored dimensions"):
        PreparedEmbeddingRecord(
            provision_id=_PROVISION_ID,
            embedding_profile_key="profile-v1",
            dimensions=2,
            source_text_sha256="b" * 64,
            embedding=[1.0],
        )
