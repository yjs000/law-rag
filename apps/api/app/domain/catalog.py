from dataclasses import dataclass
from enum import StrEnum


class SourceKind(StrEnum):
    LAW = "law"
    ADMIN_RULE = "administrative_rule"


@dataclass(frozen=True, slots=True)
class CatalogEntry:
    title: str
    source_kind: SourceKind
    priority: int


MVP_CATALOG: tuple[CatalogEntry, ...] = (
    CatalogEntry("전기사업법", SourceKind.LAW, 1),
    CatalogEntry("전기사업법 시행령", SourceKind.LAW, 2),
    CatalogEntry("전기사업법 시행규칙", SourceKind.LAW, 3),
    CatalogEntry("분산에너지 활성화 특별법", SourceKind.LAW, 4),
    CatalogEntry("분산에너지 활성화 특별법 시행령", SourceKind.LAW, 5),
    CatalogEntry("신에너지 및 재생에너지 개발ㆍ이용ㆍ보급 촉진법", SourceKind.LAW, 6),
    CatalogEntry("전기안전관리법", SourceKind.LAW, 7),
    CatalogEntry(
        "전기저장시설의 화재안전성능기준(NFPC 607)",
        SourceKind.ADMIN_RULE,
        8,
    ),
    CatalogEntry(
        "전기저장시설의 화재안전기술기준(NFTC 607)",
        SourceKind.ADMIN_RULE,
        9,
    ),
)

CATALOG_BY_TITLE = {entry.title: entry for entry in MVP_CATALOG}
