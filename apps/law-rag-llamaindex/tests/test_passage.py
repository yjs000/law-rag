from law_rag_llamaindex.passage import (
    ProvisionRecord,
    build_node_metadata,
    build_passage_text,
    compute_source_text_sha256,
)


def _record(**overrides: object) -> ProvisionRecord:
    base: ProvisionRecord = {
        "provision_id": "11111111-1111-1111-1111-111111111111",
        "document_id": "22222222-2222-2222-2222-222222222222",
        "document_title": "에너지법",
        "source_kind": "statute",
        "law_type_code": "01",
        "version_label": "MST 123456",
        "effective_from": "2024-01-01",
        "effective_to": None,
        "path": "제3조제1항",
        "heading": "정의",
        "content": "이 법에서 사용하는 용어의 뜻은 다음과 같다.",
        "source_url": "https://example.test/law/1",
    }
    base.update(overrides)  # type: ignore[typeddict-item]
    return base


def test_build_passage_text_joins_non_empty_fields_in_order():
    text = build_passage_text(_record())
    assert text == (
        "에너지법\n제3조제1항\n정의\n이 법에서 사용하는 용어의 뜻은 다음과 같다."
    )


def test_build_passage_text_skips_empty_heading():
    text = build_passage_text(_record(heading=None))
    assert text == (
        "에너지법\n제3조제1항\n이 법에서 사용하는 용어의 뜻은 다음과 같다."
    )


def test_compute_source_text_sha256_is_deterministic():
    text = build_passage_text(_record())
    assert compute_source_text_sha256(text) == compute_source_text_sha256(text)


def test_compute_source_text_sha256_changes_with_content():
    record_a = _record()
    record_b = _record(content="다른 본문")
    sha_a = compute_source_text_sha256(build_passage_text(record_a))
    sha_b = compute_source_text_sha256(build_passage_text(record_b))
    assert sha_a != sha_b


def test_build_node_metadata_preserves_raw_fields_separately_from_passage_text():
    record = _record()
    metadata = build_node_metadata(record, "deadbeef")
    assert metadata["content"] == record["content"]
    assert metadata["document_title"] == record["document_title"]
    assert metadata["path"] == record["path"]
    assert metadata["effective_from"] == "2024-01-01"
    assert metadata["effective_to"] is None
    assert metadata["source_text_sha256"] == "deadbeef"
