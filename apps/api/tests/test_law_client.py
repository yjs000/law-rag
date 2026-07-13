from pathlib import Path

import httpx
import pytest

from app.clients.law_open_api import LawOpenApiClient, LawOpenApiError
from app.domain.catalog import SourceKind

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.mark.asyncio
async def test_document_falls_back_to_xml_when_json_schema_is_invalid() -> None:
    calls: list[str] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        wire_format = request.url.params["type"]
        calls.append(wire_format)
        if wire_format == "JSON":
            return httpx.Response(200, json={"unexpected": True})
        return httpx.Response(200, text=(FIXTURES / "law.xml").read_text(encoding="utf-8"))

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as http_client:
        client = LawOpenApiClient(oc="test", base_url="https://example.test", client=http_client)
        result = await client.get_document(
            expected_title="전기사업법",
            source_kind=SourceKind.LAW,
            source_id="001",
            mst="1001",
        )

    assert calls == ["JSON", "XML"]
    assert result.raw.wire_format == "XML"
    assert result.raw.fallback_reason == "JSON schema validation failed: LawJsonParseError"
    assert result.value.fallback_reason == result.raw.fallback_reason


@pytest.mark.asyncio
async def test_secret_is_redacted_from_observable_url() -> None:
    client = LawOpenApiClient(oc="super-secret", base_url="https://example.test")
    url = client.url("lawSearch.do", {"target": "eflaw", "query": "전기사업법"})
    await client.__aexit__()
    assert "super-secret" not in url
    assert "%5Bredacted%5D" in url


@pytest.mark.asyncio
async def test_api_auth_error_does_not_trigger_format_fallback() -> None:
    calls = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(
            200, json={"result": "사용자 정보 검증에 실패하였습니다.", "msg": "IP 등록 필요"}
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http_client:
        client = LawOpenApiClient(oc="test", base_url="https://example.test", client=http_client)
        with pytest.raises(LawOpenApiError, match="Open API 오류 응답"):
            await client.search_current_law("전기사업법")
    assert calls == 1
