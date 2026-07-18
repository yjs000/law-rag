import re
import unicodedata
from dataclasses import dataclass
from itertools import combinations

from app.domain.catalog import MVP_CATALOG


@dataclass(frozen=True)
class PreparedSearchQuery:
    original: str
    normalized_text: str
    terms: tuple[str, ...]
    expanded_terms: tuple[str, ...]
    anchor_term: str | None
    strict_query: str
    minimum_match_query: str
    anchored_query: str


@dataclass(frozen=True)
class SearchStageTrace:
    stage: str
    query: str | None
    raw_candidate_count: int
    accepted_candidate_count: int
    duration_ms: float
    status: str

    def as_dict(self) -> dict[str, object]:
        return {
            "stage": self.stage,
            "query": self.query,
            "raw_candidate_count": self.raw_candidate_count,
            "accepted_candidate_count": self.accepted_candidate_count,
            "duration_ms": round(self.duration_ms, 3),
            "status": self.status,
        }


@dataclass(frozen=True)
class SearchTrace:
    strategy: str
    normalized_query: str
    terms: tuple[str, ...]
    executed_query: str | None
    relaxed: bool
    reference_title: str | None
    reference_path: str | None
    candidate_count: int
    anchor_term: str | None = None
    stages: tuple[SearchStageTrace, ...] = ()
    total_duration_ms: float = 0.0

    def as_dict(self) -> dict[str, object]:
        return {
            "strategy": self.strategy,
            "normalized_query": self.normalized_query,
            "terms": list(self.terms),
            "executed_query": self.executed_query,
            "relaxed": self.relaxed,
            "reference_title": self.reference_title,
            "reference_path": self.reference_path,
            "candidate_count": self.candidate_count,
            "anchor_term": self.anchor_term,
            "stages": [stage.as_dict() for stage in self.stages],
            "total_duration_ms": round(self.total_duration_ms, 3),
        }


_KOREAN_PARTICLES = (
    "으로부터",
    "에게서",
    "에서는",
    "으로는",
    "에서",
    "에게",
    "께서",
    "까지",
    "부터",
    "처럼",
    "보다",
    "으로",
    "와",
    "과",
    "은",
    "는",
    "이",
    "가",
    "을",
    "를",
    "의",
    "에",
    "로",
    "도",
    "만",
)

_KOREAN_ENDINGS = (
    "하려면",
    "하려는",
    "해야",
    "하나요",
    "되는",
    "하는",
    "인가요",
    "인가",
    "나요",
    "가요",
    "까요",
    "할",
)

_QUESTION_FILLER_PREFIXES = (
    "알려",
    "무엇",
    "어떤",
    "어떻게",
    "궁금",
    "보여",
    "설명",
    "확인",
    "필요",
)

_QUESTION_INTENT_TERMS = {
    "관련",
    "대해",
    "대한",
    "절차",
    "내용",
    "질문",
    "경우",
    "하는",
}

_ALIASES = {
    "신재생": ("신에너지", "재생에너지"),
    "신재생에너지": ("신에너지", "재생에너지"),
    "ess": ("전기저장시설", "에너지저장장치"),
    "에너지저장장치": ("전기저장시설",),
    "인허가": ("인가", "허가"),
}

_DOMAIN_ANCHOR_TERMS = frozenset(
    {
        "기준",
        "기술기준",
        "등록",
        "서류",
        "신고",
        "신청",
        "요건",
        "의무",
        "인가",
        "허가",
    }
)


def normalize_text(value: str) -> str:
    return unicodedata.normalize("NFKC", value).casefold()


def compact_text(value: str) -> str:
    return re.sub(r"[^0-9a-z가-힣]", "", normalize_text(value))


def prepare_search_query(query: str) -> PreparedSearchQuery:
    """사용자 문장을 안전한 PGroonga 토큰 질의로 변환한다."""
    terms: list[str] = []
    for raw in re.findall(r"[가-힣A-Za-z0-9]+", normalize_text(query)):
        term = _normalize_term(raw)
        if len(term) < 2 or _is_question_filler(term) or term in _QUESTION_INTENT_TERMS:
            continue
        if term not in terms:
            terms.append(term)
        if len(terms) == 5:
            break

    expanded = list(terms)
    for term in terms:
        for alias in _ALIASES.get(term, ()):
            if alias not in expanded:
                expanded.append(alias)

    expressions = [_term_expression(term) for term in terms]
    anchor_term = _select_anchor(terms)
    strict_query = " ".join(expressions)
    minimum_match_query = _minimum_match_query(expressions)
    anchored_query = _anchored_query(terms, expressions, anchor_term)
    return PreparedSearchQuery(
        original=query,
        normalized_text=" ".join(terms),
        terms=tuple(terms),
        expanded_terms=tuple(expanded),
        anchor_term=anchor_term,
        strict_query=strict_query,
        minimum_match_query=minimum_match_query,
        anchored_query=anchored_query,
    )


def term_variants(term: str) -> tuple[str, ...]:
    return (term, *_ALIASES.get(term, ()))


def matching_terms(value: str, prepared: PreparedSearchQuery) -> set[str]:
    normalized = normalize_text(value)
    return {
        term
        for term in prepared.terms
        if any(variant in normalized for variant in term_variants(term))
    }


def _term_expression(term: str) -> str:
    variants = term_variants(term)
    return variants[0] if len(variants) == 1 else f"({' OR '.join(variants)})"


def _minimum_match_query(expressions: list[str]) -> str:
    if len(expressions) < 3:
        return " ".join(expressions)
    return " OR ".join(f"({left} {right})" for left, right in combinations(expressions, 2))


def _anchored_query(
    terms: list[str], expressions: list[str], anchor_term: str | None
) -> str:
    if anchor_term is None:
        return ""
    if len(expressions) <= 2:
        return " ".join(expressions)
    anchor_index = terms.index(anchor_term)
    secondary = [value for index, value in enumerate(expressions) if index != anchor_index]
    if not secondary:
        return expressions[anchor_index]
    return f"{expressions[anchor_index]} ({' OR '.join(secondary)})"


def _select_anchor(terms: list[str]) -> str | None:
    if not terms:
        return None
    titles = [normalize_text(entry.title) for entry in MVP_CATALOG]

    def title_matches(term: str) -> int:
        variants = term_variants(term)
        return sum(any(variant in title for variant in variants) for title in titles)

    catalog_terms = [(title_matches(term), term) for term in terms if title_matches(term)]
    if catalog_terms:
        return min(catalog_terms, key=lambda item: (item[0], -len(item[1])))[1]
    domain_terms = [term for term in terms if term in _DOMAIN_ANCHOR_TERMS]
    return max(domain_terms, key=len) if domain_terms else None


def _normalize_term(term: str) -> str:
    normalized = term
    for ending in _KOREAN_ENDINGS:
        if normalized.endswith(ending) and len(normalized) - len(ending) >= 2:
            normalized = normalized[: -len(ending)]
            break
    for suffix in _KOREAN_PARTICLES:
        if normalized.endswith(suffix) and len(normalized) - len(suffix) >= 2:
            normalized = normalized[: -len(suffix)]
            break
    return normalized


def _is_question_filler(term: str) -> bool:
    return any(term.startswith(prefix) for prefix in _QUESTION_FILLER_PREFIXES)
