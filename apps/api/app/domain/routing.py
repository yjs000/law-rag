"""Pre-retrieval question routing (0028 / plan 0025 M4.5).

Decides, before query embedding or legal search runs, whether a question
should go to the frozen D1/D2 legal-search path or terminate early because
it needs something the system does not collect: missing user facts
(clarification), realtime information, or an external document.
"""

from dataclasses import dataclass
from typing import Literal

QuestionRoute = Literal[
    "clarification_required",
    "realtime_required",
    "external_document_required",
    "legal_search",
]

RouterTier = Literal[1, 2, 3]


@dataclass(frozen=True)
class RouteDecision:
    route: QuestionRoute
    reason_code: str
    tier: RouterTier
    confidence: float
    missing_fields: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be within [0, 1]")


# Tier 1: deterministic keyword rules. Confident matches skip tiers 2/3
# entirely (0 embedding/search/LLM calls).

_REALTIME_KEYWORDS: tuple[str, ...] = (
    "올해",
    "이번 달",
    "이번달",
    "현재 가격",
    "지금 가격",
    "요즘 가격",
    "최근 가격",
    "현재 시세",
    "지금 시세",
    "고장",
    "복구 예정",
    "복구 일정",
    "오늘",
    "지금 상태",
    "이번 분기",
)

_EXTERNAL_DOCUMENT_KEYWORDS: tuple[str, ...] = (
    "계약서",
    "정산서",
    "청구서",
    "공사비 산출서",
    "산출내역서",
    "견적서",
    "명세서",
)


def match_realtime_keywords(question: str) -> tuple[str, ...]:
    """Return the realtime-dependency keywords found in the question, if any."""
    return tuple(keyword for keyword in _REALTIME_KEYWORDS if keyword in question)


def match_external_document_keywords(question: str) -> tuple[str, ...]:
    """Return the external-document keywords found in the question, if any."""
    return tuple(keyword for keyword in _EXTERNAL_DOCUMENT_KEYWORDS if keyword in question)


def route_tier1(question: str) -> RouteDecision | None:
    """Try the free, deterministic tier. Returns None if inconclusive.

    Realtime and external-document keywords are checked before anything
    else: a question naming both a contract and this year's price is more
    reliably "needs something we don't have" than any downstream tier can
    resolve, so tier 1 does not try to disambiguate between them.
    """
    document_hits = match_external_document_keywords(question)
    if document_hits:
        return RouteDecision(
            route="external_document_required",
            reason_code="tier1_document_keyword",
            tier=1,
            confidence=1.0,
        )
    realtime_hits = match_realtime_keywords(question)
    if realtime_hits:
        return RouteDecision(
            route="realtime_required",
            reason_code="tier1_realtime_keyword",
            tier=1,
            confidence=1.0,
        )
    return None


# Tier 2: nearest-labeled-example classification over existing query embeddings.
# No new LLM call - reuses whatever embedder already produced the query vector.

@dataclass(frozen=True)
class RouteExample:
    """A question with a confirmed route, used as a tier-2 reference point."""

    example_id: str
    route: QuestionRoute
    embedding: tuple[float, ...]
    missing_fields: tuple[str, ...] = ()


@dataclass(frozen=True)
class NearestExampleMatch:
    example_id: str
    route: QuestionRoute
    similarity: float
    missing_fields: tuple[str, ...] = ()


# 2026-08-07 calibration against the 10 D-10 examples (see 0028 decision log): the
# nearest-neighbor match was WRONG once even at similarity 0.72 (a legal_search example
# out-scored the correct clarification_required one), while several genuinely correct
# matches sat as low as 0.45-0.54. A single confidence threshold cannot fully separate
# "trustworthy" from "confidently wrong" with only 10 fixture points, so this is set
# conservatively - false positives here are worse than an extra tier-3 call - and tier 2
# will fall through to tier 3 more often than a naive reading of the similarities would
# suggest. Revisit once the fixture grows past D-10.
TIER2_CONFIDENCE_THRESHOLD = 0.70


def cosine_similarity(a: tuple[float, ...], b: tuple[float, ...]) -> float:
    if len(a) != len(b):
        raise ValueError("vectors must have the same dimensionality")
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    norm_a = sum(x * x for x in a) ** 0.5
    norm_b = sum(y * y for y in b) ** 0.5
    if norm_a == 0 or norm_b == 0:
        raise ValueError("cannot compute cosine similarity against a zero vector")
    return dot / (norm_a * norm_b)


def nearest_example(
    query_embedding: tuple[float, ...], examples: tuple[RouteExample, ...]
) -> NearestExampleMatch:
    if not examples:
        raise ValueError("at least one route example is required")
    best = max(examples, key=lambda ex: cosine_similarity(query_embedding, ex.embedding))
    return NearestExampleMatch(
        example_id=best.example_id,
        route=best.route,
        similarity=cosine_similarity(query_embedding, best.embedding),
        missing_fields=best.missing_fields,
    )


def route_tier2(
    query_embedding: tuple[float, ...],
    examples: tuple[RouteExample, ...],
    *,
    threshold: float = TIER2_CONFIDENCE_THRESHOLD,
) -> tuple[RouteDecision | None, NearestExampleMatch]:
    """Try the nearest-example tier. Always returns the match (for tier-3 hinting),

    plus a RouteDecision only when the match clears ``threshold`` confidently.
    """
    match = nearest_example(query_embedding, examples)
    if match.similarity < threshold:
        return None, match
    return (
        RouteDecision(
            route=match.route,
            reason_code=f"tier2_nearest_example:{match.example_id}",
            tier=2,
            confidence=match.similarity,
            missing_fields=match.missing_fields,
        ),
        match,
    )
