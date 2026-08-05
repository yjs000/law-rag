"""Offline parent-heading and directness rerank for one confirmed D-10 run."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
from collections.abc import Mapping, Sequence
from contextlib import suppress
from pathlib import Path
from uuid import uuid4

from pydantic import ValidationError

from scripts.experiment_d_manual_review_results import (
    ExperimentD10ManualReview,
    ManualReviewResultError,
    _final_judgment,
    _validate_judgment_references,
    _validated_result,
)

REPOSITORY_ROOT = Path(__file__).parents[3]
PROFILE_KEY = "d10-parent-heading-directness-v1"
TARGET_CASE_ID = "lay-energy-0346"
WEIGHTS = {
    "dense_position": 0.35,
    "candidate_concept_coverage": 0.30,
    "parent_heading_concept_coverage": 0.25,
    "relation_completion": 0.10,
}
CONCEPT_GROUPS: dict[str, tuple[str, ...]] = {
    "permit": ("허가", "인가", "승인", "면허"),
    "report": ("신고", "신청", "제출"),
    "capacity_use": (
        "용량",
        "자가용",
        "자가소비",
        "사용 방식",
        "잉여전력",
        "전력거래",
        "전기 판매",
    ),
    "certificate": ("공급인증서", "REC"),
    "issuance": ("발급", "신청 조건", "공급량", "공급기간"),
    "support": ("지원", "보조", "융자", "재정"),
    "eligibility": ("지원 대상", "조건", "범위", "절차", "선정"),
    "site": ("장소", "토지", "땅", "산지", "농지", "입지", "용도지역"),
    "installation": ("설치", "발전소", "발전사업", "개발행위"),
    "network": ("전력망", "전력계통", "계통 연계", "연계", "접속", "송전", "배전"),
    "cost": ("공사비", "비용", "부담", "산정", "계산"),
    "settlement": ("정산", "정산금", "거래가격", "계약가격", "차액계약"),
    "measurement": ("발전량", "공급량", "전력량", "계량", "공제액", "명세"),
    "charger": ("충전기", "충전시설", "충전사업"),
    "outage": ("고장", "장애", "복구", "가동 상태", "점검", "보수"),
    "glare": ("빛 반사", "반사", "눈부심"),
    "complaint": ("민원", "시정 조치", "불편", "조치 요청"),
}


class LocalRerankError(ValueError):
    """Raised when the offline rerank contract cannot be completed."""


def _sha256(encoded: bytes) -> str:
    return hashlib.sha256(encoded).hexdigest()


def _canonical_json_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _normalized(text: str) -> str:
    return "".join(character.lower() for character in text if character.isalnum())


def _matched_terms(text: str, terms: Sequence[str]) -> list[str]:
    normalized_text = _normalized(text)
    return [term for term in terms if _normalized(term) in normalized_text]


def _active_concepts(question: str) -> list[str]:
    return [
        concept
        for concept, terms in CONCEPT_GROUPS.items()
        if _matched_terms(question, terms)
    ]


def _profile_payload() -> dict[str, object]:
    return {
        "profile_key": PROFILE_KEY,
        "weights": WEIGHTS,
        "concept_groups": CONCEPT_GROUPS,
        "candidate_text": "document_title + parent_article_heading + raw_content",
        "labels_used_for_scoring": False,
    }


def _profile_sha256() -> str:
    return _sha256(_canonical_json_bytes(_profile_payload()))


def _article_path(path: str) -> str:
    return path.split("/", 1)[0]


def _parent_headings(case: Mapping[str, object]) -> dict[tuple[str, str, str], str]:
    contexts = case.get("article_contexts")
    if not isinstance(contexts, list):
        raise LocalRerankError("D-10 case article contexts are missing")
    headings: dict[tuple[str, str, str], str] = {}
    for context in contexts:
        if not isinstance(context, dict):
            raise LocalRerankError("D-10 article context is invalid")
        document_id = context.get("document_id")
        version_id = context.get("version_id")
        article_path = context.get("article_path")
        provisions = context.get("provisions")
        identity = (document_id, version_id, article_path)
        if not all(isinstance(item, str) and item for item in identity):
            raise LocalRerankError("D-10 article context identity is invalid")
        if not isinstance(provisions, list):
            raise LocalRerankError("D-10 article context provisions are invalid")
        root = next(
            (
                provision
                for provision in provisions
                if isinstance(provision, dict) and provision.get("path") == article_path
            ),
            None,
        )
        if root is None:
            raise LocalRerankError("D-10 parent article root is missing")
        heading = root.get("heading")
        headings[(document_id, version_id, article_path)] = (
            str(heading).strip() if heading is not None else ""
        )
    return headings


def _concept_matches(text: str, active_concepts: Sequence[str]) -> dict[str, list[str]]:
    return {
        concept: matches
        for concept in active_concepts
        if (matches := _matched_terms(text, CONCEPT_GROUPS[concept]))
    }


def rerank_case(case: Mapping[str, object]) -> dict[str, object]:
    """Rerank one case without accepting or reading relevance labels."""

    question = case.get("question")
    candidates = case.get("raw_candidates")
    if not isinstance(question, str) or not question.strip():
        raise LocalRerankError("D-10 question is missing")
    if not isinstance(candidates, list) or len(candidates) != 10:
        raise LocalRerankError("D-10 rerank requires exactly 10 raw candidates")
    typed = [candidate for candidate in candidates if isinstance(candidate, dict)]
    if len(typed) != 10:
        raise LocalRerankError("D-10 raw candidate is invalid")
    scores = [float(candidate["raw_cosine_similarity"]) for candidate in typed]
    minimum = min(scores)
    maximum = max(scores)
    headings = _parent_headings(case)
    active = _active_concepts(question)
    records: list[dict[str, object]] = []
    for candidate in typed:
        raw_rank = int(candidate["rank"])
        raw_score = float(candidate["raw_cosine_similarity"])
        if maximum == minimum:
            dense_position = 1.0 - (raw_rank - 1) / 9
        else:
            dense_position = (raw_score - minimum) / (maximum - minimum)
        key = (
            str(candidate["document_id"]),
            str(candidate["version_id"]),
            _article_path(str(candidate["path"])),
        )
        if key not in headings:
            raise LocalRerankError("raw candidate has no restored parent article")
        parent_heading = headings[key]
        candidate_text = "\n".join(
            (
                str(candidate["document_title"]),
                parent_heading,
                str(candidate["content"]),
            )
        )
        candidate_matches = _concept_matches(candidate_text, active)
        heading_matches = _concept_matches(parent_heading, active)
        active_count = len(active)
        candidate_coverage = len(candidate_matches) / active_count if active_count else 0.0
        heading_coverage = len(heading_matches) / active_count if active_count else 0.0
        relation_completion = float(active_count >= 2 and len(candidate_matches) == active_count)
        if active_count:
            rerank_score = (
                WEIGHTS["dense_position"] * dense_position
                + WEIGHTS["candidate_concept_coverage"] * candidate_coverage
                + WEIGHTS["parent_heading_concept_coverage"] * heading_coverage
                + WEIGHTS["relation_completion"] * relation_completion
            )
        else:
            rerank_score = dense_position
        records.append(
            {
                "provision_id": candidate["provision_id"],
                "raw_rank": raw_rank,
                "raw_cosine_similarity": raw_score,
                "parent_article_path": key[2],
                "parent_article_heading": parent_heading,
                "active_concept_matches": candidate_matches,
                "parent_heading_concept_matches": heading_matches,
                "score_components": {
                    "dense_position": dense_position,
                    "candidate_concept_coverage": candidate_coverage,
                    "parent_heading_concept_coverage": heading_coverage,
                    "relation_completion": relation_completion,
                },
                "rerank_score": rerank_score,
            }
        )
    records.sort(
        key=lambda record: (
            -float(record["rerank_score"]),
            int(record["raw_rank"]),
            str(record["provision_id"]),
        )
    )
    for rerank_rank, record in enumerate(records, 1):
        record["rerank_rank"] = rerank_rank
    return {
        "case_id": case["case_id"],
        "question": question,
        "active_concepts": active,
        "candidates": records,
    }


def _read_json(path: Path, *, label: str) -> tuple[dict[str, object], bytes]:
    try:
        encoded = path.read_bytes()
        payload = json.loads(encoded)
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise LocalRerankError(f"could not read {label}: {path}") from error
    if not isinstance(payload, dict):
        raise LocalRerankError(f"{label} must be a JSON object")
    return payload, encoded


def _confirmed_inputs(
    result_path: Path,
    review_path: Path,
    diagnostics_path: Path,
) -> tuple[dict[str, object], ExperimentD10ManualReview, dict[str, object], dict[str, str]]:
    try:
        result, result_file_sha256 = _validated_result(result_path)
    except ManualReviewResultError as error:
        raise LocalRerankError(str(error)) from error
    raw_review, review_bytes = _read_json(review_path, label="D-10 manual review")
    try:
        review = ExperimentD10ManualReview.model_validate(raw_review)
    except ValidationError as error:
        raise LocalRerankError("D-10 manual review contract is invalid") from error
    if review.status != "confirmed":
        raise LocalRerankError("D-10 manual review is not confirmed")
    inputs = result["inputs"]
    assert isinstance(inputs, dict)
    expected_binding = {
        "run_id": result["run_id"],
        "result_file_sha256": result_file_sha256,
        "corpus_snapshot_id": inputs["corpus_snapshot_id"],
        "embedding_profile_key": inputs["embedding_profile_key"],
    }
    if review.run_binding.model_dump(mode="json") != expected_binding:
        raise LocalRerankError("D-10 review run binding mismatch")
    diagnostics, diagnostics_bytes = _read_json(
        diagnostics_path,
        label="D-10 confirmed diagnostics",
    )
    recorded_sha = diagnostics.get("payload_without_self_hash_sha256")
    without_self_hash = {
        key: value
        for key, value in diagnostics.items()
        if key != "payload_without_self_hash_sha256"
    }
    if recorded_sha != _sha256(_canonical_json_bytes(without_self_hash)):
        raise LocalRerankError("D-10 confirmed diagnostics payload SHA-256 mismatch")
    if diagnostics.get("status") != "completed":
        raise LocalRerankError("D-10 confirmed diagnostics are incomplete")
    if diagnostics.get("run_binding") != expected_binding:
        raise LocalRerankError("D-10 diagnostics run binding mismatch")
    if diagnostics.get("review_file_sha256") != _sha256(review_bytes):
        raise LocalRerankError("D-10 diagnostics review SHA-256 mismatch")
    hashes = {
        "result_file_sha256": result_file_sha256,
        "review_file_sha256": _sha256(review_bytes),
        "diagnostics_file_sha256": _sha256(diagnostics_bytes),
    }
    return result, review, diagnostics, hashes


def _first_rank(candidate_ids: Sequence[str], direct_ids: set[str]) -> int | None:
    return next(
        (rank for rank, candidate_id in enumerate(candidate_ids, 1) if candidate_id in direct_ids),
        None,
    )


def _hit_counts(first_ranks: Mapping[str, int | None]) -> dict[str, int]:
    return {
        str(cutoff): sum(rank is not None and rank <= cutoff for rank in first_ranks.values())
        for cutoff in (1, 3, 5, 10)
    }


def build_comparison(
    result: Mapping[str, object],
    review: ExperimentD10ManualReview,
    diagnostics: Mapping[str, object],
    hashes: Mapping[str, str],
) -> dict[str, object]:
    cases = result.get("cases")
    if not isinstance(cases, list) or len(cases) != 10:
        raise LocalRerankError("D-10 result must contain exactly 10 cases")
    result_by_id = {
        str(case["case_id"]): case for case in cases if isinstance(case, dict)
    }
    if list(result_by_id) != [case.case_id for case in review.cases]:
        raise LocalRerankError("D-10 result and review case order mismatch")
    before_first: dict[str, int | None] = {}
    after_first: dict[str, int | None] = {}
    before_irrelevant: dict[str, int] = {}
    after_known_irrelevant: dict[str, int] = {}
    comparison_cases: list[dict[str, object]] = []
    for review_case in review.cases:
        result_case = result_by_id[review_case.case_id]
        raw_candidates = result_case.get("raw_candidates")
        if not isinstance(raw_candidates, list):
            raise LocalRerankError("D-10 raw candidates are missing")
        typed_candidates = [item for item in raw_candidates if isinstance(item, dict)]
        judgment = _final_judgment(review_case)
        _validate_judgment_references(
            judgment,
            case_id=review_case.case_id,
            raw_candidates=typed_candidates,
        )
        reranked = rerank_case(result_case)
        records = reranked["candidates"]
        assert isinstance(records, list)
        raw_ids = [str(candidate["provision_id"]) for candidate in typed_candidates]
        reranked_ids = [str(candidate["provision_id"]) for candidate in records]
        if set(raw_ids) != set(reranked_ids) or len(reranked_ids) != 10:
            raise LocalRerankError("rerank changed the D-10 candidate set")
        direct_ids = set(judgment.direct_evidence_provision_ids)
        irrelevant_ids = set(judgment.irrelevant_top5_provision_ids)
        raw_first = _first_rank(raw_ids, direct_ids)
        reranked_first = _first_rank(reranked_ids, direct_ids)
        before_first[review_case.case_id] = raw_first
        after_first[review_case.case_id] = reranked_first
        before_count = sum(candidate_id in irrelevant_ids for candidate_id in raw_ids[:5])
        after_count = sum(candidate_id in irrelevant_ids for candidate_id in reranked_ids[:5])
        before_irrelevant[review_case.case_id] = before_count
        after_known_irrelevant[review_case.case_id] = after_count
        new_top5_ids = [
            candidate_id
            for candidate_id in reranked_ids[:5]
            if candidate_id not in raw_ids[:5]
        ]
        comparison_cases.append(
            {
                "case_id": review_case.case_id,
                "active_concepts": reranked["active_concepts"],
                "raw_first_direct_evidence_rank": raw_first,
                "reranked_first_direct_evidence_rank": reranked_first,
                "raw_confirmed_irrelevant_at_5": before_count,
                "reranked_confirmed_known_irrelevant_at_5": after_count,
                "new_unjudged_top5_provision_ids": [
                    candidate_id
                    for candidate_id in new_top5_ids
                    if candidate_id not in direct_ids and candidate_id not in irrelevant_ids
                ],
                "reranked_candidates": records,
            }
        )
    target = next(
        (case for case in comparison_cases if case["case_id"] == TARGET_CASE_ID),
        None,
    )
    if target is None:
        raise LocalRerankError(f"target case is missing: {TARGET_CASE_ID}")
    payload: dict[str, object] = {
        "schema_version": 1,
        "experiment": "D-10-R1",
        "artifact_class": "calibration_local_rerank_not_gold",
        "status": "completed",
        "input_binding": {
            "run_id": result["run_id"],
            "corpus_snapshot_id": review.run_binding.corpus_snapshot_id,
            "embedding_profile_key": review.run_binding.embedding_profile_key,
            **hashes,
        },
        "scoring_profile": _profile_payload(),
        "scoring_profile_sha256": _profile_sha256(),
        "invariants": {
            "case_count": len(comparison_cases),
            "candidate_count_per_case": 10,
            "candidate_sets_preserved": True,
            "raw_cosine_and_rank_preserved": True,
            "external_calls": 0,
            "relevance_labels_used_for_scoring": False,
        },
        "metrics": {
            "manual_direct_evidence_hit_counts_before": _hit_counts(before_first),
            "manual_direct_evidence_hit_counts_after": _hit_counts(after_first),
            "confirmed_irrelevant_at_5_before": {
                "total": sum(before_irrelevant.values()),
                "by_case": before_irrelevant,
            },
            "confirmed_known_irrelevant_at_5_after": {
                "total": sum(after_known_irrelevant.values()),
                "by_case": after_known_irrelevant,
            },
        },
        "target_case": {
            "case_id": TARGET_CASE_ID,
            "raw_first_direct_evidence_rank": target["raw_first_direct_evidence_rank"],
            "reranked_first_direct_evidence_rank": target[
                "reranked_first_direct_evidence_rank"
            ],
            "direct_evidence_reached_top3": (
                target["reranked_first_direct_evidence_rank"] is not None
                and int(target["reranked_first_direct_evidence_rank"]) <= 3
            ),
            "raw_confirmed_irrelevant_at_5": target["raw_confirmed_irrelevant_at_5"],
            "reranked_confirmed_known_irrelevant_at_5": target[
                "reranked_confirmed_known_irrelevant_at_5"
            ],
            "confirmed_known_irrelevant_at_5_decreased": (
                int(target["reranked_confirmed_known_irrelevant_at_5"])
                < int(target["raw_confirmed_irrelevant_at_5"])
            ),
        },
        "cases": comparison_cases,
        "baseline_diagnostic_payload_sha256": diagnostics[
            "payload_without_self_hash_sha256"
        ],
        "warning": (
            "Same-sample calibration diagnostic only. New top-5 candidates from original "
            "ranks 6-10 remain unjudged unless they were confirmed direct evidence."
        ),
        "reranker_code_file_sha256": _sha256(Path(__file__).read_bytes()),
    }
    payload["payload_without_self_hash_sha256"] = _sha256(_canonical_json_bytes(payload))
    return payload


def _markdown(payload: Mapping[str, object]) -> str:
    metrics = payload["metrics"]
    target = payload["target_case"]
    assert isinstance(metrics, dict)
    assert isinstance(target, dict)
    before_hits = metrics["manual_direct_evidence_hit_counts_before"]
    after_hits = metrics["manual_direct_evidence_hit_counts_after"]
    before_irrelevant = metrics["confirmed_irrelevant_at_5_before"]
    after_irrelevant = metrics["confirmed_known_irrelevant_at_5_after"]
    assert isinstance(before_hits, dict)
    assert isinstance(after_hits, dict)
    assert isinstance(before_irrelevant, dict)
    assert isinstance(after_irrelevant, dict)
    lines = [
        "# 실험 D-10-R1 로컬 재정렬 비교",
        "",
        f"- 원본 run: `{payload['input_binding']['run_id']}`",
        f"- profile: `{payload['scoring_profile_sha256']}`",
        "- 외부 호출: `0`",
        "- 성격: 같은 10문항 calibration 진단, 정식 gold 아님",
        "",
        "## 전체 비교",
        "",
        "| 값 | 전 | 후 |",
        "|---|---:|---:|",
    ]
    for cutoff in (1, 3, 5, 10):
        key = str(cutoff)
        lines.append(f"| 직접 근거 hit@{cutoff} | {before_hits[key]}/10 | {after_hits[key]}/10 |")
    lines.append(
        "| confirmed known irrelevant@5 | "
        f"{before_irrelevant['total']} | {after_irrelevant['total']} |"
    )
    lines.extend(
        [
            "",
            f"## {TARGET_CASE_ID}",
            "",
            f"- 첫 직접 근거: {target['raw_first_direct_evidence_rank']}위 → "
            f"{target['reranked_first_direct_evidence_rank']}위",
            f"- top 3 달성: `{str(target['direct_evidence_reached_top3']).lower()}`",
            "- confirmed known irrelevant@5: "
            f"{target['raw_confirmed_irrelevant_at_5']} → "
            f"{target['reranked_confirmed_known_irrelevant_at_5']}",
            "",
            "## 문항별 변화",
            "",
            "| ID | 첫 직접 근거 전→후 | known irrelevant@5 전→후 | 새 미판정 top5 |",
            "|---|---:|---:|---:|",
        ]
    )
    cases = payload["cases"]
    assert isinstance(cases, list)
    for case in cases:
        assert isinstance(case, dict)
        lines.append(
            f"| {case['case_id']} | {case['raw_first_direct_evidence_rank']}→"
            f"{case['reranked_first_direct_evidence_rank']} | "
            f"{case['raw_confirmed_irrelevant_at_5']}→"
            f"{case['reranked_confirmed_known_irrelevant_at_5']} | "
            f"{len(case['new_unjudged_top5_provision_ids'])} |"
        )
    lines.extend(
        [
            "",
            "> 주의: 원래 검토는 raw top 5만 무관 후보를 의무 판정했다. 과거 6~10위에서 새 top 5로",
            "> 들어온 미판정 후보는 관련으로 간주하지 않으며 목록을 JSON에 별도로 남겼다.",
            "",
        ]
    )
    return "\n".join(lines)


def _atomic_publish(output_dir: Path, payload: Mapping[str, object]) -> tuple[Path, Path]:
    if output_dir.exists():
        raise LocalRerankError(f"rerank output already exists: {output_dir}")
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    temporary = output_dir.parent / f".{output_dir.name}.{uuid4().hex}.tmp"
    temporary.mkdir()
    json_path = temporary / "comparison.json"
    markdown_path = temporary / "comparison.md"
    try:
        json_encoded = (
            json.dumps(payload, ensure_ascii=False, allow_nan=False, indent=2, sort_keys=True)
            + "\n"
        ).encode("utf-8")
        markdown_encoded = _markdown(payload).encode("utf-8")
        for path, encoded in (
            (json_path, json_encoded),
            (markdown_path, markdown_encoded),
        ):
            with path.open("xb") as stream:
                stream.write(encoded)
                stream.flush()
                os.fsync(stream.fileno())
        temporary.replace(output_dir)
    except OSError as error:
        raise LocalRerankError("could not atomically publish rerank output") from error
    finally:
        with suppress(OSError):
            shutil.rmtree(temporary)
    return output_dir / "comparison.json", output_dir / "comparison.md"


def run_local_rerank(
    result_path: Path,
    review_path: Path,
    diagnostics_path: Path,
    output_dir: Path,
) -> tuple[dict[str, object], Path, Path]:
    result, review, diagnostics, hashes = _confirmed_inputs(
        result_path,
        review_path,
        diagnostics_path,
    )
    payload = build_comparison(result, review, diagnostics, hashes)
    json_path, markdown_path = _atomic_publish(output_dir, payload)
    return payload, json_path, markdown_path


def _cli_path(path: Path) -> Path:
    return path if path.is_absolute() else REPOSITORY_ROOT / path


def _arguments(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Offline D-10 parent-heading rerank")
    parser.add_argument("--result", type=Path, required=True)
    parser.add_argument("--review", type=Path)
    parser.add_argument("--diagnostics", type=Path)
    parser.add_argument("--output-dir", type=Path)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    arguments = _arguments(argv)
    result_path = _cli_path(arguments.result)
    review_path = (
        _cli_path(arguments.review)
        if arguments.review
        else result_path.parent / "manual-review.json"
    )
    diagnostics_path = (
        _cli_path(arguments.diagnostics)
        if arguments.diagnostics
        else result_path.parent / "confirmed-diagnostics.json"
    )
    output_dir = (
        _cli_path(arguments.output_dir)
        if arguments.output_dir
        else result_path.parent / "rerank" / PROFILE_KEY
    )
    try:
        payload, json_path, markdown_path = run_local_rerank(
            result_path,
            review_path,
            diagnostics_path,
            output_dir,
        )
    except LocalRerankError as error:
        print(
            json.dumps(
                {
                    "status": "failed",
                    "error_code": "d10_local_rerank_failed",
                    "message": str(error),
                    "result_written": False,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 2
    print(
        json.dumps(
            {
                "status": payload["status"],
                "experiment": payload["experiment"],
                "comparison_json": str(json_path.resolve()),
                "comparison_markdown": str(markdown_path.resolve()),
                "target_case": payload["target_case"],
                "metrics": payload["metrics"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["LocalRerankError", "build_comparison", "rerank_case", "run_local_rerank"]
