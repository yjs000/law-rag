from uuid import UUID

import pytest

from law_rag_llamaindex.generations import (
    GenerationCatalog,
    GenerationStateError,
    generation_table_name,
    provision_fingerprint,
    source_fingerprint,
    transform_fingerprint,
)


def _record(*, version_label: str = "MST 1", source_url: str = "https://example.test") -> dict:
    return {
        "provision_id": "a",
        "document_id": "doc-1",
        "document_title": "에너지법",
        "source_kind": "law",
        "law_type_code": "01",
        "version_label": version_label,
        "effective_from": "2024-01-01",
        "effective_to": None,
        "path": "제1조",
        "heading": None,
        "content": "본문",
        "source_url": source_url,
    }


def test_generation_table_name_is_stable_and_allowlisted() -> None:
    generation_id = UUID("12345678-1234-5678-1234-567812345678")

    assert generation_table_name(generation_id) == "law_rag_li_12345678123456781234567812345678"


def test_publish_switches_active_only_after_generation_is_verified() -> None:
    catalog = GenerationCatalog()
    previous = catalog.start("source-v1", "transform-v1")
    catalog.verify(previous.id, source_count=2, node_count=3)
    catalog.publish(previous.id)

    candidate = catalog.start("source-v2", "transform-v1")

    with pytest.raises(GenerationStateError, match="verified"):
        catalog.publish(candidate.id)

    assert catalog.active() is not None
    assert catalog.active().id == previous.id
    assert catalog.active().status == "active"


def test_failed_generation_cannot_replace_active_generation() -> None:
    catalog = GenerationCatalog()
    active = catalog.start("source-v1", "transform-v1")
    catalog.verify(active.id, source_count=1, node_count=1)
    catalog.publish(active.id)

    failed = catalog.start("source-v2", "transform-v1")
    catalog.fail(failed.id, "embedding_failed")

    assert catalog.active() is not None
    assert catalog.active().id == active.id
    assert catalog.active().status == "active"
    assert catalog.get(failed.id).status == "failed"


def test_provision_fingerprint_changes_when_citation_metadata_changes() -> None:
    current = _record()

    assert provision_fingerprint(current) != provision_fingerprint(_record(version_label="MST 2"))
    assert provision_fingerprint(current) != provision_fingerprint(
        _record(source_url="https://other.example.test")
    )


def test_source_fingerprint_is_independent_of_database_row_order() -> None:
    first = _record()
    second = {**_record(), "provision_id": "b", "content": "다른 본문"}

    assert source_fingerprint([first, second]) == source_fingerprint([second, first])


def test_transform_fingerprint_changes_for_embedding_or_chunker_contract() -> None:
    baseline = transform_fingerprint(
        chunker_version="law-chunker-v1",
        embedding_provider="nvidia",
        embedding_model="nvidia/nemotron-3-embed-1b",
        embed_dim=2048,
    )

    assert baseline != transform_fingerprint(
        chunker_version="law-chunker-v2",
        embedding_provider="nvidia",
        embedding_model="nvidia/nemotron-3-embed-1b",
        embed_dim=2048,
    )
    assert baseline != transform_fingerprint(
        chunker_version="law-chunker-v1",
        embedding_provider="nvidia",
        embedding_model="other-model",
        embed_dim=2048,
    )
