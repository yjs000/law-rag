import json
import re
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import date
from typing import Any, Literal

from defusedxml import ElementTree as ET
from law_rag_core.domain.catalog import SourceKind

DeletionKind = Literal[1, 2]


@dataclass(frozen=True, slots=True)
class DeletionRecord:
    mst: str
    source_kind: SourceKind
    kind_name: str
    deleted_on: date


@dataclass(frozen=True, slots=True)
class DeletionPage:
    total_count: int
    page: int
    records: list[DeletionRecord]


def parse_deletions_json(
    body: str, expected_kind: DeletionKind, *, expected_page: int | None = None
) -> DeletionPage:
    try:
        payload = json.loads(body.lstrip("\ufeff\r\n\t "))
    except json.JSONDecodeError as exc:
        raise ValueError("삭제 목록 JSON을 파싱할 수 없습니다") from exc
    total = _first(payload, "totalCnt")
    page = _first(payload, "page")
    target = _first(payload, "target")
    if target not in {"delHst", "datDel"}:
        raise ValueError("삭제 목록 JSON의 target이 올바르지 않습니다")
    if total is None or page is None:
        raise ValueError("삭제 목록 JSON의 페이지 필드가 없습니다")
    if expected_page is not None and int(page) != expected_page:
        raise ValueError("삭제 목록 JSON의 페이지 번호가 요청과 다릅니다")
    records = _json_records(payload, expected_kind)
    if int(total) > 0 and not records:
        raise ValueError("삭제 목록 JSON의 결과 스키마를 인식할 수 없습니다")
    return DeletionPage(int(total), int(page), records)


def parse_deletions_xml(
    body: str, expected_kind: DeletionKind, *, expected_page: int | None = None
) -> DeletionPage:
    try:
        root = ET.fromstring(body)
    except ET.ParseError as exc:
        raise ValueError("삭제 목록 XML을 파싱할 수 없습니다") from exc
    total = _xml_first(root, "totalCnt")
    page = _xml_first(root, "page")
    target = _xml_first(root, "target")
    if target not in {"delHst", "datDel"}:
        raise ValueError("삭제 목록 XML의 target이 올바르지 않습니다")
    if total is None or page is None:
        raise ValueError("삭제 목록 XML의 페이지 필드가 없습니다")
    if expected_page is not None and int(page) != expected_page:
        raise ValueError("삭제 목록 XML의 페이지 번호가 요청과 다릅니다")
    records: list[DeletionRecord] = []
    for node in root.iter():
        values = {
            child.tag.rsplit("}", 1)[-1]: _clean(" ".join(child.itertext()))
            for child in node.iter()
        }
        if values.get("일련번호") and values.get("삭제일자"):
            records.append(_record(values, expected_kind))
    records = sorted(
        {(item.mst, item.deleted_on): item for item in records}.values(),
        key=lambda item: (item.deleted_on, item.mst),
    )
    if int(total) > 0 and not records:
        raise ValueError("삭제 목록 XML의 결과 스키마를 인식할 수 없습니다")
    return DeletionPage(int(total), int(page), records)


def _json_records(payload: Any, expected_kind: DeletionKind) -> list[DeletionRecord]:
    records: dict[tuple[str, date], DeletionRecord] = {}
    for node in _walk(payload):
        if node.get("일련번호") is None or node.get("삭제일자") is None:
            continue
        record = _record(node, expected_kind)
        records[(record.mst, record.deleted_on)] = record
    return sorted(records.values(), key=lambda item: (item.deleted_on, item.mst))


def _record(values: dict[str, Any], expected_kind: DeletionKind) -> DeletionRecord:
    mst = _clean(values.get("일련번호"))
    kind_name = _clean(values.get("구분명"))
    deleted_on = _date(values.get("삭제일자"))
    expected_name = "법령" if expected_kind == 1 else "행정규칙"
    if not mst or deleted_on is None:
        raise ValueError("삭제 목록에 일련번호 또는 삭제일자가 없습니다")
    if kind_name != expected_name:
        raise ValueError(f"삭제 목록 구분명이 다릅니다: expected={expected_name}")
    return DeletionRecord(
        mst=mst,
        source_kind=SourceKind.LAW if expected_kind == 1 else SourceKind.ADMIN_RULE,
        kind_name=kind_name,
        deleted_on=deleted_on,
    )


def _walk(value: Any) -> Iterator[dict[str, Any]]:
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from _walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk(child)


def _first(payload: Any, name: str) -> Any | None:
    return next((node[name] for node in _walk(payload) if name in node), None)


def _xml_first(root: ET.Element, name: str) -> str | None:
    return next(
        (
            _clean(" ".join(node.itertext()))
            for node in root.iter()
            if node.tag.rsplit("}", 1)[-1] == name
        ),
        None,
    )


def _date(value: Any) -> date | None:
    digits = re.sub(r"\D", "", str(value or ""))
    if len(digits) != 8:
        return None
    try:
        return date(int(digits[:4]), int(digits[4:6]), int(digits[6:]))
    except ValueError:
        return None


def _clean(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()
