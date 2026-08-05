from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from scripts.experiment_d_local_rerank import (
    LocalRerankError,
    rerank_case,
    run_local_rerank,
)
from scripts.experiment_d_manual_review_results import (
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


def _candidate(case_index: int, rank: int, *, target: bool) -> dict[str, object]:
    if target and rank == 8:
        heading = "송전ㆍ배전용 전기설비의 이용요금 및 이용조건의 내용"
        content = "공사비 등 송전ㆍ배전용 전기설비 이용자가 부담할 비용의 기준 및 부담방법"
    elif target and rank == 1:
        heading = "변경허가사항 등"
        content = "전력계통의 연계 계획 중 연계장소를 변경한다."
    elif target and rank == 2:
        heading = "배전망 접속 관리"
        content = "배전망 접속을 차단할 수 있다."
    elif target:
        heading = f"전기설비 일반 조항 {rank}"
        content = f"전기설비 설치와 사업 절차에 관한 일반 내용 {rank}"
    elif rank == 1:
        heading = "전기사업의 허가와 신고"
        content = "전기사업 허가를 받고 필요한 사항을 신고한다."
    else:
        heading = f"일반 조항 {rank}"
        content = f"전기설비의 일반 관리 내용 {rank}"
    article_path = f"제{rank}조"
    return {
        "rank": rank,
        "provision_id": f"case-{case_index:02d}-provision-{rank:02d}",
        "raw_cosine_similarity": 0.91 - rank / 100,
        "document_id": f"document-{case_index:02d}",
        "version_id": f"version-{case_index:02d}",
        "document_title": "전기사업법 시행규칙",
        "path": f"{article_path}/항①",
        "content": content,
        "test_parent_heading": heading,
    }


def _case(case_index: int) -> dict[str, object]:
    target = case_index == 6
    candidates = [_candidate(case_index, rank, target=target) for rank in range(1, 11)]
    contexts = []
    for candidate in candidates:
        article_path = str(candidate["path"]).split("/", 1)[0]
        contexts.append(
            {
                "document_id": candidate["document_id"],
                "version_id": candidate["version_id"],
                "article_path": article_path,
                "provisions": [
                    {
                        "path": article_path,
                        "heading": candidate.pop("test_parent_heading"),
                    }
                ],
            }
        )
    return {
        "case_id": "lay-energy-0346" if target else f"case-{case_index:02d}",
        "question": (
            "전력망 연결 공사비가 어떻게 계산됐는지 어떤 항목을 확인하나요?"
            if target
            else "전기사업 허가와 신고가 필요한가요?"
        ),
        "raw_candidates": candidates,
        "article_contexts": contexts,
    }


def _write_confirmed_inputs(tmp_path: Path) -> tuple[Path, Path, Path]:
    cases = [_case(index) for index in range(1, 11)]
    result: dict[str, object] = {
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
    result["payload_without_self_hash_sha256"] = _canonical_sha256(result)
    result_path = tmp_path / "result.json"
    result_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    review_path = tmp_path / "manual-review.json"
    review, _ = create_review_template(result_path, review_path)
    review["status"] = "confirmed"
    for index, case in enumerate(review["cases"], 1):
        target = case["case_id"] == "lay-energy-0346"
        direct_rank = 8 if target else 1
        case["assistant_review"] = {
            "direct_evidence_provision_ids": [
                f"case-{index:02d}-provision-{direct_rank:02d}"
            ],
            "irrelevant_top5_provision_ids": (
                [f"case-{index:02d}-provision-{rank:02d}" for rank in range(1, 6)]
                if target
                else [f"case-{index:02d}-provision-05"]
            ),
            "verdict": "directly_answerable",
            "reason": "테스트 사람이 직접 확인한 판정입니다.",
            "supported_answer_elements": ["확인된 직접 근거"],
            "missing_answer_elements": [],
            "context_verdict": "sufficient",
        }
        case["user_confirmation"] = {
            "status": "approved",
            "notes": "확인",
            "override": None,
        }
    review_path.write_text(
        json.dumps(review, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    diagnostics_path = tmp_path / "confirmed-diagnostics.json"
    finalize_confirmed_review(result_path, review_path, diagnostics_path)
    return result_path, review_path, diagnostics_path


def test_rerank_uses_case_text_without_relevance_labels(tmp_path: Path) -> None:
    result_path, _, _ = _write_confirmed_inputs(tmp_path)
    result = json.loads(result_path.read_text(encoding="utf-8"))
    target = next(case for case in result["cases"] if case["case_id"] == "lay-energy-0346")

    reranked = rerank_case(target)

    assert "assistant_review" not in target
    assert reranked["active_concepts"] == ["network", "cost"]
    assert {item["provision_id"] for item in reranked["candidates"]} == {
        item["provision_id"] for item in target["raw_candidates"]
    }


def test_rerank_moves_target_evidence_to_top3_and_reduces_known_noise(
    tmp_path: Path,
) -> None:
    result_path, review_path, diagnostics_path = _write_confirmed_inputs(tmp_path)

    payload, json_path, markdown_path = run_local_rerank(
        result_path,
        review_path,
        diagnostics_path,
        tmp_path / "rerank-output",
    )

    target = payload["target_case"]
    assert target["raw_first_direct_evidence_rank"] == 8
    assert target["reranked_first_direct_evidence_rank"] <= 3
    assert target["direct_evidence_reached_top3"] is True
    assert target["raw_confirmed_irrelevant_at_5"] == 5
    assert target["reranked_confirmed_known_irrelevant_at_5"] < 5
    assert payload["invariants"]["candidate_sets_preserved"] is True
    assert payload["invariants"]["external_calls"] == 0
    assert json_path.exists()
    assert markdown_path.exists()


def test_rerank_rejects_unconfirmed_review_without_output(tmp_path: Path) -> None:
    result_path, review_path, diagnostics_path = _write_confirmed_inputs(tmp_path)
    review = json.loads(review_path.read_text(encoding="utf-8"))
    review["status"] = "in_review"
    review_path.write_text(
        json.dumps(review, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    output_dir = tmp_path / "rerank-output"

    with pytest.raises(LocalRerankError, match="not confirmed"):
        run_local_rerank(result_path, review_path, diagnostics_path, output_dir)

    assert not output_dir.exists()


def test_rerank_does_not_overwrite_existing_output(tmp_path: Path) -> None:
    result_path, review_path, diagnostics_path = _write_confirmed_inputs(tmp_path)
    output_dir = tmp_path / "rerank-output"
    run_local_rerank(result_path, review_path, diagnostics_path, output_dir)

    with pytest.raises(LocalRerankError, match="already exists"):
        run_local_rerank(result_path, review_path, diagnostics_path, output_dir)
