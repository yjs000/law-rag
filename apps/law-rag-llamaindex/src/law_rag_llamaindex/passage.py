import hashlib
from typing import TypedDict


class ProvisionRecord(TypedDict):
    provision_id: str
    document_id: str
    document_title: str
    source_kind: str
    law_type_code: str | None
    version_label: str
    effective_from: str | None
    effective_to: str | None
    path: str
    heading: str | None
    content: str
    source_url: str


def build_passage_text(record: ProvisionRecord) -> str:
    parts = [
        record["document_title"],
        record["path"],
        record.get("heading"),
        record["content"],
    ]
    return "\n".join(part for part in parts if part)


def compute_source_text_sha256(passage_text: str) -> str:
    return hashlib.sha256(passage_text.encode("utf-8")).hexdigest()


def build_node_metadata(record: ProvisionRecord, source_text_sha256: str) -> dict[str, object]:
    return {
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
        "source_text_sha256": source_text_sha256,
    }
