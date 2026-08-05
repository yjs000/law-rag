from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from scripts import experiment_d_manual_review_results as results_module
from scripts.experiment_d_manual_review_results import (
    ManualReviewResultError,
    create_review_template,
    finalize_confirmed_review,
)


def _canonical_sha256(value: object) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()


def _result(path: Path) -> dict[str, object]:
    cases = []
    for case_index in range(1, 11):
        raw = [
            {
                "rank": rank,
                "provision_id": f"case-{case_index:02d}-provision-{rank:02d}",
            }
            for rank in range(1, 11)
        ]
        cases.append(
            {
                "case_id": f"case-{case_index:02d}",
                "raw_candidates": raw,
            }
        )
    payload: dict[str, object] = {
        "schema_version": 1,
        "experiment": "D-10",
        "artifact_class": "not_gold",
        "status": "retrieval_completed_awaiting_manual_review",
        "run_id": "d10-test",
        "case_count": 10,
        "inputs": {
            "corpus_snapshot_id": "corpus-sha256:" + "a" * 64,
            "embedding_profile_key": "nvidia-nemotron-3-embed-1b-512-v1",
        },
        "cases": cases,
    }
    payload["payload_without_self_hash_sha256"] = _canonical_sha256(payload)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, allow_nan=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return payload


def _judgment(
    case_index: int,
    *,
    direct_rank: int | None,
    verdict: str,
    context_verdict: str,
    irrelevant_rank: int | None = None,
) -> dict[str, object]:
    direct_ids = (
        [f"case-{case_index:02d}-provision-{direct_rank:02d}"]
        if direct_rank is not None
        else []
    )
    irrelevant_ids = (
        [f"case-{case_index:02d}-provision-{irrelevant_rank:02d}"]
        if irrelevant_rank is not None
        else []
    )
    return {
        "direct_evidence_provision_ids": direct_ids,
        "irrelevant_top5_provision_ids": irrelevant_ids,
        "verdict": verdict,
        "reason": "사람이 원문을 확인한 판정입니다.",
        "supported_answer_elements": ["확인된 요소"] if direct_ids else [],
        "missing_answer_elements": [] if direct_ids else ["현재 corpus 밖 요소"],
        "context_verdict": context_verdict,
    }


def test_create_review_template_binds_run_and_leaves_all_cases_on_hold(tmp_path: Path) -> None:
    result_path = tmp_path / "result.json"
    _result(result_path)
    review_path = tmp_path / "manual-review.json"

    payload, file_sha256 = create_review_template(result_path, review_path)

    assert review_path.exists()
    assert len(file_sha256) == 64
    assert payload["status"] == "in_review"
    assert len(payload["cases"]) == 10
    assert all(case["assistant_review"] is None for case in payload["cases"])
    assert all(
        case["user_confirmation"]["status"] == "on_hold" for case in payload["cases"]
    )


def test_cli_resolves_relative_artifact_paths_from_repository_root(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    result_path = tmp_path / ".data" / "runs" / "d10-test" / "result.json"
    result_path.parent.mkdir(parents=True)
    _result(result_path)
    monkeypatch.setattr(results_module, "REPOSITORY_ROOT", tmp_path)
    monkeypatch.chdir(tmp_path / ".data")

    exit_code = results_module.main(
        ["create-review", "--result", ".data/runs/d10-test/result.json"]
    )

    assert exit_code == 0
    assert (result_path.parent / "manual-review.json").exists()


def test_finalize_rejects_any_unconfirmed_review_without_output(tmp_path: Path) -> None:
    result_path = tmp_path / "result.json"
    _result(result_path)
    review_path = tmp_path / "manual-review.json"
    create_review_template(result_path, review_path)
    output_path = tmp_path / "diagnostics.json"

    with pytest.raises(ManualReviewResultError, match="not confirmed"):
        finalize_confirmed_review(result_path, review_path, output_path)

    assert not output_path.exists()


def test_confirmed_review_computes_only_manual_diagnostics(tmp_path: Path) -> None:
    result_path = tmp_path / "result.json"
    _result(result_path)
    review_path = tmp_path / "manual-review.json"
    template, _ = create_review_template(result_path, review_path)
    template["status"] = "confirmed"
    for index, case in enumerate(template["cases"], 1):
        if index <= 4:
            direct_rank = (1, 3, 5, 10)[index - 1]
            verdict = "directly_answerable"
            context_verdict = "sufficient"
        elif index <= 7:
            direct_rank = None
            verdict = "clarification_required"
            context_verdict = "insufficient"
        else:
            direct_rank = None
            verdict = "not_answerable_from_current_corpus"
            context_verdict = "blocked"
        case["assistant_review"] = _judgment(
            index,
            direct_rank=direct_rank,
            verdict=verdict,
            context_verdict=context_verdict,
            irrelevant_rank=5 if direct_rank != 5 else 4,
        )
        case["user_confirmation"] = {
            "status": "approved",
            "notes": "확인",
            "override": None,
        }
    review_path.write_text(
        json.dumps(template, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    output_path = tmp_path / "confirmed-diagnostics.json"

    diagnostics, _ = finalize_confirmed_review(result_path, review_path, output_path)

    assert diagnostics["artifact_class"] == "confirmed_manual_diagnostic_not_gold"
    assert diagnostics["manual_direct_evidence_hit_at"]["1"]["hit_count"] == 1
    assert diagnostics["manual_direct_evidence_hit_at"]["3"]["hit_count"] == 2
    assert diagnostics["manual_direct_evidence_hit_at"]["5"]["hit_count"] == 3
    assert diagnostics["manual_direct_evidence_hit_at"]["10"]["hit_count"] == 4
    assert diagnostics["context_verdict_counts"] == {
        "sufficient": 4,
        "insufficient": 3,
        "blocked": 3,
    }
    distinction = diagnostics["clarification_vs_corpus_gap_distinction"]
    assert distinction == {"correct_count": 6, "boundary_case_count": 6}
    assert output_path.exists()


def test_modified_user_override_is_used_and_compared_with_assistant(tmp_path: Path) -> None:
    result_path = tmp_path / "result.json"
    _result(result_path)
    review_path = tmp_path / "manual-review.json"
    template, _ = create_review_template(result_path, review_path)
    template["status"] = "confirmed"
    for index, case in enumerate(template["cases"], 1):
        assistant = _judgment(
            index,
            direct_rank=1,
            verdict="directly_answerable",
            context_verdict="sufficient",
        )
        case["assistant_review"] = assistant
        case["user_confirmation"] = {
            "status": "approved",
            "notes": "",
            "override": None,
        }
    template["cases"][0]["user_confirmation"] = {
        "status": "modified",
        "notes": "현재 corpus로 답할 수 없음",
        "override": _judgment(
            1,
            direct_rank=None,
            verdict="not_answerable_from_current_corpus",
            context_verdict="blocked",
        ),
    }
    review_path.write_text(
        json.dumps(template, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    diagnostics, _ = finalize_confirmed_review(
        result_path,
        review_path,
        tmp_path / "diagnostics.json",
    )

    assert diagnostics["manual_direct_evidence_hit_at"]["1"]["hit_count"] == 9
    assert diagnostics["assistant_final_verdict_agreement"]["match_count"] == 9
    assert diagnostics["clarification_vs_corpus_gap_distinction"] == {
        "correct_count": 0,
        "boundary_case_count": 1,
    }
