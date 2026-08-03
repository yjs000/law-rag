import json
from datetime import date
from uuid import NAMESPACE_URL, UUID, uuid5

from law_rag_core.domain.catalog import SourceKind

PARSER_SCHEMA_VERSION = "3"

_PROVISION_UUID_NAMESPACE = uuid5(
    NAMESPACE_URL,
    f"law-rag:canonical-provision:{PARSER_SCHEMA_VERSION}",
)


def canonical_provision_id(
    *,
    source_kind: SourceKind,
    source_id: str,
    mst: str,
    effective_from: date | None,
    path: str,
) -> UUID:
    """출처·버전·시행일·원문 위치로 schema v3 조문 UUID를 결정한다.

    시행일이 없는 문서도 파서 결과와 오류 원문을 검사할 수 있도록 ``None``을
    결정적으로 직렬화한다. 그런 문서는 collector 활성화 단계에서 거부된다.
    """
    identity = json.dumps(
        {
            "effective_from": effective_from.isoformat() if effective_from else None,
            "mst": mst,
            "path": path,
            "source_id": source_id,
            "source_kind": source_kind.value,
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return uuid5(_PROVISION_UUID_NAMESPACE, identity)
