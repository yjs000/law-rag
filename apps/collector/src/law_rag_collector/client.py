import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from typing import Literal
from urllib.parse import urlencode

import httpx
from law_rag_core.domain.catalog import SourceKind
from law_rag_core.domain.entities import LegalDocumentRecord
from law_rag_core.parsers import law_json, law_xml

from law_rag_collector.history import HistoryVersion

WireFormat = Literal["JSON", "XML"]


class LawOpenApiError(RuntimeError):
    pass


class RetryableLawOpenApiError(LawOpenApiError):
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
    """JSON 도메인 검증 실패 때만 XML로 폴백하는 Open API 클라이언트."""

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

    def safe_url(self, operation: str, params: dict[str, str | int]) -> str:
        return f"{self._base_url}/{operation}?{urlencode({**params, 'OC': '[redacted]'})}"

    async def _request_format(
        self, operation: str, wire_format: WireFormat, params: dict[str, str | int]
    ) -> RawResponse:
        request_params = {"OC": self._oc, "type": wire_format, **params}
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
                    raise RetryableLawOpenApiError(
                        f"Open API HTTP {response.status_code}: {operation}"
                    )
                if response.status_code != 200:
                    raise LawOpenApiError(f"Open API HTTP {response.status_code}: {operation}")
                body = response.text.lstrip("\ufeff\r\n\t ")
                if wire_format == "JSON" and not body.startswith(("{", "[")):
                    raise ValueError("JSON이 아닌 응답")
                if wire_format == "XML" and not body.startswith("<"):
                    raise ValueError("XML이 아닌 응답")
                return RawResponse(body, wire_format, self.safe_url(operation, params))
            except (
                httpx.TimeoutException,
                httpx.TransportError,
                RetryableLawOpenApiError,
            ) as exc:
                if attempt + 1 < self._retry_attempts:
                    await asyncio.sleep(0.2 * (2**attempt))
                    continue
                raise LawOpenApiError(f"Open API 요청 실패: {operation}") from exc
        raise AssertionError("retry loop exhausted")

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

    async def search(
        self, exact_title: str, source_kind: SourceKind, *, historical: bool = False
    ) -> ParsedResponse[list[SearchRecord]]:
        def records(items: list[dict[str, str]]) -> list[SearchRecord]:
            return [
                SearchRecord(
                    title=item["title"],
                    source_id=item["id"],
                    mst=item["mst"],
                    effective_date=item["effective_date"],
                    detail_link=item["detail_link"],
                )
                for item in items
            ]

        target = "eflaw" if source_kind is SourceKind.LAW else "admrul"
        params: dict[str, str | int] = {
            "target": target,
            "search": 1,
            "query": exact_title,
            "display": 100,
            "nw": (
                1
                if source_kind is SourceKind.LAW and historical
                else 3
                if source_kind is SourceKind.LAW
                else 2
                if historical
                else 1
            ),
        }
        return await self._parsed(
            "lawSearch.do",
            params,
            lambda body: records(law_json.parse_search_results(body, source_kind)),
            lambda body: records(law_xml.parse_search_results(body, source_kind)),
        )

    async def history(
        self, *, exact_title: str, source_kind: SourceKind, source_id: str
    ) -> ParsedResponse[list[HistoryVersion]]:
        search = await self.search(exact_title, source_kind, historical=True)
        versions = [
            HistoryVersion(item.source_id, item.mst, _compact_date(item.effective_date))
            for item in search.value
            if item.title == exact_title
        ]
        if not versions:
            raise LawOpenApiError("법령 연혁을 찾을 수 없습니다")
        return ParsedResponse(versions, search.raw)

    async def document(
        self,
        *,
        expected_title: str,
        source_kind: SourceKind,
        source_id: str,
        mst: str,
        historical: bool,
        effective_date: date | None = None,
    ) -> ParsedResponse[LegalDocumentRecord]:
        if source_kind is SourceKind.LAW:
            if historical:
                if effective_date is None:
                    raise ValueError("과거 시행법령 본문 조회에는 시행일이 필요합니다")
                params: dict[str, str | int] = {
                    "target": "eflaw",
                    "MST": mst,
                    "efYd": effective_date.strftime("%Y%m%d"),
                }
            else:
                params = {"target": "eflaw", "ID": source_id}
        else:
            params = {"target": "admrul", "ID": mst}

        def parse_json(body: str) -> LegalDocumentRecord:
            return law_json.parse_legal_document(
                body,
                expected_title=expected_title,
                source_kind=source_kind,
                source_url=self.safe_url("lawService.do", params),
                mst_override=mst,
            )

        def parse_xml(body: str) -> LegalDocumentRecord:
            return law_xml.parse_legal_document(
                body,
                expected_title=expected_title,
                source_kind=source_kind,
                source_url=self.safe_url("lawService.do", params),
                mst_override=mst,
            )

        parsed = await self._parsed("lawService.do", params, parse_json, parse_xml)
        parsed.value.fallback_reason = parsed.raw.fallback_reason
        return parsed

    async def article_history_msts(
        self, *, source_id: str, article_code: str
    ) -> ParsedResponse[set[str]]:
        return await self._parsed(
            "lawService.do",
            {"target": "lsJoHstInf", "ID": source_id, "JO": article_code, "display": 100},
            law_json.parse_history_msts,
            law_xml.parse_history_msts,
        )

    async def changed_law_msts(self, *, changed_on: date) -> ParsedResponse[set[str]]:
        return await self._parsed(
            "lawSearch.do",
            {"target": "lsHstInf", "regDt": changed_on.strftime("%Y%m%d"), "display": 100},
            law_json.parse_history_msts,
            law_xml.parse_history_msts,
        )


def _compact_date(value: str):
    from datetime import date

    digits = "".join(character for character in value if character.isdigit())
    if len(digits) != 8:
        return None
    return date(int(digits[:4]), int(digits[4:6]), int(digits[6:]))
