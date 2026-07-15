import re
from dataclasses import dataclass

from app.domain.catalog import MVP_CATALOG

_PROVISION_REFERENCE = re.compile(
    r"(?:제\s*)?(?P<article>\d+)\s*조"
    r"(?:\s*의\s*(?P<branch>\d+))?"
    r"(?:\s*(?:제\s*)?(?P<paragraph>\d+)\s*항)?"
    r"(?:\s*(?:제\s*)?(?P<item>\d+)\s*호)?"
    r"(?:\s*(?P<subitem>[가-힣])\s*목)?"
)


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
    titles = [entry.title for entry in MVP_CATALOG if entry.title in query]
    return ProvisionReference(
        path=path,
        document_title=max(titles, key=len) if titles else None,
    )
