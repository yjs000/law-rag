import hashlib
import json
from datetime import date
from uuid import NAMESPACE_URL, uuid5

import httpx
import pytest
import respx
from law_rag_core.domain.catalog import SourceKind
from law_rag_core.domain.entities import LegalDocumentRecord, ProvisionRecord

from law_rag_collector.client import RawResponse
from law_rag_collector.supabase_repository import SupabaseRawStorage, raw_object_path


def _document(body: str = "{}") -> LegalDocumentRecord:
    return LegalDocumentRecord(
        source_id="001",
        mst="1000",
        title="전기사업법",
        source_kind=SourceKind.LAW,
        promulgation_number="제1호",
        promulgated_on=date(2020, 1, 1),
        effective_from=date(2020, 2, 1),
        ministry="산업통상자원부",
        source_url="https://www.law.go.kr/법령/전기사업법",
        raw_format="JSON",
        raw_sha256=hashlib.sha256(body.encode()).hexdigest(),
        provisions=[
            ProvisionRecord(
                id=uuid5(NAMESPACE_URL, "test#1"),
                path="제1조",
                heading="목적",
                content="목적 조문",
            )
        ],
    )


def test_raw_object_path_is_content_addressed() -> None:
    raw = RawResponse("{}", "JSON", "https://example.test")
    document = _document()

    path = raw_object_path(document, raw)

    assert path.startswith("law/001/1000-2020-02-01-")
    assert document.raw_sha256 in path
    assert path.endswith(".json")


@pytest.mark.asyncio
@respx.mock
async def test_storage_creates_private_bucket_and_uploads_without_overwrite() -> None:
    get_bucket = respx.get("https://project.supabase.co/storage/v1/bucket/law-raw").mock(
        return_value=httpx.Response(
            400,
            json={
                "statusCode": "404",
                "error": "Bucket not found",
                "message": "Bucket not found",
            },
        )
    )
    create_bucket = respx.post("https://project.supabase.co/storage/v1/bucket").mock(
        return_value=httpx.Response(200, json={"name": "law-raw"})
    )
    upload = respx.post(
        "https://project.supabase.co/storage/v1/object/law-raw/law/001/raw.json"
    ).mock(return_value=httpx.Response(200, json={"Key": "law/001/raw.json"}))
    storage = SupabaseRawStorage(
        url="https://project.supabase.co",
        secret_key="sb_secret_test",
        bucket="law-raw",
    )
    raw = RawResponse("{}", "JSON", "https://example.test")

    try:
        stored = await storage.put_immutable("law/001/raw.json", raw)
    finally:
        await storage.close()

    assert stored == "law-raw/law/001/raw.json"
    assert get_bucket.called
    assert json.loads(create_bucket.calls.last.request.content) == {
        "id": "law-raw",
        "name": "law-raw",
        "public": False,
    }
    assert upload.calls.last.request.headers["x-upsert"] == "false"
    assert upload.calls.last.request.headers["apikey"] == "sb_secret_test"
    assert "authorization" not in upload.calls.last.request.headers


@pytest.mark.asyncio
@respx.mock
async def test_existing_immutable_object_is_idempotent() -> None:
    respx.get("https://project.supabase.co/storage/v1/bucket/law-raw").mock(
        return_value=httpx.Response(200, json={"name": "law-raw"})
    )
    respx.post("https://project.supabase.co/storage/v1/object/law-raw/law/001/raw.json").mock(
        return_value=httpx.Response(
            400,
            json={
                "statusCode": "409",
                "error": "Duplicate",
                "message": "The resource already exists",
            },
        )
    )
    storage = SupabaseRawStorage(
        url="https://project.supabase.co",
        secret_key="sb_secret_test",
        bucket="law-raw",
    )

    try:
        stored = await storage.put_immutable(
            "law/001/raw.json", RawResponse("{}", "JSON", "https://example.test")
        )
    finally:
        await storage.close()

    assert stored == "law-raw/law/001/raw.json"
