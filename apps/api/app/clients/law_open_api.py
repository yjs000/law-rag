import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from typing import Literal
from urllib.parse import urlencode

import httpx

from app.domain.catalog import SourceKind
from app.domain.entities import LegalDocumentRecord
from app.parsers import law_json, law_xml

WireFormat = Literal["JSON", "XML"]


class LawOpenApiError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class SearchRecord:
    title: str
    source_id: str
    mst: str
    effective_date: str
    detail_link: str


@dataclass(frozen=True, slots=True)
class RawResponse:
    body: str
    wire_format: WireFormat
    source_url: str
    fallback_reason: str | None = None


@dataclass(frozen=True, slots=True)
class ParsedResponse[T]:
    value: T
    raw: RawResponse


class LawOpenApiClient:
    """JSON을 우선 사용하고 검증 실패 시에만 XML로 폴백한다."""

    def __init__(
        self,
        *,
        oc: str,
        base_url: str = "https://www.law.go.kr/DRF",
        timeout: float = 30,
        client: httpx.AsyncClient | None = None,
        retry_attempts: int = 3,
    ) -> None:
        if not oc:
            raise ValueError("LAW_OPEN_API_OC가 필요합니다")
        self._oc = oc
        self._base_url = base_url.rstrip("/")
        self._owned_client = client is None
        self._client = client or httpx.AsyncClient(timeout=timeout, follow_redirects=False)
        self._retry_attempts = retry_attempts

    async def __aenter__(self) -> LawOpenApiClient:
        return self

    async def __aexit__(self, *_: object) -> None:
        if self._owned_client:
            await self._client.aclose()

    def url(self, operation: str, params: dict[str, str | int]) -> str:
        safe = {**params, "OC": "[redacted]"}
        return f"{self._base_url}/{operation}?{urlencode(safe)}"

    async def _request_format(
        self, operation: str, wire_format: WireFormat, params: dict[str, str | int]
    ) -> RawResponse:
        request_params = {"OC": self._oc, "type": wire_format, **params}
        last_error: Exception | None = None
        for attempt in range(self._retry_attempts):
            try:
                response = await self._client.get(
                    f"{self._base_url}/{operation}",
                    params=request_params,
                    headers={
                        "Accept": "application/json"
                        if wire_format == "JSON"
                        else "application/xml,text/xml"
                    },
                )
                if response.status_code >= 500:
                    raise LawOpenApiError(f"Open API HTTP {response.status_code}: {operation}")
                if response.status_code != 200:
                    raise LawOpenApiError(f"Open API HTTP {response.status_code}: {operation}")
                body = response.text.lstrip("\ufeff\r\n\t ")
                if wire_format == "JSON" and not body.startswith(("{", "[")):
                    raise ValueError("JSON이 아닌 응답")
                if wire_format == "XML" and not body.startswith("<"):
                    raise ValueError("XML이 아닌 응답")
                return RawResponse(body, wire_format, self.url(operation, params))
            except (httpx.TimeoutException, httpx.TransportError, LawOpenApiError) as exc:
                last_error = exc
                if attempt + 1 < self._retry_attempts:
                    await asyncio.sleep(0.2 * (2**attempt))
                    continue
                raise LawOpenApiError(f"Open API 요청 실패: {operation}") from exc
        raise LawOpenApiError(f"Open API 요청 실패: {operation}") from last_error

    async def _parsed[T](
        self,
        operation: str,
        params: dict[str, str | int],
        json_parser: Callable[[str], T],
        xml_parser: Callable[[str], T],
    ) -> ParsedResponse[T]:
        try:
            raw = await self._request_format(operation, "JSON", params)
            return ParsedResponse(json_parser(raw.body), raw)
        except (ValueError, TypeError, KeyError) as exc:
            if str(exc).startswith("Open API 오류 응답"):
                raise LawOpenApiError(str(exc)) from exc
            reason = f"JSON schema validation failed: {type(exc).__name__}"
        raw = await self._request_format(operation, "XML", params)
        raw = RawResponse(raw.body, raw.wire_format, raw.source_url, reason)
        try:
            return ParsedResponse(xml_parser(raw.body), raw)
        except (ValueError, TypeError, KeyError) as exc:
            raise LawOpenApiError("JSON과 XML 응답을 모두 정규화할 수 없습니다") from exc

    async def _search(
        self, exact_title: str, source_kind: SourceKind, **params: str | int
    ) -> ParsedResponse[list[SearchRecord]]:
        def records(items: list[dict[str, str]]) -> list[SearchRecord]:
            return [
                SearchRecord(
                    item["title"],
                    item["id"],
                    item["mst"],
                    item["effective_date"],
                    item["detail_link"],
                )
                for item in items
            ]

        parsed = await self._parsed(
            "lawSearch.do",
            {"search": 1, "query": exact_title, "display": 100, **params},
            lambda body: records(law_json.parse_search_results(body, source_kind)),
            lambda body: records(law_xml.parse_search_results(body, source_kind)),
        )
        return parsed

    async def search_current_law(self, exact_title: str) -> ParsedResponse[list[SearchRecord]]:
        return await self._search(exact_title, SourceKind.LAW, target="eflaw", nw=3)

    async def search_admin_rule(
        self, exact_title: str, *, historical: bool = False
    ) -> ParsedResponse[list[SearchRecord]]:
        return await self._search(
            exact_title, SourceKind.ADMIN_RULE, target="admrul", nw=2 if historical else 1
        )

    async def get_law_body(
        self, *, source_id: str | None = None, mst: str | None = None, historical: bool = False
    ) -> RawResponse:
        if not source_id and not mst:
            raise ValueError("source_id 또는 mst가 필요합니다")
        params: dict[str, str | int] = {"target": "law" if historical else "eflaw"}
        if source_id:
            params["ID"] = source_id
        elif mst:
            params["MST"] = mst
            if not historical:
                params["efYd"] = date.today().strftime("%Y%m%d")
        parsed = await self._parsed(
            "lawService.do", params, law_json.load_json, lambda body: law_xml.ET.fromstring(body)
        )
        return parsed.raw

    async def get_admin_rule_body(
        self, *, serial_id: str | None = None, source_id: str | None = None
    ) -> RawResponse:
        if not serial_id and not source_id:
            raise ValueError("serial_id 또는 source_id가 필요합니다")
        params: dict[str, str | int] = {"target": "admrul"}
        if serial_id:
            params["ID"] = serial_id
        if source_id:
            params["LID"] = source_id
        parsed = await self._parsed(
            "lawService.do", params, law_json.load_json, lambda body: law_xml.ET.fromstring(body)
        )
        return parsed.raw

    async def get_document(
        self,
        *,
        expected_title: str,
        source_kind: SourceKind,
        source_id: str,
        mst: str | None = None,
    ) -> ParsedResponse[LegalDocumentRecord]:
        if source_kind is SourceKind.LAW:
            params: dict[str, str | int] = {"target": "eflaw", "ID": source_id}
        else:
            params = {"target": "admrul"}
            if mst:
                params["ID"] = mst
            else:
                params["LID"] = source_id

        def parse_json(body: str) -> LegalDocumentRecord:
            return law_json.parse_legal_document(
                body,
                expected_title=expected_title,
                source_kind=source_kind,
                source_url=self.url("lawService.do", params),
                mst_override=mst,
            )

        def parse_xml(body: str) -> LegalDocumentRecord:
            return law_xml.parse_legal_document(
                body,
                expected_title=expected_title,
                source_kind=source_kind,
                source_url=self.url("lawService.do", params),
                mst_override=mst,
            )

        parsed = await self._parsed("lawService.do", params, parse_json, parse_xml)
        if parsed.raw.fallback_reason:
            parsed.value.fallback_reason = parsed.raw.fallback_reason
        return parsed

    async def article_history_msts(
        self, source_id: str, article_code: str
    ) -> ParsedResponse[set[str]]:
        return await self._parsed(
            "lawService.do",
            {"target": "lsJoHstInf", "ID": source_id, "JO": article_code, "display": 100},
            law_json.parse_history_msts,
            law_xml.parse_history_msts,
        )

    async def changed_laws(self, changed_on: date) -> ParsedResponse[set[str]]:
        return await self._parsed(
            "lawSearch.do",
            {"target": "lsHstInf", "regDt": changed_on.strftime("%Y%m%d"), "display": 100},
            law_json.parse_history_msts,
            law_xml.parse_history_msts,
        )
