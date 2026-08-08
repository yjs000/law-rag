"""0028 tier 1 term-dictionary build + held-out coverage check.

Splits the v1 lay-energy question bank (evaluation/experiment-d-lay-energy-query-bank-
v1-draft.json, 1,000 questions) deterministically into a ~200-question BUILD set and an
~800-question EVAL set, using each question's own `question_sha256` (no random seed
needed, same split every run). Kiwi morphological analysis runs only on the BUILD set to
produce candidate stems for the three tier-1 lexical categories (realtime, external-
document, conditional-variance). The EVAL set is never used to mine candidates - it is
only used to check how the *current* app/domain/routing.py keyword lists (whatever a
human has actually curated in) generalize to held-out questions, so dictionary building
doesn't quietly overfit to the same 1,000 questions it's evaluated against.

This is a build-time analysis tool, not runtime code: its output is human-reviewed input
to the keyword tuples hardcoded in app/domain/routing.py, not a JSON file loaded at
request time (the domain layer stays pure/I/O-free).

One-command usage:
    uv run python scripts/build_tier1_term_dictionary.py
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

if sys.stdout.encoding is None or sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]

_API_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_API_ROOT))  # lets `python scripts/....py` find app.* unaided

from kiwipiepy import Kiwi  # noqa: E402

from app.domain.routing import (  # noqa: E402
    match_conditional_variance_phrase,
    match_external_document_keywords,
    match_realtime_keywords,
)

QUESTION_BANK_PATH = _API_ROOT / "evaluation" / "experiment-d-lay-energy-query-bank-v1-draft.json"
OUTPUT_PATH = _API_ROOT / "evaluation" / "tier1-term-dictionary-analysis-v1.json"

_CONTENT_TAGS = {"NNG", "NNP", "VV", "VA", "MAG"}

# BUILD/EVAL split: deterministic via question_sha256 (no RNG, no seed to lose track of).
# ~20% land in BUILD (target ~200 of 1,000); the rest are EVAL.
_BUILD_SET_MODULUS = 5
_BUILD_SET_REMAINDER = 0

# Time-deictic stems: words whose referent shifts with the calendar date, independent
# of legal topic. A question containing one of these needs a "what is true right now"
# answer that a static law corpus cannot give.
_TEMPORAL_DEICTIC_STEMS = {
    "올해",
    "금년",
    "작년",
    "전년",
    "내년",
    "이번",
    "현재",
    "지금",
    "요즘",
    "최근",
    "당해",
    "오늘",
    "이달",
}

# Document-type nouns: candidates are any NNG/NNP stem ending in 서(書) or 증(證) that
# names a paper artifact a user would need to physically hold or look up, not a legal
# concept the corpus already defines. Reviewed manually before being added to routing.py.
_DOCUMENT_SUFFIXES = ("서", "증")

# Terms that end in a document suffix but name a legal *concept* the law corpus can
# explain on its own (e.g. "신고서를 언제 내야 하나요" is answerable from the statute
# that defines the filing requirement) - excluded even though they match the suffix.
_DOCUMENT_SUFFIX_FALSE_POSITIVES = {
    "허가서",  # 허가 절차 자체는 법령으로 설명 가능 (허가증 실물 필요와는 다름)
    "신고서",  # 신고 절차/요건은 법령으로 설명 가능
    "인가서",
    "등록증",  # 등록 요건은 법령으로 설명 가능; 실물 등록증 확인은 external_document의 별도 범주
}


def load_questions() -> list[dict]:
    data = json.loads(QUESTION_BANK_PATH.read_text(encoding="utf-8"))
    return data["questions"]


def split_build_eval(questions: list[dict]) -> tuple[list[dict], list[dict]]:
    build, held_out = [], []
    for q in questions:
        digest = int(q["question_sha256"], 16)
        (build if digest % _BUILD_SET_MODULUS == _BUILD_SET_REMAINDER else held_out).append(q)
    return build, held_out


def mine_candidates(build_questions: list[dict]) -> dict:
    """Kiwi morphological analysis over the BUILD set only."""
    kiwi = Kiwi()
    stem_doc_freq: Counter[tuple[str, str]] = Counter()
    for q in build_questions:
        seen_in_question: set[tuple[str, str]] = set()
        for token in kiwi.tokenize(q["question"]):
            if token.tag in _CONTENT_TAGS and len(token.form) >= 2:
                seen_in_question.add((token.form, token.tag))
        stem_doc_freq.update(seen_in_question)

    temporal_candidates = {
        stem: freq for (stem, tag), freq in stem_doc_freq.items() if stem in _TEMPORAL_DEICTIC_STEMS
    }
    document_candidates = {
        stem: freq
        for (stem, tag), freq in stem_doc_freq.items()
        if tag in {"NNG", "NNP"}
        and stem.endswith(_DOCUMENT_SUFFIXES)
        and stem not in _DOCUMENT_SUFFIX_FALSE_POSITIVES
        and len(stem) >= 3
    }
    conditional_variance_stems = {
        stem: freq
        for (stem, tag), freq in stem_doc_freq.items()
        if tag == "VA" and stem in {"다르", "같"}
    } | {
        stem: freq
        for (stem, tag), freq in stem_doc_freq.items()
        if tag == "VV" and stem in {"달라지", "따르", "구분되", "나뉘"}
    }

    return {
        "build_set_size": len(build_questions),
        "temporal_deictic_candidates": dict(
            sorted(temporal_candidates.items(), key=lambda kv: -kv[1])
        ),
        "document_type_candidates": dict(
            sorted(document_candidates.items(), key=lambda kv: -kv[1])
        ),
        "document_type_excluded_false_positives": sorted(_DOCUMENT_SUFFIX_FALSE_POSITIVES),
        "conditional_variance_stem_candidates": dict(
            sorted(conditional_variance_stems.items(), key=lambda kv: -kv[1])
        ),
        "top_100_content_stems": [
            {"stem": stem, "tag": tag, "document_frequency": freq}
            for (stem, tag), freq in stem_doc_freq.most_common(100)
        ],
    }


def evaluate_held_out(eval_questions: list[dict]) -> dict:
    """Apply the CURRENT app/domain/routing.py tier-1 rules to the held-out set.

    This measures generalization, not recall against gold labels - there is no gold
    for these 1,000 questions outside D-10. It reports coverage plus a small sample of
    matches per category so a human can spot-check for false positives the 200-question
    BUILD set never surfaced.
    """
    realtime_hits = [q for q in eval_questions if match_realtime_keywords(q["question"])]
    document_hits = [q for q in eval_questions if match_external_document_keywords(q["question"])]
    conditional_hits = [
        q for q in eval_questions if match_conditional_variance_phrase(q["question"])
    ]
    n = len(eval_questions)
    return {
        "eval_set_size": n,
        "realtime_hit_rate": round(len(realtime_hits) / n, 4),
        "document_hit_rate": round(len(document_hits) / n, 4),
        "conditional_variance_hit_rate": round(len(conditional_hits) / n, 4),
        "realtime_sample": [q["question"] for q in realtime_hits[:5]],
        "document_sample": [q["question"] for q in document_hits[:5]],
        "conditional_variance_sample": [q["question"] for q in conditional_hits[:5]],
    }


def main() -> None:
    questions = load_questions()
    build_questions, eval_questions = split_build_eval(questions)

    report = {
        "corpus_size": len(questions),
        "build": mine_candidates(build_questions),
        "eval": evaluate_held_out(eval_questions),
        "build_question_ids": sorted(q["id"] for q in build_questions),
    }
    OUTPUT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"corpus: {report['corpus_size']} questions -> {OUTPUT_PATH}")
    print(f"build set: {report['build']['build_set_size']} questions (candidate mining)")
    print(f"eval set: {report['eval']['eval_set_size']} questions (held-out coverage check)")
    print("build: temporal candidates:", report["build"]["temporal_deictic_candidates"])
    print("build: document candidates:", report["build"]["document_type_candidates"])
    print(
        "build: conditional-variance stem candidates:",
        report["build"]["conditional_variance_stem_candidates"],
    )
    print("eval: realtime hit rate:", report["eval"]["realtime_hit_rate"])
    print("eval: document hit rate:", report["eval"]["document_hit_rate"])
    print("eval: conditional-variance hit rate:", report["eval"]["conditional_variance_hit_rate"])


if __name__ == "__main__":
    main()
