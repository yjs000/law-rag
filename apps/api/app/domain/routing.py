"""Pre-retrieval question routing (0028 / plan 0025 M4.5).

Decides, before query embedding or legal search runs, whether a question
should go to the frozen D1/D2 legal-search path or terminate early because
it needs something the system does not collect: missing user facts
(clarification), realtime information, or an external document.
"""

import re
from dataclasses import dataclass
from typing import Literal, Protocol

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

# 2026-08-08: v1 질문은행(1,000문항, lay-energy-query-bank-v1-draft)을 question_sha256
# 기준으로 결정적 분할한 BUILD 200문항만 Kiwi로 형태소 분석해 후보를 채굴하고, 나머지
# EVAL 800문항은 사전에 반영하지 않고 커버리지 확인에만 쓴다(scripts/
# build_tier1_term_dictionary.py, evaluation/tier1-term-dictionary-analysis-v1.json) -
# 사전 구축에 쓴 데이터로 다시 사전을 "검증"하는 leakage를 피하기 위해서다. document 목록은
# 서·증으로 끝나는 명사 후보 중 BUILD 200에서 나온 것만 검토했다 - "인증서"(3건)는 전부
# REC(신재생에너지 공급인증서) 발급 절차를 묻는 문항이라 법령으로 설명 가능한 절차 질문으로
# 판단해 제외했고, "보증서"(1건)는 "계약서와 보증서에서 수리 책임을 확인" 같은 실제 문서
# 대조 질문이라 채택했다.
#
# [2026-08-08 되돌림] 처음엔 "현재" 단독 어간도 BUILD 200의 개인 계정 상태 질문 2건
# 근거로 추가했으나, 사용자 지적으로 route-fixture-v1.json 평가에서 "현재 시행 중인
# 신재생에너지법의 허가 절차를 알려주세요"(법령 currency 질문, corpus의 as_of_date가 이미
# 처리하는 개념)가 realtime_required로 잘못 차단되는 걸 확인했다. tier1이 잘못 걸러내면
# 법령으로 답할 수 있는 질문도 못 답하게 되므로 - "정말 답할 수 없는 것만 타이트하게
# 거른다"는 방향에 따라 단독 어간 매칭을 버리고, 아래 `match_realtime_personal_state_phrase`
# 처럼 "시점어 + 개인·계정 상태 명사" 근접 매칭으로 좁혔다(더불어 "시행/유효한/법/법령/
# 기준일"이 바로 뒤에 오면 애초에 제외한다).
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
    "보증서",
)

# 시점어(현재/지금/최근/요즘) 바로 뒤에 이런 말이 오면 "지금 내 상태"가 아니라 "지금
# 시행 중인 법"을 가리키는 것이다 - as_of_date로 이미 처리되는 개념이라 realtime_required가
# 아니다.
_REALTIME_LAW_CURRENCY_EXCLUSION = r"시행|유효한|법령|법률|법(?!인)|규정|기준일|조문"

# 2026-08-08 corpus 검토(v1 질문은행 BUILD 200 + 전수 15문항 표본)에서 "현재"·"지금"·
# "최근"이 진짜 realtime_required였던 사례는 전부 이런 개인·계정 상태 명사와 같이
# 나타났다("현재 대기 순서", "현재 계약 조건", "현재 명의", "최근 사용량" 등). 시점어
# 단독으로는 판단하지 않고 이 명사와의 근접(12자 이내) 공기를 요구해 위양성을 줄인다.
_REALTIME_PERSONAL_STATE_NOUNS = (
    "순서",
    "조건",
    "기한",
    "수수료",
    "지원",
    "대출",
    "요금",
    "명의",
    "소유자",
    "사용량",
    "신청",
    "대기",
    "처리",
    "계약",
    "상태",
)
_REALTIME_PERSONAL_STATE_PATTERN = re.compile(
    r"(?:현재|지금|최근|요즘)(?!\s*(?:" + _REALTIME_LAW_CURRENCY_EXCLUSION + r"))"
    r"[^.?!]{0,12}(?:" + "|".join(_REALTIME_PERSONAL_STATE_NOUNS) + r")"
)


def match_realtime_personal_state_phrase(question: str) -> bool:
    return _REALTIME_PERSONAL_STATE_PATTERN.search(question) is not None


# 계약서·정산서 같은 단어가 있어도 "이 문서를 대조해달라"가 아니라 "법이 이걸 요구하는가"를
# 묻는 일반 법령 질문이면 external_document_required가 아니다 - 법령 corpus로 답 가능하다.
# 2026-08-08: route-fixture-v1.json 평가에서 "계약서를 반드시 작성해야 하는 법적 의무가
# 있나요?"가 잘못 차단되는 걸 확인하고 추가했다.
_GENERAL_LEGAL_REQUIREMENT_INQUIRY_PATTERN = re.compile(
    r"법적\s*의무|법령에\s*규정|법으로\s*정해|법적으로\s*정해|의무가\s*있|의무인가요|법령상"
)


def match_realtime_keywords(question: str) -> tuple[str, ...]:
    """Return the realtime-dependency keywords found in the question, if any."""
    return tuple(keyword for keyword in _REALTIME_KEYWORDS if keyword in question)


def match_external_document_keywords(question: str) -> tuple[str, ...]:
    """Return the external-document keywords found in the question, if any.

    A general "does the law require X document" question is excluded even if a
    document word appears - it's asking about the legal requirement, not asking to
    check the user's own document (see _GENERAL_LEGAL_REQUIREMENT_INQUIRY_PATTERN).
    """
    if _GENERAL_LEGAL_REQUIREMENT_INQUIRY_PATTERN.search(question):
        return ()
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
    if match_realtime_personal_state_phrase(question):
        return RouteDecision(
            route="realtime_required",
            reason_code="tier1_realtime_personal_state_phrase",
            tier=1,
            confidence=1.0,
        )
    if match_conditional_variance_phrase(question):
        return RouteDecision(
            route="clarification_required",
            reason_code="tier1_conditional_variance_phrase",
            tier=1,
            confidence=1.0,
        )
    return None


# "~에 따라 달라지나요/다른가요/다릅니다" etc: a syntactic marker that the answer
# branches on a fact the question has not supplied, e.g. "용량이나 사용 방식에 따라
# 허가와 신고가 어떻게 달라지나요?" (D-10 case 0251). Found during 2026-08-07 tier 2
# calibration: this pattern is what actually separates a clarification-needing
# question from a same-topic, generally-answerable one (D-10 case 0201) - topic
# embeddings conflate the two because both are "about" the same permit/report
# distinction. This rule only catches questions using this specific construction;
# it does not generalize to every clarification case (see tier 2/3).
_CONDITIONAL_VARIANCE_PATTERN = re.compile(r"에\s*따라.{0,20}?(달라|다른가|다릅)")


def match_conditional_variance_phrase(question: str) -> bool:
    return _CONDITIONAL_VARIANCE_PATTERN.search(question) is not None


# Tier 2: LLM self-judgment (Self-RAG "reflection token" style), optionally hinted by
# nearest-example embedding similarity. cosine_similarity/nearest_example are kept as a
# cheap, already-computed *hint* fed into the LLM prompt - not a standalone decision gate.
#
# 2026-08-08 decision (0028 "문제 탐색과 결론"): an embedding-similarity threshold gate
# (the previous tier 2) is retired as the decision mechanism. The 2026-08-07 calibration
# found a WRONG nearest-neighbor match (0.7185, a legal_search example out-scoring the
# correct clarification_required one) ranked ABOVE every correct match in the same batch
# (best correct match: 0.6947) - similarity magnitude and correctness were uncorrelated,
# not just noisy near one boundary. Root cause: topic embeddings answer "is this the same
# subject", but tier 2 needs "does this question already carry enough information to
# route it" - a pragmatic-sufficiency judgment, not a topic-similarity one. Published
# approaches to this class of problem (Self-RAG, Adaptive-RAG, ClariQ/Qulac, INTENT-SIM -
# see 0028 문제 탐색과 결론) use a judgment call (model-produced or entropy-over-answers),
# never raw embedding distance, to decide this. Nearest-example similarity is retained
# only as a weak, explicitly-labeled hint inside the tier-2 prompt.


@dataclass(frozen=True)
class RouteExample:
    """A question with a confirmed route, used as a tier-2 hint reference point."""

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


# <10-line route definitions per the 0028 tier-3 cost design: the prompt gets this and
# the question only, never the full corpus or design doc.
ROUTE_DEFINITIONS = """\
- legal_search: 법령 조문으로 일반적인 설명이 가능한 질문.
- clarification_required: 설비용량 등 사용자 사실에 따라 답이 달라져 먼저 물어야 하는 질문.
- realtime_required: 시점/개인 계정 상태에 따라 바뀌는 정보(가격·예산·처리 상태 등)가 \
필요한 질문.
- external_document_required: 계약서·정산서 등 사용자가 보유한 문서 대조가 필요한 질문.
"""


@dataclass(frozen=True)
class RouteJudgment:
    """Parsed tier-2 LLM output, before it becomes a RouteDecision."""

    route: QuestionRoute
    confidence: float
    reason: str
    missing_fields: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be within [0, 1]")


class RouteClassifier(Protocol):
    """Adapter boundary for the tier-2 LLM call (see NvidiaNimRouteClassifier)."""

    async def classify(
        self, question: str, hint: NearestExampleMatch | None
    ) -> RouteJudgment: ...


def build_tier2_prompt(question: str, hint: NearestExampleMatch | None) -> str:
    """Question + route definitions + an optional, explicitly weak nearest-example hint.

    The hint is framed as advisory to avoid anchoring the model on a possibly-wrong
    nearest neighbor (2026-08-07 calibration: similarity doesn't track correctness).
    """
    hint_text = "(참고할 유사 예시 없음)"
    if hint is not None:
        hint_text = (
            f"참고용 힌트(최종 판단의 근거로 쓰지 말 것): 가장 비슷한 예시의 route는 "
            f"'{hint.route}'이고 유사도는 {hint.similarity:.2f}. 유사도가 낮으면 이 힌트를 "
            "약하게만 신뢰하라. 최종 판단은 질문 원문만으로 독립적으로 하라."
        )
    return f"다음 route 중 하나로만 분류하라.\n{ROUTE_DEFINITIONS}\n질문: {question}\n{hint_text}"


async def route_tier2(
    question: str,
    classifier: RouteClassifier,
    *,
    hint: NearestExampleMatch | None = None,
) -> RouteDecision:
    judgment = await classifier.classify(question, hint)
    return RouteDecision(
        route=judgment.route,
        reason_code="tier2_llm_judgment",
        tier=2,
        confidence=judgment.confidence,
        missing_fields=judgment.missing_fields,
    )
