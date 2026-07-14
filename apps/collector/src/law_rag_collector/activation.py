import json
import re
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import date
from typing import Any, Literal

from defusedxml import ElementTree as ET
from law_rag_core.domain.entities import LegalDocumentRecord

from law_rag_collector.client import RawResponse

LifecycleState = Literal["active", "scheduled", "abolished"]
SourceRecordState = Literal["available", "deleted"]


@dataclass(frozen=True, slots=True)
class ActivationMetadata:
    lifecycle_state: LifecycleState
    source_record_state: SourceRecordState
    has_supplementary_provisions: bool


def validate_for_activation(
    document: LegalDocumentRecord,
    raw: RawResponse,
    *,
    today: date,
) -> ActivationMetadata:
    """활성 manifest에 들어가기 전에 문서 단위 불변조건을 모두 확인한다."""
    if not document.title.strip():
        raise ValueError("법령명이 없습니다")
    if not document.source_id.strip():
        raise ValueError("출처 ID가 없습니다")
    if not document.mst.strip():
        raise ValueError("MST가 없습니다")
    if document.effective_from is None:
        raise ValueError("시행일이 없습니다")
    if not document.provisions:
        raise ValueError("검색 가능한 조문이 없습니다")
    paths = [provision.path for provision in document.provisions]
    if len(paths) != len(set(paths)):
        raise ValueError("조문 경로가 중복되었습니다")
    if any(not provision.content.strip() for provision in document.provisions):
        raise ValueError("내용이 없는 조문이 있습니다")
    if document.raw_format.upper() != raw.wire_format:
        raise ValueError("파서 포맷과 원문 포맷이 다릅니다")
    import hashlib

    actual_sha256 = hashlib.sha256(raw.body.encode("utf-8")).hexdigest()
    if document.raw_sha256 != actual_sha256:
        raise ValueError("원문 SHA-256이 일치하지 않습니다")

    markers = _markers(raw)
    if markers["abolished"]:
        lifecycle = "abolished"
    elif document.effective_from > today:
        lifecycle = "scheduled"
    else:
        lifecycle = "active"
    return ActivationMetadata(
        lifecycle_state=lifecycle,
        source_record_state="deleted" if markers["deleted"] else "available",
        has_supplementary_provisions=markers["supplementary"],
    )


def _markers(raw: RawResponse) -> dict[str, bool]:
    if raw.wire_format == "JSON":
        try:
            payload = json.loads(raw.body.lstrip("\ufeff\r\n\t "))
        except json.JSONDecodeError as exc:
            raise ValueError("활성화 검사에서 JSON을 파싱할 수 없습니다") from exc
        values = list(_json_values(payload))
    else:
        try:
            root = ET.fromstring(raw.body)
        except ET.ParseError as exc:
            raise ValueError("활성화 검사에서 XML을 파싱할 수 없습니다") from exc
        values = [
            (node.tag.rsplit("}", 1)[-1], _clean(" ".join(node.itertext())))
            for node in root.iter()
        ]
    return {
        "deleted": any(_truthy(value) for key, value in values if "삭제여부" in key),
        "abolished": any(
            _truthy(value) if "여부" in key else bool(value)
            for key, value in values
            if key in {"폐지여부", "폐지일자", "폐지일"}
        ),
        "supplementary": any(key in {"부칙", "부칙단위", "부칙내용"} for key, _ in values),
    }


def _json_values(value: Any) -> Iterator[tuple[str, str]]:
    if isinstance(value, dict):
        for key, child in value.items():
            yield str(key), _clean(child) if not isinstance(child, (dict, list)) else ""
            yield from _json_values(child)
    elif isinstance(value, list):
        for child in value:
            yield from _json_values(child)


def _clean(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _truthy(value: str) -> bool:
    return value.casefold() in {"1", "true", "y", "yes", "예", "폐지", "삭제"}
