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
