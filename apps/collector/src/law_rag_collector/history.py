import json
import re
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

from defusedxml import ElementTree as ET


@dataclass(frozen=True, slots=True)
class HistoryVersion:
    source_id: str
    mst: str
    effective_from: date | None
    promulgated_on: date | None = None


@dataclass(frozen=True, slots=True)
class EffectiveVersion:
    source_id: str
    mst: str
    effective_from: date | None
    effective_to: date | None


def _date(value: Any) -> date | None:
    digits = re.sub(r"\D", "", str(value or ""))
    if len(digits) != 8:
        return None
    try:
        return date(int(digits[:4]), int(digits[4:6]), int(digits[6:]))
    except ValueError:
        return None


def _walk(value: Any) -> Iterator[dict[str, Any]]:
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from _walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk(child)


def _text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def parse_history_json(body: str) -> list[HistoryVersion]:
    try:
        payload = json.loads(body.lstrip("\ufeff\r\n\t "))
    except json.JSONDecodeError as exc:
        raise ValueError("연혁 JSON을 파싱할 수 없습니다") from exc
    versions: dict[str, HistoryVersion] = {}
    for node in _walk(payload):
        mst = _text(node.get("법령일련번호") or node.get("행정규칙일련번호"))
        if not mst:
            continue
        source_id = _text(node.get("법령ID") or node.get("행정규칙ID"))
        versions[mst] = HistoryVersion(
            source_id=source_id,
            mst=mst,
            effective_from=_date(node.get("시행일자")),
            promulgated_on=_date(node.get("공포일자") or node.get("발령일자")),
        )
    if not versions:
        raise ValueError("연혁 JSON 스키마를 인식할 수 없습니다")
    return list(versions.values())


def parse_history_xml(body: str) -> list[HistoryVersion]:
    try:
        root = ET.fromstring(body)
    except ET.ParseError as exc:
        raise ValueError("연혁 XML을 파싱할 수 없습니다") from exc
    versions: dict[str, HistoryVersion] = {}
    for node in root.iter():
        values = {
            child.tag.rsplit("}", 1)[-1]: _text(" ".join(child.itertext()))
            for child in node.iter()
        }
        mst = values.get("법령일련번호") or values.get("행정규칙일련번호") or ""
        if not mst:
            continue
        versions[mst] = HistoryVersion(
            source_id=values.get("법령ID") or values.get("행정규칙ID") or "",
            mst=mst,
            effective_from=_date(values.get("시행일자")),
            promulgated_on=_date(values.get("공포일자") or values.get("발령일자")),
        )
    if not versions:
        raise ValueError("연혁 XML 스키마를 인식할 수 없습니다")
    return list(versions.values())


def effective_periods(versions: list[HistoryVersion]) -> list[EffectiveVersion]:
    """시행일 오름차순으로 다음 버전 전날까지 효력 기간을 계산한다."""
    if any(item.effective_from is None for item in versions):
        raise ValueError("효력 기간 계산에는 모든 버전의 시행일이 필요합니다")
    ordered = sorted(
        versions,
        key=lambda item: (item.effective_from, item.promulgated_on or date.min, item.mst),
    )
    version_keys = {(item.mst, item.effective_from) for item in ordered}
    if len(version_keys) != len(ordered):
        raise ValueError("동일 MST와 시행일이 중복되었습니다")
    distinct_dates = sorted({item.effective_from for item in ordered})
    next_date = {
        effective_from: distinct_dates[index + 1]
        if index + 1 < len(distinct_dates)
        else None
        for index, effective_from in enumerate(distinct_dates)
    }
    return [
        EffectiveVersion(
            source_id=item.source_id,
            mst=item.mst,
            effective_from=item.effective_from,
            effective_to=(next_date[item.effective_from] - timedelta(days=1))
            if next_date[item.effective_from]
            else None,
        )
        for item in ordered
    ]
