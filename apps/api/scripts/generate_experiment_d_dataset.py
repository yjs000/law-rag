"""운영 corpus에서 결정적으로 실험 D 1,000문항과 BEIR qrels를 생성한다."""

from __future__ import annotations

import argparse
import asyncio
import difflib
import hashlib
import json
import re
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from sqlalchemy import text

from app.adapters.postgres_repository import PostgresLegalRepository
from app.domain.embedding_profiles import embedding_text_sha256
from app.settings import get_settings

REPOSITORY_ROOT = Path(__file__).parents[3]
DEFAULT_DATASET = Path(__file__).parents[1] / "evaluation" / "experiment-d-v3-1000.json"
DEFAULT_REVIEW = REPOSITORY_ROOT / "docs" / "generated" / "experiment-d-v3-review.md"
DEFAULT_BEIR = REPOSITORY_ROOT / ".data" / "experiments" / "context" / "beir-v3"
DATASET_VERSION = "experiment-d-1000-v3-draft"
DEFAULT_QUOTAS = {
    "exact_path_control": 200,
    "heading_lexical_control": 200,
    "semantic_paraphrase": 200,
    "hierarchy_child": 150,
    "hard_contrast": 100,
    "temporal_before_effective": 75,
    "outside_corpus": 75,
}
OUTSIDE_CORPUS_TITLES = (
    "에너지법",
    "에너지이용 합리화법",
    "수소경제 육성 및 수소 안전관리에 관한 법률",
    "전기공사업법",
    "전력기술관리법",
    "원자력안전법",
    "기후위기 대응을 위한 탄소중립ㆍ녹색성장 기본법",
    "건축법",
    "개인정보 보호법",
    "저작권법",
    "근로기준법",
    "주택임대차보호법",
)
OUTSIDE_CORPUS_TOPICS = ("목적", "정의", "허가 요건", "신고 의무", "벌칙")
_CIRCLED = {character: index for index, character in enumerate("①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮⑯⑰⑱⑲⑳", 1)}
_ARTICLE = re.compile(r"^(제\d+조(?:의\d+)?)")
_DELETED_PROVISION = re.compile(
    r"^\s*(?:제\s*\d+\s*조(?:의\s*\d+)?(?:\([^)]*\))?|"
    r"[①-⑳]|\d+(?:의\d+)?\.|[가-힣]\.)?\s*삭제(?:\s|<|$)"
)
_STRUCTURE_MARKER = re.compile(r"^\s*제\s*\d+\s*(?:장|절)(?:의\s*\d+)?(?:\s|$)")
_SPACE = re.compile(r"\s+")


@dataclass(frozen=True, slots=True)
class SourceProvision:
    provision_id: str
    version_id: str
    document_id: str
    document_title: str
    source_kind: str
    mst: str
    effective_from: date
    effective_to: date | None
    source_url: str
    path: str
    parent_path: str | None
    heading: str | None
    content: str
    ordinal: int

    @property
    def content_sha256(self) -> str:
        return embedding_text_sha256(self.content)

    @property
    def article_path(self) -> str | None:
        match = _ARTICLE.match(self.path)
        return match.group(1) if match else None


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="실험 D 1,000문항 고정 평가셋 생성")
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--review", type=Path, default=DEFAULT_REVIEW)
    parser.add_argument("--beir-dir", type=Path, default=DEFAULT_BEIR)
    return parser.parse_args()


def _stable(items: list[SourceProvision], salt: str) -> list[SourceProvision]:
    return sorted(
        items,
        key=lambda item: hashlib.sha256(f"{salt}:{item.provision_id}".encode()).hexdigest(),
    )


def _clean(value: str) -> str:
    return _SPACE.sub(" ", value).strip()


def _excerpt(content: str, limit: int = 900) -> str:
    value = _clean(content)
    if len(value) <= limit:
        return value
    boundary = max(value.rfind(".", 0, limit), value.rfind("다.", 0, limit))
    return value[: boundary + 1 if boundary >= limit // 2 else limit].rstrip() + "…"


def _render_path(path: str) -> str:
    rendered: list[str] = []
    for component in path.split("/"):
        if component.startswith("제") and "조" in component:
            rendered.append(component)
        elif component.startswith("항"):
            value = component.removeprefix("항").rstrip(".")
            rendered.append(f"제{_CIRCLED.get(value, value)}항")
        elif component.startswith("호"):
            rendered.append(f"제{component.removeprefix('호').rstrip('.')}호")
        elif component.startswith("목"):
            rendered.append(f"{component.removeprefix('목').rstrip('.')}목")
    return " ".join(rendered)


def _topic(item: SourceProvision) -> str:
    if item.heading and _clean(item.heading):
        return _clean(item.heading)
    content = re.sub(r"^\s*(?:제\d+조(?:의\d+)?(?:\([^)]*\))?|[①-⑳]|\d+\.)\s*", "", item.content)
    return _clean(content)[:32].rstrip(" ,.;:") or _render_path(item.path)


def _has_direct_body(item: SourceProvision) -> bool:
    content = _clean(item.content)
    without_heading = re.sub(r"^제\d+조(?:의\d+)?(?:\([^)]*\))?\s*", "", content)
    without_number = re.sub(r"^(?:[①-⑳]|\d+\.|[가-힣]\.)\s*", "", without_heading)
    return len(without_number) >= 20


def _semantic_question(item: SourceProvision, topic: str) -> tuple[str, str]:
    content = _clean(item.content)
    if any(marker in content for marker in ("허가를 받아야", "인가를 받아야", "승인을 받아야")):
        question = f"{topic}에 적용되는 허가·인가·승인 요건은 무엇인가요?"
        template = "approval_requirement"
    elif any(marker in content for marker in ("신고하여야", "보고하여야")):
        question = f"{topic} 규정에서 요구하는 신고나 보고 의무는 무엇인가요?"
        template = "reporting_duty"
    elif any(marker in content for marker in ("해서는 아니", "하여서는 아니")):
        question = f"{topic} 규정에서 금지하는 행위는 무엇인가요?"
        template = "prohibition"
    elif "할 수 없다" in content:
        question = f"{topic} 규정에서 허용하지 않는 행위는 무엇인가요?"
        template = "not_permitted"
    elif "할 수 있다" in content:
        question = f"{topic} 규정이 허용하는 조치나 행위는 무엇인가요?"
        template = "permitted_action"
    else:
        question = f"{topic} 규정이 부과하는 의무는 무엇인가요?"
        template = "mandatory_action"
    return f"{item.document_title}에서 {question}", template


def _review_reasons(item: SourceProvision, *, template: str) -> list[str]:
    reasons: list[str] = []
    if len(_clean(item.content)) < 45:
        reasons.append("very_short_evidence")
    if len(item.content) > 4000:
        reasons.append("very_long_evidence")
    if "fallback" in template:
        reasons.append("generic_semantic_template")
    if re.search(r"제\d+조(?:의\d+)?에 따른", item.content) and len(item.content) < 120:
        reasons.append("cross_reference_dominant")
    return reasons


def _split(index: int) -> str:
    return "calibration" if index % 5 == 0 else "test"


def _qrels(
    item: SourceProvision,
    by_article: dict[tuple[str, str, str], list[SourceProvision]],
    *,
    exact_leaf: bool,
) -> list[dict[str, object]]:
    relevant = [item]
    if not exact_leaf and item.article_path:
        relevant = by_article[(item.document_id, item.version_id, item.article_path)]
    return [
        {
            "provision_id": candidate.provision_id,
            "document_id": candidate.document_id,
            "version_id": candidate.version_id,
            "path": candidate.path,
            "relevance": 2 if candidate.provision_id == item.provision_id else 1,
            "content_sha256": candidate.content_sha256,
        }
        for candidate in relevant
    ]


def _positive_case(
    *,
    case_id: str,
    category: str,
    question: str,
    item: SourceProvision,
    by_article: dict[tuple[str, str, str], list[SourceProvision]],
    index: int,
    template: str,
    exact_leaf: bool = False,
    distractor_ids: list[str] | None = None,
    generation_details: dict[str, object] | None = None,
) -> dict[str, object]:
    reasons = (
        _review_reasons(item, template=template)
        if category in {"semantic_paraphrase", "hard_contrast"}
        else []
    )
    return {
        "id": case_id,
        "split": _split(index),
        "category": category,
        "difficulty": "hard" if category in {"semantic_paraphrase", "hard_contrast"} else "medium",
        "answerable": True,
        "user_input": question,
        "as_of_date": item.effective_from.isoformat(),
        "reference": _excerpt(item.content),
        "reference_contexts": [_excerpt(item.content, 1600)],
        "primary_evidence": {
            "document_title": item.document_title,
            "source_kind": item.source_kind,
            "mst": item.mst,
            "document_id": item.document_id,
            "version_id": item.version_id,
            "provision_id": item.provision_id,
            "path": item.path,
            "content_sha256": item.content_sha256,
            "source_url": item.source_url,
        },
        "qrels": _qrels(item, by_article, exact_leaf=exact_leaf),
        "distractor_provision_ids": distractor_ids or [],
        "generation": {
            "method": "deterministic_template",
            "template_id": template,
            **(generation_details or {}),
        },
        "review": {
            "status": "needs_human_review" if reasons else "auto_validated",
            "reasons": reasons,
        },
    }


def _negative_case(
    *, case_id: str, category: str, question: str, as_of_date: date, index: int, reason: str
) -> dict[str, object]:
    return {
        "id": case_id,
        "split": _split(index),
        "category": category,
        "difficulty": "hard",
        "answerable": False,
        "user_input": question,
        "as_of_date": as_of_date.isoformat(),
        "reference": "현재 corpus와 기준일에서는 직접 근거를 찾을 수 없습니다.",
        "reference_contexts": [],
        "primary_evidence": None,
        "qrels": [],
        "distractor_provision_ids": [],
        "generation": {"method": "deterministic_boundary", "template_id": reason},
        "review": {"status": "auto_validated", "reasons": []},
    }


def build_dataset(
    provisions: list[SourceProvision], quotas: dict[str, int] | None = None
) -> dict[str, object]:
    quotas = quotas or DEFAULT_QUOTAS
    eligible = [
        item
        for item in provisions
        if item.article_path
        and len(_clean(item.content)) >= 20
        and not _DELETED_PROVISION.match(item.content)
        and not _STRUCTURE_MARKER.match(item.content)
    ]
    roots = [item for item in eligible if "/" not in item.path]
    children = [item for item in eligible if "/" in item.path]
    headings = [item for item in eligible if item.heading and _clean(item.heading)]
    by_article: dict[tuple[str, str, str], list[SourceProvision]] = defaultdict(list)
    by_version: dict[tuple[str, str], list[SourceProvision]] = defaultdict(list)
    for item in eligible:
        assert item.article_path is not None
        by_article[(item.document_id, item.version_id, item.article_path)].append(item)
        by_version[(item.document_id, item.version_id)].append(item)
    for values in by_article.values():
        values.sort(key=lambda item: (item.ordinal, item.path))
    article_topics = {
        key: _clean(item.heading or "")
        for key, values in by_article.items()
        for item in values
        if item.path == item.article_path and item.heading and _clean(item.heading)
    }
    semantic = [
        item
        for item in eligible
        if _has_direct_body(item)
        and item.article_path is not None
        and (item.document_id, item.version_id, item.article_path) in article_topics
        and any(
            marker in item.content
            for marker in (
                "받아야",
                "신고하여야",
                "보고하여야",
                "하여야 한다",
                "해서는 아니",
                "하여서는 아니",
                "할 수 없다",
                "할 수 있다",
            )
        )
    ]

    cases: list[dict[str, object]] = []
    questions: set[str] = set()

    def add(case: dict[str, object]) -> bool:
        question = _clean(str(case["user_input"]))
        if question in questions:
            return False
        questions.add(question)
        cases.append(case)
        return True

    def take(category: str, candidates: list[SourceProvision], builder) -> None:
        target = quotas[category]
        accepted = 0
        for item in _stable(candidates, category):
            case_id = f"d2-{category}-{accepted + 1:04d}"
            if add(builder(item, case_id, len(cases))):
                accepted += 1
            if accepted == target:
                return
        raise ValueError(f"not enough unique candidates for {category}: {accepted}/{target}")

    take(
        "exact_path_control",
        roots,
        lambda item, case_id, index: _positive_case(
            case_id=case_id,
            category="exact_path_control",
            question=(
                f"{item.document_title} {_render_path(item.path)}의 "
                "조문 제목과 규정 주제는 무엇인가요?"
            ),
            item=item,
            by_article=by_article,
            index=index,
            template="exact_path",
        ),
    )
    take(
        "heading_lexical_control",
        headings,
        lambda item, case_id, index: _positive_case(
            case_id=case_id,
            category="heading_lexical_control",
            question=(
                f"{item.document_title}에서 '{_clean(item.heading or '')}'은 "
                f"어떤 주제의 조문인가요? ({_render_path(item.path)})"
            ),
            item=item,
            by_article=by_article,
            index=index,
            template="title_heading",
            exact_leaf="/" in item.path,
        ),
    )
    take(
        "semantic_paraphrase",
        semantic,
        lambda item, case_id, index: _positive_case(
            case_id=case_id,
            category="semantic_paraphrase",
            question=_semantic_question(
                item,
                article_topics[(item.document_id, item.version_id, item.article_path)],
            )[0],
            item=item,
            by_article=by_article,
            index=index,
            template=_semantic_question(
                item,
                article_topics[(item.document_id, item.version_id, item.article_path)],
            )[1],
            exact_leaf="/" in item.path,
        ),
    )
    take(
        "hierarchy_child",
        children,
        lambda item, case_id, index: _positive_case(
            case_id=case_id,
            category="hierarchy_child",
            question=(
                f"{item.document_title} {_render_path(item.path)}에서 "
                "직접 정한 내용은 무엇인가요?"
            ),
            item=item,
            by_article=by_article,
            index=index,
            template="exact_hierarchy_path",
            exact_leaf=True,
        ),
    )

    contrast_matches: dict[str, tuple[SourceProvision, float]] = {}
    for item in semantic:
        siblings = [
            other
            for other in by_version[(item.document_id, item.version_id)]
            if other.provision_id != item.provision_id
            and other.article_path != item.article_path
        ]
        if not siblings:
            continue
        sibling = max(
            siblings,
            key=lambda other: difflib.SequenceMatcher(
                None, _clean(item.content), _clean(other.content)
            ).ratio(),
        )
        similarity = difflib.SequenceMatcher(
            None, _clean(item.content), _clean(sibling.content)
        ).ratio()
        if similarity >= 0.30:
            contrast_matches[item.provision_id] = (sibling, similarity)
    contrast_candidates = [
        item for item in semantic if item.provision_id in contrast_matches
    ]

    def contrast(item: SourceProvision, case_id: str, index: int) -> dict[str, object]:
        sibling, distractor_similarity = contrast_matches[item.provision_id]
        question, template = _semantic_question(
            item,
            article_topics[(item.document_id, item.version_id, item.article_path)],
        )
        return _positive_case(
            case_id=case_id,
            category="hard_contrast",
            question=f"{question} 비슷한 인접 규정과 구분해서 알려주세요.",
            item=item,
            by_article=by_article,
            index=index,
            template=f"contrast_{template}",
            exact_leaf="/" in item.path,
            distractor_ids=[sibling.provision_id],
            generation_details={
                "distractor_selection": "highest_sequence_similarity_same_version_other_article",
                "distractor_similarity": round(distractor_similarity, 6),
            },
        )

    take("hard_contrast", contrast_candidates, contrast)

    earliest_roots: list[SourceProvision] = []
    earliest_by_document: dict[str, date] = {}
    for item in roots:
        earliest_by_document[item.document_id] = min(
            earliest_by_document.get(item.document_id, item.effective_from), item.effective_from
        )
    for item in roots:
        if item.effective_from == earliest_by_document[item.document_id]:
            earliest_roots.append(item)
    temporal_target = quotas["temporal_before_effective"]
    temporal_count = 0
    for cycle in range(1, temporal_target + 1):
        item = _stable(earliest_roots, f"temporal:{cycle}")[0]
        question = (
            f"{item.document_title} {_render_path(item.path)}를 "
            f"{(item.effective_from - timedelta(days=cycle)).isoformat()} 기준으로 확인해 주세요."
        )
        case = _negative_case(
            case_id=f"d2-temporal_before_effective-{cycle:04d}",
            category="temporal_before_effective",
            question=question,
            as_of_date=item.effective_from - timedelta(days=cycle),
            index=len(cases),
            reason="before_first_effective_date",
        )
        if add(case):
            temporal_count += 1
    if temporal_count != temporal_target:
        raise ValueError("not enough unique temporal boundary cases")

    documents = sorted(
        {item.document_id: item for item in roots}.values(), key=lambda item: item.document_title
    )
    corpus_titles = {item.document_title for item in documents}
    if corpus_titles.intersection(OUTSIDE_CORPUS_TITLES):
        raise ValueError("outside-corpus title is present in the current corpus")
    outside_target = quotas["outside_corpus"]
    realistic_target = min(outside_target, len(OUTSIDE_CORPUS_TITLES) * len(OUTSIDE_CORPUS_TOPICS))
    outside_index = 0
    for title in OUTSIDE_CORPUS_TITLES:
        for topic in OUTSIDE_CORPUS_TOPICS:
            if outside_index == realistic_target:
                break
            outside_index += 1
            add(
                _negative_case(
                    case_id=f"d2-outside_corpus-{outside_index:04d}",
                    category="outside_corpus",
                    question=f"{title}에서 {topic}에 관해 직접 정한 근거를 찾아주세요.",
                    as_of_date=date(2026, 8, 3),
                    index=len(cases),
                    reason="document_outside_corpus",
                )
            )
    for index in range(outside_target - realistic_target):
        item = documents[index % len(documents)]
        nonexistent = 9000 + index
        outside_index += 1
        add(
            _negative_case(
                case_id=f"d2-outside_corpus-{outside_index:04d}",
                category="outside_corpus",
                question=f"{item.document_title} 제{nonexistent}조의 내용은 무엇인가요?",
                as_of_date=max(item.effective_from, date(2026, 8, 3)),
                index=len(cases),
                reason="nonexistent_article",
            )
        )
    if outside_index != outside_target:
        raise ValueError("outside-corpus boundary count mismatch")

    expected_count = sum(quotas.values())
    if len(cases) != expected_count:
        raise ValueError(f"dataset size mismatch: {len(cases)}/{expected_count}")
    category_counts = Counter(str(case["category"]) for case in cases)
    split_counts = Counter(str(case["split"]) for case in cases)
    review_counts = Counter(str(case["review"]["status"]) for case in cases)  # type: ignore[index]
    corpus_fingerprint = hashlib.sha256(
        "\n".join(
            f"{item.provision_id}:{item.content_sha256}"
            for item in sorted(eligible, key=lambda candidate: candidate.provision_id)
        ).encode()
    ).hexdigest()
    return {
        "schema_version": 2,
        "dataset_version": DATASET_VERSION,
        "method": (
            "BEIR qrels + LlamaIndex-style labelled RAG references "
            "+ deterministic legal boundaries"
        ),
        "corpus": {
            "eligible_provision_count": len(eligible),
            "fingerprint_sha256": corpus_fingerprint,
        },
        "counts": {
            "total": len(cases),
            "categories": dict(sorted(category_counts.items())),
            "splits": dict(sorted(split_counts.items())),
            "review": dict(sorted(review_counts.items())),
        },
        "cases": cases,
    }


def validate_dataset(dataset: dict[str, object], provisions: list[SourceProvision]) -> None:
    cases = dataset.get("cases")
    if not isinstance(cases, list) or len(cases) != 1000:
        raise ValueError("experiment D dataset must contain exactly 1000 cases")
    by_id = {item.provision_id: item for item in provisions}
    ids: set[str] = set()
    questions: set[str] = set()
    for case in cases:
        if not isinstance(case, dict):
            raise ValueError("invalid dataset case")
        case_id = str(case.get("id", ""))
        question = _clean(str(case.get("user_input", "")))
        if not case_id or case_id in ids or not question or question in questions:
            raise ValueError("duplicate or empty case identity")
        ids.add(case_id)
        questions.add(question)
        qrels = case.get("qrels")
        if not isinstance(qrels, list):
            raise ValueError("invalid qrels")
        if case.get("answerable") and not qrels:
            raise ValueError("answerable case has no qrels")
        if not case.get("answerable") and qrels:
            raise ValueError("unanswerable case has qrels")
        for qrel in qrels:
            source = by_id.get(str(qrel.get("provision_id"))) if isinstance(qrel, dict) else None
            if source is None or source.content_sha256 != qrel.get("content_sha256"):
                raise ValueError("qrel source is missing or changed")
        qrel_ids = {
            str(qrel.get("provision_id")) for qrel in qrels if isinstance(qrel, dict)
        }
        distractor_ids = case.get("distractor_provision_ids")
        if not isinstance(distractor_ids, list):
            raise ValueError("invalid distractor ids")
        if any(str(item) not in by_id or str(item) in qrel_ids for item in distractor_ids):
            raise ValueError("distractor is missing or marked relevant")


async def _load_provisions(repository: PostgresLegalRepository) -> list[SourceProvision]:
    async with repository.engine.connect() as connection:
        rows = (
            (
                await connection.execute(
                    text(
                        """SELECT p.id provision_id,p.version_id,d.id document_id,
                        d.exact_title document_title,d.source_kind,v.mst,v.effective_from,
                        v.effective_to,v.source_url,p.path,p.parent_path,p.heading,p.content,p.ordinal
                        FROM provisions p
                        JOIN document_versions v ON v.id=p.version_id
                        JOIN legal_documents d ON d.id=v.document_id
                        ORDER BY d.exact_title,v.effective_from,p.ordinal,p.path"""
                    )
                )
            )
            .mappings()
            .all()
        )
    return [
        SourceProvision(
            provision_id=str(row["provision_id"]),
            version_id=str(row["version_id"]),
            document_id=str(row["document_id"]),
            document_title=row["document_title"],
            source_kind=row["source_kind"],
            mst=row["mst"],
            effective_from=row["effective_from"],
            effective_to=row["effective_to"],
            source_url=row["source_url"],
            path=row["path"],
            parent_path=row["parent_path"],
            heading=row["heading"],
            content=row["content"],
            ordinal=row["ordinal"],
        )
        for row in rows
    ]


def _write_outputs(
    dataset: dict[str, object],
    provisions: list[SourceProvision],
    *,
    dataset_path: Path,
    review_path: Path,
    beir_dir: Path,
) -> None:
    dataset_path.parent.mkdir(parents=True, exist_ok=True)
    dataset_path.write_text(
        json.dumps(dataset, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    cases = dataset["cases"]
    assert isinstance(cases, list)
    review_cases = [
        case
        for case in cases
        if isinstance(case, dict) and case["review"]["status"] == "needs_human_review"
    ]
    lines = [
        "# 실험 D 1,000문항 생성·검토 보고",
        "",
        "> 생성 명령: `uv run --directory apps/api python -m "
        "scripts.generate_experiment_d_dataset`",
        f"> dataset version: `{dataset['dataset_version']}`",
        "",
        "## 구성",
        "",
        f"- 전체: {dataset['counts']['total']}개",
        f"- calibration/test: {dataset['counts']['splits']}",
        f"- 범주: {dataset['counts']['categories']}",
        f"- 사람 검토 필요: {len(review_cases)}개",
        "",
        "## 사람이 직접 확인할 문항",
        "",
        "아래 문항은 표제 누락, 너무 짧거나 긴 근거, 일반화된 의미 템플릿, "
        "교차참조 중심 본문 중 하나에 해당한다.",
        "",
        "| ID | 질문 | 기준 답 일부 | 이유 |",
        "|---|---|---|---|",
    ]
    for case in review_cases:
        answer = str(case["reference"]).replace("|", "\\|")[:180]
        question = str(case["user_input"]).replace("|", "\\|")
        reasons = ", ".join(case["review"]["reasons"])
        lines.append(f"| {case['id']} | {question} | {answer} | {reasons} |")
    review_path.parent.mkdir(parents=True, exist_ok=True)
    review_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    beir_dir.mkdir(parents=True, exist_ok=True)
    corpus_lines = [
        json.dumps(
            {
                "_id": item.provision_id,
                "title": f"{item.document_title} {item.path}",
                "text": item.content,
                "metadata": {
                    "version_id": item.version_id,
                    "document_id": item.document_id,
                    "content_sha256": item.content_sha256,
                },
            },
            ensure_ascii=False,
        )
        for item in provisions
    ]
    (beir_dir / "corpus.jsonl").write_text("\n".join(corpus_lines) + "\n", encoding="utf-8")
    query_lines = [
        json.dumps({"_id": case["id"], "text": case["user_input"]}, ensure_ascii=False)
        for case in cases
    ]
    (beir_dir / "queries.jsonl").write_text("\n".join(query_lines) + "\n", encoding="utf-8")
    for split in ("calibration", "test"):
        qrels = ["query-id\tcorpus-id\tscore"]
        for case in cases:
            if case["split"] != split:
                continue
            qrels.extend(
                f"{case['id']}\t{qrel['provision_id']}\t{qrel['relevance']}"
                for qrel in case["qrels"]
            )
        (beir_dir / f"qrels-{split}.tsv").write_text("\n".join(qrels) + "\n", encoding="utf-8")


async def _run(arguments: argparse.Namespace) -> dict[str, Any]:
    settings = get_settings()
    if not settings.database_url:
        raise SystemExit("DATABASE_URL이 필요합니다.")
    repository = PostgresLegalRepository(settings.database_url)
    try:
        provisions = await _load_provisions(repository)
    finally:
        await repository.engine.dispose()
    dataset = build_dataset(provisions)
    validate_dataset(dataset, provisions)
    _write_outputs(
        dataset,
        provisions,
        dataset_path=arguments.dataset,
        review_path=arguments.review,
        beir_dir=arguments.beir_dir,
    )
    return {
        "dataset": str(arguments.dataset),
        "review": str(arguments.review),
        "beir_dir": str(arguments.beir_dir),
        "counts": dataset["counts"],
        "corpus": dataset["corpus"],
    }


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    print(json.dumps(asyncio.run(_run(_arguments())), ensure_ascii=False, indent=2))
