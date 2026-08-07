from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from scripts.experiment_d_10_gold_review import (
    DEFAULT_CONTRACT,
    AnnotationProposal,
    D10GoldReviewError,
    ProposedCase,
    UserAdjudication,
    load_workflow_contract,
    preflight_contract,
)


def test_tracked_contract_freezes_ten_by_3066_judgments() -> None:
    contract = load_workflow_contract()

    assert contract.expected_case_count == 10
    assert contract.corpus_binding.eligible_provision_count == 3066
    assert contract.expected_total_judgment_count == 30660
    assert "rank" in contract.forbidden_annotation_input_fields
    assert "approved_gold" in contract.prohibited_claims_before_seal


def test_contract_preflight_binds_existing_d10_without_external_calls() -> None:
    result = preflight_contract()

    assert result["status"] == "valid"
    assert result["question_count"] == 10
    assert result["expected_total_judgment_count"] == 30660
    assert result["external_calls"] == 0


def test_contract_rejects_payload_drift(tmp_path: Path) -> None:
    payload = json.loads(DEFAULT_CONTRACT.read_text(encoding="utf-8"))
    payload["expected_total_judgment_count"] = 1
    path = tmp_path / "contract.json"
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    with pytest.raises(D10GoldReviewError):
        load_workflow_contract(path)


def test_unanswerable_proposal_rejects_positive_qrel() -> None:
    with pytest.raises(ValidationError, match="cannot contain positive evidence"):
        ProposedCase(
            case_id="case-1",
            answerability="unanswerable",
            expected_action="insufficient_evidence",
            missing_user_facts=[],
            insufficient_reason="outside corpus",
            facets=[
                {
                    "facet_id": "facet-1",
                    "claim": "current price",
                    "status": "unsupported",
                    "status_reason": "outside corpus",
                }
            ],
            positive_judgments=[
                {
                    "provision_id": "provision-1",
                    "relevance": 2,
                    "facet_ids": ["facet-1"],
                    "evidence_scope": "leaf",
                    "rationale": "invalid",
                }
            ],
            reference_response={
                "action": "insufficient_evidence",
                "text": "법령 corpus로 확인할 수 없습니다.",
                "cited_provision_ids": [],
            },
            annotation_notes="boundary",
        )


def test_annotation_proposal_requires_ten_distinct_cases() -> None:
    with pytest.raises(ValidationError):
        AnnotationProposal(
            schema_version=1,
            experiment="D-10-GOLD-V1",
            artifact_class="assistant_annotation_proposal_not_gold",
            status="pending_user_review",
            annotator_id="codex-draft-v1",
            annotation_method="canonical_full_corpus_proposal_without_retrieval_labels",
            independence_limitation="assistant has prior project context",
            cases=[],
        )


def _confirmed_user_review() -> dict[str, object]:
    return {
        "schema_version": 1,
        "experiment": "D-10-GOLD-V1",
        "artifact_class": "user_adjudication_input",
        "status": "confirmed",
        "annotator_id": "codex-draft",
        "reviewer_id": "user-reviewer",
        "reviewed_at": "2026-08-07T13:00:00+09:00",
        "annotation_draft_sha256": "a" * 64,
        "judgments_jsonl_sha256": "b" * 64,
        "cases": [
            {
                "case_id": f"case-{index}",
                "decision": "approved",
                "positive_qrels_confirmed": True,
                "bulk_negative_confirmed": True,
                "facets_and_reference_confirmed": True,
                "comment": "",
            }
            for index in range(10)
        ],
    }


def test_confirmed_user_review_requires_independent_reviewer() -> None:
    payload = _confirmed_user_review()
    payload["reviewer_id"] = payload["annotator_id"]

    with pytest.raises(ValidationError, match="reviewer must differ"):
        UserAdjudication.model_validate(payload)


def test_confirmed_user_review_accepts_ten_approved_cases() -> None:
    review = UserAdjudication.model_validate(_confirmed_user_review())

    assert review.status == "confirmed"
    assert len(review.cases) == 10
    assert all(case.bulk_negative_confirmed for case in review.cases)
