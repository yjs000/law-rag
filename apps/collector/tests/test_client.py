from datetime import date
from pathlib import Path

import httpx
import pytest
import respx
from law_rag_core.domain.catalog import SourceKind

from law_rag_collector.client import LawOpenApiClient, LawOpenApiError, SearchRecord

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.mark.asyncio
@respx.mock
async def test_history_prefers_json_and_redacts_oc() -> None:
    route = respx.get("https://example.test/DRF/lawSearch.do").mock(
        return_value=httpx.Response(
            200, text=(FIXTURES / "search-history.json").read_text(encoding="utf-8")
        )
    )
    async with LawOpenApiClient(oc="secret", base_url="https://example.test/DRF") as client:
        response = await client.history(
            exact_title="전기사업법", source_kind=SourceKind.LAW, source_id="001"
        )

    assert [item.mst for item in response.value] == ["1000", "1001"]
    assert response.raw.wire_format == "JSON"
    assert "secret" not in response.raw.source_url
    assert route.calls[0].request.url.params["type"] == "JSON"


@pytest.mark.asyncio
@respx.mock
async def test_search_maps_open_api_id_to_source_id() -> None:
    respx.get("https://example.test/DRF/lawSearch.do").mock(
        return_value=httpx.Response(
            200, text=(FIXTURES / "search.json").read_text(encoding="utf-8")
        )
    )
    async with LawOpenApiClient(oc="secret", base_url="https://example.test/DRF") as client:
        response = await client.search("전기사업법", SourceKind.LAW)

    assert response.value == [
        SearchRecord(
            title="전기사업법",
            source_id="001854",
            mst="283981",
            effective_date="20260310",
            detail_link="/DRF/lawService.do",
        )
    ]


@pytest.mark.asyncio
@respx.mock
async def test_schema_failure_falls_back_to_xml() -> None:
    route = respx.get("https://example.test/DRF/lawSearch.do").mock(
        side_effect=[
            httpx.Response(200, json={"unexpected": []}),
            httpx.Response(
                200, text=(FIXTURES / "search-history.xml").read_text(encoding="utf-8")
            ),
        ]
    )
    async with LawOpenApiClient(oc="secret", base_url="https://example.test/DRF") as client:
        response = await client.history(
            exact_title="전기사업법", source_kind=SourceKind.LAW, source_id="001"
        )

    assert response.raw.wire_format == "XML"
    assert response.raw.fallback_reason == "JSON schema validation failed: LawJsonParseError"
    assert [call.request.url.params["type"] for call in route.calls] == ["JSON", "XML"]


@pytest.mark.asyncio
@respx.mock
async def test_transport_failure_does_not_fall_back() -> None:
    route = respx.get("https://example.test/DRF/lawSearch.do").mock(
        return_value=httpx.Response(503, text="unavailable")
    )
    async with LawOpenApiClient(
        oc="secret", base_url="https://example.test/DRF", retry_attempts=2
    ) as client:
        with pytest.raises(LawOpenApiError):
            await client.history(
                exact_title="전기사업법", source_kind=SourceKind.LAW, source_id="001"
            )

    assert len(route.calls) == 2
    assert {call.request.url.params["type"] for call in route.calls} == {"JSON"}


@pytest.mark.asyncio
@respx.mock
async def test_client_error_is_not_retried_or_changed_to_xml() -> None:
    route = respx.get("https://example.test/DRF/lawSearch.do").mock(
        return_value=httpx.Response(401, text="unauthorized")
    )
    async with LawOpenApiClient(
        oc="secret", base_url="https://example.test/DRF", retry_attempts=3
    ) as client:
        with pytest.raises(LawOpenApiError):
            await client.history(
                exact_title="전기사업법", source_kind=SourceKind.LAW, source_id="001"
            )

    assert len(route.calls) == 1
    assert route.calls[0].request.url.params["type"] == "JSON"


@pytest.mark.asyncio
@respx.mock
async def test_historical_law_body_uses_effective_law_mst_and_date() -> None:
    route = respx.get("https://example.test/DRF/lawService.do").mock(
        return_value=httpx.Response(
            200, text=(FIXTURES / "law.json").read_text(encoding="utf-8")
        )
    )
    async with LawOpenApiClient(oc="secret", base_url="https://example.test/DRF") as client:
        response = await client.document(
            expected_title="전기사업법",
            source_kind=SourceKind.LAW,
            source_id="001",
            mst="1001",
            historical=True,
            effective_date=date(2026, 2, 1),
        )

    params = route.calls[0].request.url.params
    assert params["target"] == "eflaw"
    assert params["MST"] == "1001"
    assert params["efYd"] == "20260201"
    assert response.value.mst == "1001"


@pytest.mark.asyncio
@respx.mock
async def test_article_history_contract() -> None:
    respx.get("https://example.test/DRF/lawService.do").mock(
        return_value=httpx.Response(
            200, text=(FIXTURES / "article-history.json").read_text(encoding="utf-8")
        )
    )
    async with LawOpenApiClient(oc="secret", base_url="https://example.test/DRF") as client:
        response = await client.article_history_msts(source_id="001", article_code="000100")
    assert response.value == {"1000", "1001"}


@pytest.mark.asyncio
@respx.mock
async def test_changed_law_history_contract() -> None:
    route = respx.get("https://example.test/DRF/lawSearch.do").mock(
        return_value=httpx.Response(
            200, text=(FIXTURES / "article-history.json").read_text(encoding="utf-8")
        )
    )
    async with LawOpenApiClient(oc="secret", base_url="https://example.test/DRF") as client:
        response = await client.changed_law_msts(changed_on=date(2026, 7, 13))
    assert response.value == {"1000", "1001"}
    assert route.calls[0].request.url.params["target"] == "lsHstInf"
    assert route.calls[0].request.url.params["regDt"] == "20260713"
