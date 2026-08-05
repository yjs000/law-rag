"""Create and finalize human review artifacts for one Experiment D-10 run."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from collections import Counter
from collections.abc import Mapping, Sequence
from contextlib import suppress
from pathlib import Path
from typing import Annotated, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, ValidationError

REPOSITORY_ROOT = Path(__file__).parents[3]
Sha256 = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]
NonBlankStr = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
Verdict = Literal[
    "directly_answerable",
    "partially_answerable",
    "clarification_required",
    "not_answerable_from_current_corpus",
]
ContextVerdict = Literal["sufficient", "insufficient", "blocked"]


class ManualReviewResultError(ValueError):
    """Raised when a review cannot be bound or finalized safely."""


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class RunBinding(StrictModel):
    run_id: NonBlankStr
    result_file_sha256: Sha256
    corpus_snapshot_id: NonBlankStr
    embedding_profile_key: NonBlankStr


class CompletedJudgment(StrictModel):
    direct_evidence_provision_ids: list[NonBlankStr]
    irrelevant_top5_provision_ids: list[NonBlankStr]
    verdict: Verdict
    reason: NonBlankStr
    supported_answer_elements: list[NonBlankStr]
    missing_answer_elements: list[NonBlankStr]
    context_verdict: ContextVerdict


class UserConfirmation(StrictModel):
    status: Literal["approved", "modified", "on_hold"]
    notes: str = ""
    override: CompletedJudgment | None = None


class ManualReviewCase(StrictModel):
    case_id: NonBlankStr
    assistant_review: CompletedJudgment | None
    user_confirmation: UserConfirmation


class ExperimentD10ManualReview(StrictModel):
    schema_version: Literal[1]
    experiment: Literal["D-10"]
    artifact_class: Literal["manual_review"]
    status: Literal["in_review", "confirmed"]
    run_binding: RunBinding
    cases: list[ManualReviewCase] = Field(min_length=10, max_length=10)


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


def _read_json_object(path: Path, *, label: str) -> tuple[dict[str, object], bytes]:
    try:
        encoded = path.read_bytes()
        value = json.loads(encoded.decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ManualReviewResultError(f"could not read {label}: {path}") from error
    if not isinstance(value, dict):
        raise ManualReviewResultError(f"{label} root must be an object")
    return value, encoded


def _validated_result(path: Path) -> tuple[dict[str, object], str]:
    result, encoded = _read_json_object(path, label="D-10 result")
    if (
        result.get("schema_version") != 1
        or result.get("experiment") != "D-10"
        or result.get("artifact_class") != "not_gold"
        or result.get("status") != "retrieval_completed_awaiting_manual_review"
        or result.get("case_count") != 10
    ):
        raise ManualReviewResultError("D-10 result contract mismatch")
    cases = result.get("cases")
    inputs = result.get("inputs")
    if not isinstance(cases, list) or len(cases) != 10 or not isinstance(inputs, dict):
        raise ManualReviewResultError("D-10 result cases or inputs are invalid")
    case_ids: list[str] = []
    for case in cases:
        if not isinstance(case, dict) or not isinstance(case.get("case_id"), str):
            raise ManualReviewResultError("D-10 result case is invalid")
        raw_candidates = case.get("raw_candidates")
        if not isinstance(raw_candidates, list) or len(raw_candidates) != 10:
            raise ManualReviewResultError("D-10 result must contain raw top 10 per case")
        expected_ranks = list(range(1, 11))
        actual_ranks = [
            candidate.get("rank")
            for candidate in raw_candidates
            if isinstance(candidate, dict)
        ]
        if len(actual_ranks) != 10 or actual_ranks != expected_ranks:
            raise ManualReviewResultError("D-10 raw candidate ranks are invalid")
        provision_ids = [
            candidate.get("provision_id")
            for candidate in raw_candidates
            if isinstance(candidate, dict)
        ]
        if any(not isinstance(item, str) or not item for item in provision_ids):
            raise ManualReviewResultError("D-10 raw candidate provision IDs are invalid")
        if len(set(provision_ids)) != 10:
            raise ManualReviewResultError("D-10 raw candidate provision IDs are duplicated")
        case_ids.append(case["case_id"])
    if len(set(case_ids)) != 10:
        raise ManualReviewResultError("D-10 result case IDs are duplicated")

    recorded_payload_sha = result.get("payload_without_self_hash_sha256")
    without_self_hash = {
        key: value for key, value in result.items() if key != "payload_without_self_hash_sha256"
    }
    if recorded_payload_sha != _sha256(_canonical_json_bytes(without_self_hash)):
        raise ManualReviewResultError("D-10 result payload SHA-256 mismatch")
    required_inputs = (
        "corpus_snapshot_id",
        "embedding_profile_key",
    )
    if any(not isinstance(inputs.get(key), str) or not inputs[key] for key in required_inputs):
        raise ManualReviewResultError("D-10 result binding inputs are invalid")
    return result, _sha256(encoded)


def _atomic_create_json(path: Path, payload: Mapping[str, object]) -> str:
    encoded = (
        json.dumps(payload, ensure_ascii=False, allow_nan=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.parent / f".{path.name}.{uuid4().hex}.tmp"
    try:
        with temporary.open("xb") as stream:
            stream.write(encoded)
            stream.flush()
            os.fsync(stream.fileno())
        try:
            os.link(temporary, path)
        except FileExistsError as error:
            raise ManualReviewResultError(f"output already exists: {path}") from error
    finally:
        with suppress(OSError):
            temporary.unlink(missing_ok=True)
    return _sha256(encoded)


def create_review_template(result_path: Path, output_path: Path) -> tuple[dict[str, object], str]:
    result, result_file_sha256 = _validated_result(result_path)
    inputs = result["inputs"]
    cases = result["cases"]
    assert isinstance(inputs, dict)
    assert isinstance(cases, list)
    payload: dict[str, object] = {
        "schema_version": 1,
        "experiment": "D-10",
        "artifact_class": "manual_review",
        "status": "in_review",
        "run_binding": {
            "run_id": result["run_id"],
            "result_file_sha256": result_file_sha256,
            "corpus_snapshot_id": inputs["corpus_snapshot_id"],
            "embedding_profile_key": inputs["embedding_profile_key"],
        },
        "cases": [
            {
                "case_id": case["case_id"],
                "assistant_review": None,
                "user_confirmation": {
                    "status": "on_hold",
                    "notes": "",
                    "override": None,
                },
            }
            for case in cases
            if isinstance(case, dict)
        ],
    }
    ExperimentD10ManualReview.model_validate(payload)
    return payload, _atomic_create_json(output_path, payload)


def _final_judgment(review_case: ManualReviewCase) -> CompletedJudgment:
    assistant = review_case.assistant_review
    confirmation = review_case.user_confirmation
    if assistant is None:
        raise ManualReviewResultError(f"assistant review is incomplete: {review_case.case_id}")
    if confirmation.status == "on_hold":
        raise ManualReviewResultError(f"user confirmation is on hold: {review_case.case_id}")
    if confirmation.status == "approved":
        if confirmation.override is not None:
            raise ManualReviewResultError(
                f"approved review must not contain an override: {review_case.case_id}"
            )
        return assistant
    if confirmation.override is None:
        raise ManualReviewResultError(
            f"modified review requires an override: {review_case.case_id}"
        )
    return confirmation.override


def _validate_judgment_references(
    judgment: CompletedJudgment,
    *,
    case_id: str,
    raw_candidates: Sequence[Mapping[str, object]],
) -> None:
    raw_ids = [str(candidate["provision_id"]) for candidate in raw_candidates]
    top5_ids = set(raw_ids[:5])
    direct_ids = judgment.direct_evidence_provision_ids
    irrelevant_ids = judgment.irrelevant_top5_provision_ids
    if len(set(direct_ids)) != len(direct_ids):
        raise ManualReviewResultError(f"direct evidence IDs are duplicated: {case_id}")
    if len(set(irrelevant_ids)) != len(irrelevant_ids):
        raise ManualReviewResultError(f"irrelevant top-5 IDs are duplicated: {case_id}")
    if not set(direct_ids).issubset(raw_ids):
        raise ManualReviewResultError(f"direct evidence is outside raw top 10: {case_id}")
    if not set(irrelevant_ids).issubset(top5_ids):
        raise ManualReviewResultError(f"irrelevant evidence is outside raw top 5: {case_id}")
    if set(direct_ids) & set(irrelevant_ids):
        raise ManualReviewResultError(f"candidate cannot be direct and irrelevant: {case_id}")
    if judgment.verdict == "not_answerable_from_current_corpus" and direct_ids:
        raise ManualReviewResultError(
            f"not-answerable verdict cannot contain direct evidence: {case_id}"
        )


def _ratio(numerator: int, denominator: int) -> float:
    return numerator / denominator if denominator else 0.0


def finalize_confirmed_review(
    result_path: Path,
    review_path: Path,
    output_path: Path,
) -> tuple[dict[str, object], str]:
    result, result_file_sha256 = _validated_result(result_path)
    raw_review, review_bytes = _read_json_object(review_path, label="D-10 manual review")
    try:
        review = ExperimentD10ManualReview.model_validate(raw_review)
    except ValidationError as error:
        raise ManualReviewResultError("D-10 manual review contract is invalid") from error
    if review.status != "confirmed":
        raise ManualReviewResultError("D-10 manual review is not confirmed")
    inputs = result["inputs"]
    cases = result["cases"]
    assert isinstance(inputs, dict)
    assert isinstance(cases, list)
    expected_binding = {
        "run_id": result["run_id"],
        "result_file_sha256": result_file_sha256,
        "corpus_snapshot_id": inputs["corpus_snapshot_id"],
        "embedding_profile_key": inputs["embedding_profile_key"],
    }
    if review.run_binding.model_dump(mode="json") != expected_binding:
        raise ManualReviewResultError("D-10 review run binding mismatch")
    result_by_id = {
        str(case["case_id"]): case for case in cases if isinstance(case, dict)
    }
    review_ids = [case.case_id for case in review.cases]
    if review_ids != list(result_by_id):
        raise ManualReviewResultError("D-10 review cases do not match result order")

    cutoffs = (1, 3, 5, 10)
    hit_counts = {cutoff: 0 for cutoff in cutoffs}
    first_rank_by_case: dict[str, int | None] = {}
    irrelevant_by_case: dict[str, int] = {}
    context_counts: Counter[str] = Counter()
    assistant_final_agreement_count = 0
    boundary_case_count = 0
    assistant_correct_boundary_count = 0
    confirmed_cases: list[dict[str, object]] = []
    for review_case in review.cases:
        result_case = result_by_id[review_case.case_id]
        raw_candidates = result_case["raw_candidates"]
        assert isinstance(raw_candidates, list)
        typed_candidates = [
            candidate for candidate in raw_candidates if isinstance(candidate, dict)
        ]
        assistant = review_case.assistant_review
        final = _final_judgment(review_case)
        assert assistant is not None
        _validate_judgment_references(
            assistant,
            case_id=review_case.case_id,
            raw_candidates=typed_candidates,
        )
        _validate_judgment_references(
            final,
            case_id=review_case.case_id,
            raw_candidates=typed_candidates,
        )
        rank_by_id = {
            str(candidate["provision_id"]): int(candidate["rank"])
            for candidate in typed_candidates
        }
        direct_ranks = sorted(rank_by_id[item] for item in final.direct_evidence_provision_ids)
        first_rank = direct_ranks[0] if direct_ranks else None
        first_rank_by_case[review_case.case_id] = first_rank
        for cutoff in cutoffs:
            if first_rank is not None and first_rank <= cutoff:
                hit_counts[cutoff] += 1
        irrelevant_count = len(final.irrelevant_top5_provision_ids)
        irrelevant_by_case[review_case.case_id] = irrelevant_count
        context_counts[final.context_verdict] += 1
        if assistant.verdict == final.verdict:
            assistant_final_agreement_count += 1
        if final.verdict in {
            "clarification_required",
            "not_answerable_from_current_corpus",
        }:
            boundary_case_count += 1
            if assistant.verdict == final.verdict:
                assistant_correct_boundary_count += 1
        confirmed_cases.append(
            {
                "case_id": review_case.case_id,
                "user_confirmation": review_case.user_confirmation.status,
                "final_verdict": final.verdict,
                "direct_evidence_ranks": direct_ranks,
                "first_direct_evidence_rank": first_rank,
                "irrelevant_top5_count": irrelevant_count,
                "context_verdict": final.context_verdict,
                "assistant_verdict_matches_final": assistant.verdict == final.verdict,
            }
        )

    case_count = len(review.cases)
    diagnostics: dict[str, object] = {
        "schema_version": 1,
        "experiment": "D-10",
        "artifact_class": "confirmed_manual_diagnostic_not_gold",
        "status": "completed",
        "run_binding": expected_binding,
        "review_file_sha256": _sha256(review_bytes),
        "finalizer_code_file_sha256": _sha256(Path(__file__).read_bytes()),
        "confirmed_case_count": case_count,
        "manual_direct_evidence_hit_at": {
            str(cutoff): {
                "hit_count": hit_counts[cutoff],
                "case_count": case_count,
                "rate": _ratio(hit_counts[cutoff], case_count),
            }
            for cutoff in cutoffs
        },
        "first_direct_evidence_rank_by_case": first_rank_by_case,
        "top5_irrelevant_candidates": {
            "total": sum(irrelevant_by_case.values()),
            "by_case": irrelevant_by_case,
        },
        "context_verdict_counts": {
            key: context_counts.get(key, 0)
            for key in ("sufficient", "insufficient", "blocked")
        },
        "assistant_final_verdict_agreement": {
            "match_count": assistant_final_agreement_count,
            "case_count": case_count,
        },
        "clarification_vs_corpus_gap_distinction": {
            "correct_count": assistant_correct_boundary_count,
            "boundary_case_count": boundary_case_count,
        },
        "cases": confirmed_cases,
        "metric_warning": (
            "This is a user-confirmed D-10 manual diagnostic, not Evidence Recall or gold."
        ),
    }
    diagnostics["payload_without_self_hash_sha256"] = _sha256(
        _canonical_json_bytes(diagnostics)
    )
    return diagnostics, _atomic_create_json(output_path, diagnostics)


def _arguments(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Experiment D-10 manual review workflow")
    subparsers = parser.add_subparsers(dest="command", required=True)
    create = subparsers.add_parser("create-review")
    create.add_argument("--result", type=Path, required=True)
    create.add_argument("--output", type=Path)
    finalize = subparsers.add_parser("finalize")
    finalize.add_argument("--result", type=Path, required=True)
    finalize.add_argument("--review", type=Path, required=True)
    finalize.add_argument("--output", type=Path)
    return parser.parse_args(argv)


def _cli_path(path: Path) -> Path:
    return path if path.is_absolute() else REPOSITORY_ROOT / path


def main(argv: Sequence[str] | None = None) -> int:
    arguments = _arguments(argv)
    try:
        result = _cli_path(arguments.result)
        if arguments.command == "create-review":
            output = (
                _cli_path(arguments.output)
                if arguments.output
                else result.parent / "manual-review.json"
            )
            payload, file_sha256 = create_review_template(result, output)
            print(
                json.dumps(
                    {
                        "status": payload["status"],
                        "review_path": str(output.resolve()),
                        "review_file_sha256": file_sha256,
                        "case_count": len(payload["cases"]),
                    },
                    ensure_ascii=False,
                    indent=2,
                )
            )
            return 0
        review = _cli_path(arguments.review)
        output = (
            _cli_path(arguments.output)
            if arguments.output
            else result.parent / "confirmed-diagnostics.json"
        )
        diagnostics, file_sha256 = finalize_confirmed_review(
            result,
            review,
            output,
        )
        print(
            json.dumps(
                {
                    "status": diagnostics["status"],
                    "diagnostics_path": str(output.resolve()),
                    "diagnostics_file_sha256": file_sha256,
                    "confirmed_case_count": diagnostics["confirmed_case_count"],
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0
    except ManualReviewResultError as error:
        print(
            json.dumps(
                {
                    "status": "failed",
                    "error_code": "manual_review_not_finalized",
                    "message": str(error),
                    "result_written": False,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "CompletedJudgment",
    "ExperimentD10ManualReview",
    "ManualReviewResultError",
    "create_review_template",
    "finalize_confirmed_review",
]
