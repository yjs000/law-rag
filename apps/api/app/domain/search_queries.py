import re
import unicodedata
from dataclasses import dataclass


@dataclass(frozen=True)
class PreparedSearchQuery:
    original: str
    normalized_text: str
    terms: tuple[str, ...]
    expanded_terms: tuple[str, ...]
    strict_query: str
    relaxed_query: str


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
        if len(terms) == 12:
            break

    expanded = list(terms)
    for term in terms:
        for alias in _ALIASES.get(term, ()):
            if alias not in expanded:
                expanded.append(alias)

    strict_query = " ".join(terms)
    relaxed_query = " OR ".join(expanded)
    return PreparedSearchQuery(
        original=query,
        normalized_text=" ".join(terms),
        terms=tuple(terms),
        expanded_terms=tuple(expanded),
        strict_query=strict_query,
        relaxed_query=relaxed_query,
    )


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
