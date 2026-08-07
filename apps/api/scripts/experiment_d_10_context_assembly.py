"""M4 (실험 D2) offline context-assembly calibration for D-10.

Compares two context-assembly strategies (A: 조문당 최고 leaf 1개, B: 조·항·호·목
계층 복원) over two candidate rankings (raw, R1) using only artifacts already on
disk. No new query embedding, DB read, or NIM call.

Inputs (all local, already fetched):
  - D-10 raw run: .data/experiments/d-manual/runs/<run-id>/result.json
  - R1 rerank:     .../rerank/<profile>/comparison.json
  - D-10 manual review (context_verdict baseline): .../manual-review.json
  - Full corpus export (for hierarchy restoration): 0030 sealed corpus.jsonl
  - Sealed D-10 Gold (direct-evidence qrels): 0030 sealed judgments.jsonl

Output: a JSON report with per-combo metrics, printed to stdout. This is a
calibration diagnostic, not the frozen search-context-contract-v1 artifact.
"""

from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass, field, replace
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]

RUN_DIR = (
    REPO_ROOT
    / ".data/experiments/d-manual/runs/d10-20260805t065001773007z-442bef4a327b"
)
RESULT_PATH = RUN_DIR / "result.json"
MANUAL_REVIEW_PATH = RUN_DIR / "manual-review.json"
RERANK_COMPARISON_PATH = (
    RUN_DIR / "rerank" / "d10-parent-heading-directness-v1" / "comparison.json"
)
SEALED_DIR = (
    REPO_ROOT
    / ".data/experiments/d-gold-10/d10-gold-20260807t065254073895z/review/sealed"
)
CORPUS_PATH = (
    REPO_ROOT
    / ".data/experiments/d-gold-10/d10-gold-20260807t065254073895z/corpus.jsonl"
)
JUDGMENTS_PATH = SEALED_DIR / "judgments.jsonl"


@dataclass
class Candidate:
    provision_id: str
    document_id: str
    document_title: str
    path: str
    parent_path: str | None
    heading: str | None
    content: str
    rank: int


@dataclass
class CorpusRecord:
    provision_id: str
    document_id: str
    path: str
    parent_path: str | None
    heading: str | None
    content: str
    ordinal: int


def load_jsonl(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def article_key(document_id: str, path: str, parent_path: str | None) -> tuple[str, str]:
    return (document_id, parent_path or path)


def load_raw_candidates() -> dict[str, list[Candidate]]:
    result = json.loads(RESULT_PATH.read_text(encoding="utf-8"))
    by_case: dict[str, list[Candidate]] = {}
    for case in result["cases"]:
        cands = [
            Candidate(
                provision_id=c["provision_id"],
                document_id=c["document_id"],
                document_title=c["document_title"],
                path=c["path"],
                parent_path=c.get("parent_path"),
                heading=c.get("heading"),
                content=c["content"],
                rank=c["rank"],
            )
            for c in case["raw_candidates"]
        ]
        cands.sort(key=lambda c: c.rank)
        by_case[case["case_id"]] = cands
    return by_case


def load_r1_order() -> dict[str, list[str]]:
    comparison = json.loads(RERANK_COMPARISON_PATH.read_text(encoding="utf-8"))
    by_case: dict[str, list[str]] = {}
    for case in comparison["cases"]:
        ordered = sorted(case["reranked_candidates"], key=lambda c: c["rerank_rank"])
        by_case[case["case_id"]] = [c["provision_id"] for c in ordered]
    return by_case


def load_context_verdicts() -> dict[str, str]:
    manual = json.loads(MANUAL_REVIEW_PATH.read_text(encoding="utf-8"))
    return {
        case["case_id"]: case["assistant_review"]["context_verdict"]
        for case in manual["cases"]
    }


CorpusIndex = tuple[
    dict[tuple[str, str], CorpusRecord], dict[tuple[str, str], list[CorpusRecord]]
]


def load_corpus_index() -> CorpusIndex:
    by_path: dict[tuple[str, str], CorpusRecord] = {}
    children_by_article: dict[tuple[str, str], list[CorpusRecord]] = defaultdict(list)
    for row in load_jsonl(CORPUS_PATH):
        rec = CorpusRecord(
            provision_id=row["provision_id"],
            document_id=row["document_id"],
            path=row["path"],
            parent_path=row.get("parent_path"),
            heading=row.get("heading"),
            content=row["content"],
            ordinal=row["ordinal"],
        )
        by_path[(rec.document_id, rec.path)] = rec
        if rec.parent_path is not None:
            children_by_article[(rec.document_id, rec.parent_path)].append(rec)
    for key in children_by_article:
        children_by_article[key].sort(key=lambda r: r.ordinal)
    return by_path, children_by_article


def load_direct_evidence() -> dict[str, set[str]]:
    by_case: dict[str, set[str]] = defaultdict(set)
    for row in load_jsonl(JUDGMENTS_PATH):
        if row["relevance"] == 2:
            by_case[row["case_id"]].add(row["provision_id"])
    return by_case


@dataclass
class AssembledArticle:
    article_key: tuple[str, str]
    text: str
    char_count: int
    leaf_provision_ids: list[str] = field(default_factory=list)


def assemble_variant_a(
    ranked: list[Candidate], max_articles: int, char_budget: int
) -> tuple[list[AssembledArticle], bool]:
    """A: dedupe by article, best-ranked leaf only, no hierarchy restoration."""
    seen_articles: set[tuple[str, str]] = set()
    articles: list[AssembledArticle] = []
    total_chars = 0
    budget_exceeded = False
    for cand in ranked:
        key = article_key(cand.document_id, cand.path, cand.parent_path)
        if key in seen_articles:
            continue
        if len(articles) >= max_articles:
            break
        unit_text = cand.content
        unit_chars = len(unit_text)
        if total_chars + unit_chars > char_budget:
            budget_exceeded = True
            continue
        seen_articles.add(key)
        total_chars += unit_chars
        articles.append(
            AssembledArticle(
                article_key=key,
                text=unit_text,
                char_count=unit_chars,
                leaf_provision_ids=[cand.provision_id],
            )
        )
    return articles, budget_exceeded


def assemble_variant_b(
    ranked: list[Candidate],
    max_articles: int,
    char_budget: int,
    by_path: dict[tuple[str, str], CorpusRecord],
    children_by_article: dict[tuple[str, str], list[CorpusRecord]],
) -> tuple[list[AssembledArticle], bool]:
    """B: dedupe by article (same selection as A), restore full 조/항/호/목 hierarchy."""
    seen_articles: set[tuple[str, str]] = set()
    articles: list[AssembledArticle] = []
    total_chars = 0
    budget_exceeded = False
    for cand in ranked:
        key = article_key(cand.document_id, cand.path, cand.parent_path)
        if key in seen_articles:
            continue
        if len(articles) >= max_articles:
            break

        document_id, article_path = key
        root = by_path.get((document_id, article_path))
        children = children_by_article.get(key, [])
        units: list[CorpusRecord] = ([root] if root is not None else []) + children
        if not units:
            units = [
                CorpusRecord(
                    provision_id=cand.provision_id,
                    document_id=cand.document_id,
                    path=cand.path,
                    parent_path=cand.parent_path,
                    heading=cand.heading,
                    content=cand.content,
                    ordinal=0,
                )
            ]

        unit_text = "\n".join(u.content for u in units)
        unit_chars = len(unit_text)
        if total_chars + unit_chars > char_budget:
            budget_exceeded = True
            continue
        seen_articles.add(key)
        total_chars += unit_chars
        articles.append(
            AssembledArticle(
                article_key=key,
                text=unit_text,
                char_count=unit_chars,
                leaf_provision_ids=[u.provision_id for u in units],
            )
        )
    return articles, budget_exceeded


def evaluate_combo(
    case_id: str,
    articles: list[AssembledArticle],
    ranked: list[Candidate],
    direct_evidence: set[str],
    budget_exceeded: bool,
    manual_context_verdict: str,
) -> dict:
    included_ids = {pid for a in articles for pid in a.leaf_provision_ids}
    hit = bool(direct_evidence & included_ids)
    first_rank = None
    if hit:
        rank_by_id = {c.provision_id: c.rank for c in ranked}
        hit_ranks = [rank_by_id[pid] for pid in direct_evidence if pid in rank_by_id]
        first_rank = min(hit_ranks) if hit_ranks else None
    total_chars = sum(a.char_count for a in articles)
    context_available = len(articles) > 0 and not (budget_exceeded and not articles)
    # manual verdict was judged against the original raw top 10, not this assembly;
    # "blocked" cases have no positive qrel at all, so no assembly can ever hit them.
    if manual_context_verdict == "sufficient":
        matches_manual_verdict = hit
    else:
        matches_manual_verdict = not hit or manual_context_verdict == "blocked"
    return {
        "case_id": case_id,
        "direct_evidence_included": hit,
        "first_direct_evidence_rank": first_rank,
        "article_count": len(articles),
        "duplicate_articles": len(articles) != len({a.article_key for a in articles}),
        "char_count": total_chars,
        "approx_tokens": round(total_chars / 2.2),
        "context_budget_exceeded": budget_exceeded,
        "context_available": context_available,
        "manual_context_verdict": manual_context_verdict,
        "matches_manual_verdict": matches_manual_verdict,
    }


def main() -> None:
    raw_by_case = load_raw_candidates()
    r1_order_by_case = load_r1_order()
    direct_evidence_by_case = load_direct_evidence()
    context_verdicts = load_context_verdicts()
    by_path, children_by_article = load_corpus_index()

    variants = [
        ("A", 5, 60_000),
        ("B", 3, 30_000),
        ("B", 3, 60_000),
        ("B", 5, 30_000),
        ("B", 5, 60_000),
    ]

    report: dict[str, dict] = {}
    for ranking_name in ("raw", "R1"):
        for kind, max_articles, char_budget in variants:
            combo_name = f"{ranking_name}+{kind}-{max_articles}-{char_budget}"
            per_case = []
            for case_id, raw_cands in raw_by_case.items():
                if ranking_name == "raw":
                    ranked = raw_cands
                else:
                    order = r1_order_by_case[case_id]
                    by_id = {c.provision_id: c for c in raw_cands}
                    # rank must reflect R1 position, not the stale raw rank,
                    # since evaluate_combo reports first_direct_evidence_rank from it.
                    ranked = [
                        replace(by_id[pid], rank=position)
                        for position, pid in enumerate(order, start=1)
                        if pid in by_id
                    ]

                if kind == "A":
                    articles, exceeded = assemble_variant_a(ranked, max_articles, char_budget)
                else:
                    articles, exceeded = assemble_variant_b(
                        ranked, max_articles, char_budget, by_path, children_by_article
                    )
                per_case.append(
                    evaluate_combo(
                        case_id,
                        articles,
                        ranked,
                        direct_evidence_by_case.get(case_id, set()),
                        exceeded,
                        context_verdicts[case_id],
                    )
                )

            hits = sum(1 for c in per_case if c["direct_evidence_included"])
            context_available = sum(1 for c in per_case if c["context_available"])
            budget_exceeded_cases = [c["case_id"] for c in per_case if c["context_budget_exceeded"]]
            avg_chars = round(sum(c["char_count"] for c in per_case) / len(per_case))
            avg_tokens = round(sum(c["approx_tokens"] for c in per_case) / len(per_case))
            total_tokens = sum(c["approx_tokens"] for c in per_case)

            report[combo_name] = {
                "ranking": ranking_name,
                "assembly": kind,
                "max_articles": max_articles,
                "char_budget": char_budget,
                "direct_evidence_hit_count": hits,
                "context_available_count": context_available,
                "budget_exceeded_cases": budget_exceeded_cases,
                "avg_char_count": avg_chars,
                "avg_approx_tokens": avg_tokens,
                "total_approx_tokens": total_tokens,
                "per_case": per_case,
            }

    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
