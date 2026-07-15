import re
import unicodedata
from dataclasses import dataclass

from app.domain.catalog import MVP_CATALOG

_PROVISION_REFERENCE = re.compile(
    r"(?:제\s*)?(?P<article>\d+)\s*조"
    r"(?:\s*의\s*(?P<branch>\d+))?"
    r"(?:\s*(?:제\s*)?(?P<paragraph>\d+)\s*항)?"
    r"(?:\s*(?:제\s*)?(?P<item>\d+)\s*호)?"
    r"(?:\s*(?P<subitem>[가-힣])\s*목)?"
)

_DOCUMENT_TITLE_ALIASES = {
    "분산에너지법": "분산에너지 활성화 특별법",
    "신재생에너지법": "신에너지 및 재생에너지 개발ㆍ이용ㆍ보급 촉진법",
    "nfpc607": "전기저장시설의 화재안전성능기준(NFPC 607)",
    "nftc607": "전기저장시설의 화재안전기술기준(NFTC 607)",
}


@dataclass(frozen=True)
class ProvisionReference:
    path: str
    document_title: str | None

    @property
    def storage_paths(self) -> tuple[str, ...]:
        """현재 숫자 경로와 기존 Open API 기호 경로를 모두 조회한다."""
        variants = {self.path}
        match = re.fullmatch(
            r"(?P<article>제\d+조(?:의\d+)?)"
            r"(?:/항(?P<paragraph>\d+))?"
            r"(?:/호(?P<item>\d+))?"
            r"(?:/목(?P<subitem>[가-힣]))?",
            self.path,
        )
        if match is None:
            return tuple(variants)
        path = match.group("article")
        if paragraph := match.group("paragraph"):
            number = int(paragraph)
            path += f"/항{_CIRCLED_NUMBERS.get(number, paragraph)}"
        if item := match.group("item"):
            path += f"/호{item}."
        if subitem := match.group("subitem"):
            path += f"/목{subitem}."
        variants.add(path)
        return tuple(sorted(variants))


_CIRCLED_NUMBERS = dict(enumerate("①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮⑯⑰⑱⑲⑳", 1))


def parse_provision_reference(query: str) -> ProvisionReference | None:
    """사용자 표기(예: 1조2항)를 저장 경로(제1조/항2)로 정규화한다."""
    match = _PROVISION_REFERENCE.search(query)
    if match is None:
        return None
    path = f"제{int(match.group('article'))}조"
    if branch := match.group("branch"):
        path += f"의{int(branch)}"
    if paragraph := match.group("paragraph"):
        path += f"/항{int(paragraph)}"
    if item := match.group("item"):
        path += f"/호{int(item)}"
    if subitem := match.group("subitem"):
        path += f"/목{subitem}"
    compact_query = _compact(query)
    title_candidates = [
        (_compact(entry.title), entry.title)
        for entry in MVP_CATALOG
        if _compact(entry.title) in compact_query
    ]
    title_candidates.extend(
        (alias, title)
        for alias, title in _DOCUMENT_TITLE_ALIASES.items()
        if alias in compact_query
    )
    return ProvisionReference(
        path=path,
        document_title=max(title_candidates, key=lambda candidate: len(candidate[0]))[1]
        if title_candidates
        else None,
    )


def _compact(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).casefold()
    return re.sub(r"[^0-9a-z가-힣]", "", normalized)
