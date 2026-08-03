import json
import re
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import date
from typing import Any, Literal

from defusedxml import ElementTree as ET
from law_rag_core.domain.catalog import SourceKind
from law_rag_core.domain.entities import LegalDocumentRecord
from law_rag_core.domain.identifiers import PARSER_SCHEMA_VERSION, canonical_provision_id

from law_rag_collector.client import RawResponse

LifecycleState = Literal["active", "scheduled", "abolished"]
SourceRecordState = Literal["available", "deleted"]

_ARTICLE_PATH = re.compile(r"^(제\d+조(?:의\d+)?)(?:/|$)")
_STRUCTURE_MARKER = re.compile(r"^\s*제\s*\d+\s*(?:장|절)(?:의\s*\d+)?(?:\s|$)")


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
    if document.parser_schema_version != PARSER_SCHEMA_VERSION:
        raise ValueError(
            "지원하지 않는 파서 스키마입니다: "
            f"expected={PARSER_SCHEMA_VERSION}, actual={document.parser_schema_version}"
        )
    if not document.provisions:
        raise ValueError("검색 가능한 조문이 없습니다")
    paths = [provision.path for provision in document.provisions]
    if len(paths) != len(set(paths)):
        raise ValueError("조문 경로가 중복되었습니다")
    if any(not provision.content.strip() for provision in document.provisions):
        raise ValueError("내용이 없는 조문이 있습니다")
    _validate_provision_hierarchy(document)
    for provision in document.provisions:
        expected_id = canonical_provision_id(
            source_kind=document.source_kind,
            source_id=document.source_id,
            mst=document.mst,
            effective_from=document.effective_from,
            path=provision.path,
        )
        if provision.id != expected_id:
            raise ValueError(f"조문 ID가 정규 UUID와 일치하지 않습니다: {provision.path}")
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


def _validate_provision_hierarchy(document: LegalDocumentRecord) -> None:
    """검색·임베딩 전에 원문 위치와 부모 관계를 결정적으로 검증한다."""
    by_path = {provision.path: provision for provision in document.provisions}
    for provision in document.provisions:
        if provision.parent_path is not None and provision.parent_path not in by_path:
            raise ValueError(f"상위 조문 경로가 없습니다: {provision.path}")

    if document.source_kind is not SourceKind.LAW:
        return

    roots: set[str] = set()
    expected_roots: set[str] = set()
    for provision in document.provisions:
        match = _ARTICLE_PATH.match(provision.path)
        if match is None:
            raise ValueError(f"법률 조문 경로 형식이 아닙니다: {provision.path}")
        article_path = match.group(1)
        expected_roots.add(article_path)
        if provision.parent_path is None:
            if provision.path != article_path:
                raise ValueError(f"하위 조문에 상위 경로가 없습니다: {provision.path}")
            if _STRUCTURE_MARKER.match(provision.content):
                raise ValueError(f"조문 본문이 장·절 구조 표지입니다: {provision.path}")
            roots.add(provision.path)
            continue

        parent_match = _ARTICLE_PATH.match(provision.parent_path)
        if parent_match is None or parent_match.group(1) != article_path:
            raise ValueError(f"상위 경로가 다른 조문을 가리킵니다: {provision.path}")

    missing_roots = expected_roots - roots
    if missing_roots:
        raise ValueError(f"조문 루트가 없습니다: {', '.join(sorted(missing_roots))}")


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
            (node.tag.rsplit("}", 1)[-1], _clean(" ".join(node.itertext()))) for node in root.iter()
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
