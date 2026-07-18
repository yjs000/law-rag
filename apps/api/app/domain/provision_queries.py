import re
import unicodedata
from dataclasses import dataclass

from app.domain.catalog import MVP_CATALOG

_PROVISION_REFERENCE = re.compile(
    r"(?:제\s*)?(?P<article>\d+)\s*조"
    r"(?:\s*의\s*(?P<branch>\d+))?"
    r"(?:\s*(?:제\s*)?(?P<paragraph>\d+|[①-⑳])\s*항)?"
    r"(?:\s*(?:제\s*)?(?P<item>\d+)\s*호)?"
    r"(?:\s*(?P<subitem>[가-힣])\s*목)?"
)

_DOCUMENT_TITLE_ALIASES = {
    "분산에너지법": "분산에너지 활성화 특별법",
    "신재생에너지법": "신에너지 및 재생에너지 개발ㆍ이용ㆍ보급 촉진법",
    "nfpc607": "전기저장시설의 화재안전성능기준(NFPC 607)",
    "nftc607": "전기저장시설의 화재안전기술기준(NFTC 607)",
}

_KOREAN_DIGITS = {
    "영": 0,
    "공": 0,
    "일": 1,
    "이": 2,
    "삼": 3,
    "사": 4,
    "오": 5,
    "육": 6,
    "칠": 7,
    "팔": 8,
    "구": 9,
}
_MAX_RANGE_SIZE = 20


@dataclass(frozen=True)
class ProvisionReference:
    path: str
    document_title: str | None
    unrecognized_document_title: str | None = None

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


@dataclass(frozen=True)
class ProvisionQuery:
    references: tuple[ProvisionReference, ...]
    document_title: str | None
    unrecognized_document_title: str | None = None
    invalid_reason: str | None = None

    @property
    def storage_paths(self) -> tuple[str, ...]:
        return tuple(
            dict.fromkeys(path for reference in self.references for path in reference.storage_paths)
        )


_CIRCLED_NUMBERS = dict(enumerate("①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮⑯⑰⑱⑲⑳", 1))
_CIRCLED_NUMBER_VALUES = {symbol: number for number, symbol in _CIRCLED_NUMBERS.items()}


def parse_provision_reference(query: str) -> ProvisionReference | None:
    """사용자 표기(예: 1조2항)를 저장 경로(제1조/항2)로 정규화한다."""
    parsed = parse_provision_references(query)
    return parsed.references[0] if parsed and parsed.references else None


def parse_provision_references(query: str) -> ProvisionQuery | None:
    """직접 조문 질의를 단일·복수·범위 경로 집합으로 정규화한다."""
    normalized = _normalize_korean_provision_numbers(query)
    title, unknown_title = _document_title(normalized)
    range_match = re.search(
        r"(?:제\s*)?(?P<start>\d+)\s*조\s*부터\s*(?:제\s*)?(?P<end>\d+)\s*조",
        normalized,
    )
    if range_match:
        start, end = int(range_match.group("start")), int(range_match.group("end"))
        if end < start:
            return ProvisionQuery((), title, unknown_title, "descending_range")
        if end - start + 1 > _MAX_RANGE_SIZE:
            return ProvisionQuery((), title, unknown_title, "range_too_wide")
        return ProvisionQuery(
            tuple(
                ProvisionReference(f"제{number}조", title, unknown_title)
                for number in range(start, end + 1)
            ),
            title,
            unknown_title,
        )

    matches = list(_PROVISION_REFERENCE.finditer(normalized))
    if not matches:
        return None
    references = [_reference_from_match(match, title, unknown_title) for match in matches]

    # "제1조 제2항 및 제3항"의 뒤 항은 조 번호가 생략되므로 첫 조에 결합한다.
    first_article = references[0].path.split("/", 1)[0]
    covered_spans = [match.span() for match in matches]
    for paragraph_match in re.finditer(
        r"(?:및|또는|,|ㆍ)\s*(?:제\s*)?(\d+|[①-⑳])\s*항", normalized
    ):
        if any(start <= paragraph_match.start() < end for start, end in covered_spans):
            continue
        references.append(
            ProvisionReference(
                f"{first_article}/항{_number_value(paragraph_match.group(1))}",
                title,
                unknown_title,
            )
        )
    unique = {reference.path: reference for reference in references}
    return ProvisionQuery(tuple(unique.values()), title, unknown_title)


def _reference_from_match(
    match: re.Match[str], title: str | None, unknown_title: str | None
) -> ProvisionReference:
    if match is None:
        raise ValueError("match is required")
    path = f"제{int(match.group('article'))}조"
    if branch := match.group("branch"):
        path += f"의{int(branch)}"
    if paragraph := match.group("paragraph"):
        path += f"/항{_number_value(paragraph)}"
    if item := match.group("item"):
        path += f"/호{int(item)}"
    if subitem := match.group("subitem"):
        path += f"/목{subitem}"
    return ProvisionReference(path, title, unknown_title)


def _document_title(query: str) -> tuple[str | None, str | None]:
    compact_query = _compact(query)
    title_candidates = [
        (_compact(entry.title), entry.title)
        for entry in MVP_CATALOG
        if _compact(entry.title) in compact_query
    ]
    title_candidates.extend(
        (alias, title) for alias, title in _DOCUMENT_TITLE_ALIASES.items() if alias in compact_query
    )
    recognized_title = (
        max(title_candidates, key=lambda candidate: len(candidate[0]))[1]
        if title_candidates
        else None
    )
    unknown_title_match = re.search(
        r"(?P<title>[0-9A-Za-z가-힣ㆍ·()]+(?:\s+[0-9A-Za-z가-힣ㆍ·()]+){0,5}"
        r"(?:법|령|규칙|기준))\s*(?:의|에서)?\s*(?:제\s*)?\d+\s*조",
        unicodedata.normalize("NFKC", query),
    )
    return recognized_title, (
        " ".join(unknown_title_match.group("title").split())
        if unknown_title_match and recognized_title is None
        else None
    )


def _normalize_korean_provision_numbers(query: str) -> str:
    normalized = unicodedata.normalize("NFKC", query)
    pattern = re.compile(r"제\s*([영공일이삼사오육칠팔구십백]+)\s*(조|항|호)")
    return pattern.sub(
        lambda match: f"제{_korean_number(match.group(1))}{match.group(2)}", normalized
    )


def _korean_number(value: str) -> int:
    if "백" in value:
        hundreds, rest = value.split("백", 1)
        return (_KOREAN_DIGITS.get(hundreds, 1) * 100) + (_korean_number(rest) if rest else 0)
    if "십" in value:
        tens, ones = value.split("십", 1)
        return (_KOREAN_DIGITS.get(tens, 1) * 10) + (_KOREAN_DIGITS[ones] if ones else 0)
    if len(value) == 1:
        return _KOREAN_DIGITS[value]
    raise ValueError(f"unsupported Korean number: {value}")


def _compact(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).casefold()
    return re.sub(r"[^0-9a-z가-힣]", "", normalized)


def _number_value(value: str) -> int:
    return _CIRCLED_NUMBER_VALUES[value] if value in _CIRCLED_NUMBER_VALUES else int(value)
