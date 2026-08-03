from __future__ import annotations

import copy
import hashlib
import json

import pytest
from pydantic import ValidationError

from scripts.experiment_d_gold_contract import (
    ExperimentDGoldAdjudicationManifest,
    ExperimentDGoldCase,
    ExperimentDGoldDataset,
    ExperimentDQuestionApprovalManifest,
    GoldMetricProtocol,
    GoldSplitManifest,
    canonical_gold_case_payload_sha256,
    canonical_gold_dataset_sha256,
)
from scripts.experiment_d_question_identity import (
    question_scope_set_sha256,
    question_scope_sha256,
)

CONTENT = "제1조(목적) 이 법은 전기사업에 관한 기본 사항을 정한다."
CONTENT_SHA = hashlib.sha256(CONTENT.encode("utf-8")).hexdigest()
PASSAGE_SHA = hashlib.sha256(f"전기사업법\n제1조\n목적\n{CONTENT}".encode()).hexdigest()
CONFIG_SHA = hashlib.sha256(b"fixed-config").hexdigest()


def _json_sha256(value: object) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()


def _case(index: int, split: str | None = None) -> dict[str, object]:
    question = f"전기사업의 기본 사항을 확인하는 일반 질문 {index}은 무엇인가요?"
    case_id = f"lay-energy-{index:04d}"
    qrel_id = f"{case_id}-qrel-1"
    family_index = (index - 1) // 5
    if split is None:
        split = "calibration" if family_index < 40 else "test"
    candidate_ids = [f"provision-{index}", f"distractor-{index}"]
    return {
        "id": case_id,
        "question": question,
        "question_sha256": hashlib.sha256(question.encode("utf-8")).hexdigest(),
        "question_style": "plain_language_direct_question",
        "question_review_status": "approved",
        "scenario_family_id": f"scenario-{family_index + 1:03d}",
        "intent": "사업 시작·전체 절차",
        "technology": "renewable_business",
        "as_of_date": "2026-08-03",
        "split": split,
        "answerability": "fully_answerable",
        "expected_action": "answer",
        "missing_user_facts": [],
        "insufficient_reason": None,
        "required_answer_facets": [
            {
                "facet_id": "facet-purpose",
                "claim": "법이 정하는 기본 사항",
                "status": "supported",
                "status_reason": "제1조가 직접 규정함",
            }
        ],
        "qrels": [
            {
                "qrel_id": qrel_id,
                "provision_id": f"provision-{index}",
                "document_id": "document-1",
                "version_id": "version-1",
                "path": "제1조",
                "heading": "목적",
                "effective_from": "2026-01-01",
                "effective_to": None,
                "content_sha256": CONTENT_SHA,
                "passage_text_sha256": PASSAGE_SHA,
                "relevance": 2,
                "facet_ids": ["facet-purpose"],
                "evidence_scope": "leaf",
            }
        ],
        "reference_contexts": [
            {
                "qrel_id": qrel_id,
                "content": CONTENT,
                "content_sha256": CONTENT_SHA,
            }
        ],
        "reference_response": {
            "action": "answer",
            "text": "전기사업에 관한 기본 사항을 정합니다.",
            "cited_qrel_ids": [qrel_id],
        },
        "judgment_coverage": {
            "candidate_count": 2,
            "judged_count": 2,
            "judged_candidate_provision_ids": list(candidate_ids),
            "judged_candidate_set_sha256": _json_sha256(sorted(candidate_ids)),
            "pool_method_candidates": [
                {
                    "method_id": "manual-path-v1",
                    "top_k": 1,
                    "candidate_provision_ids": [f"provision-{index}"],
                    "candidate_set_sha256": _json_sha256([f"provision-{index}"]),
                },
                {
                    "method_id": "dense-pool-v1",
                    "top_k": 2,
                    "candidate_provision_ids": list(candidate_ids),
                    "candidate_set_sha256": _json_sha256(sorted(candidate_ids)),
                },
            ],
            "all_candidates_judged": True,
            "alternative_positive_search_completed": True,
            "completeness_status": "adjudicated",
            "distractor_provision_ids": [f"distractor-{index}"],
        },
        "annotation_review": {
            "annotator_id": "annotator-a",
            "reviewer_id": "reviewer-b",
            "status": "adjudicated",
            "reviewed_at": "2026-08-03T13:00:00+09:00",
            "disagreement_resolution": None,
        },
        "evaluation_tags": ["layperson"],
        "boundary_type": None,
        "control_pair_id": None,
    }


def _dataset() -> dict[str, object]:
    cases = [_case(index) for index in range(1, 1001)]
    question_set_sha = hashlib.sha256(
        json.dumps(
            [{"id": case["id"], "question": case["question"]} for case in cases],
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()
    family_assignments = sorted({(case["scenario_family_id"], case["split"]) for case in cases})
    assignment_sha = hashlib.sha256(
        json.dumps(
            family_assignments,
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    question_scope_set_sha = question_scope_set_sha256(cases)
    assert question_scope_set_sha is not None
    return {
        "schema_version": 1,
        "dataset_version": "experiment-d-lay-energy-gold-v1",
        "evaluation_status": "approved_gold",
        "source_bank": {
            "artifact": "experiment-d-lay-energy-query-bank-v1-draft.json",
            "bank_version": "experiment-d-lay-energy-query-bank-v1-draft",
            "question_count": 1000,
            "question_set_sha256": question_set_sha,
            "question_scope_set_sha256": question_scope_set_sha,
            "approval_manifest_artifact": ("experiment-d-lay-energy-question-approval-v1.json"),
            "approval_manifest_sha256": CONFIG_SHA,
        },
        "corpus_snapshot": {
            "parser_contract_version": "3",
            "as_of_date": "2026-08-03",
            "retrieval_unit": "provision",
            "searchable_provision_count": 3066,
            "fingerprint_sha256": CONFIG_SHA,
            "passage_template_version": "legal-provision-v1",
            "embedding_profile_key": "nvidia-nemotron-3-embed-1b-512-v1",
        },
        "split_manifest": {
            "algorithm": "frozen-scenario-family-assignment-v1",
            "group_field": "scenario_family_id",
            "calibration_count": 200,
            "test_count": 800,
            "assignment_sha256": assignment_sha,
        },
        "metric_protocol": {
            "retrieval_mode": "dense_only",
            "retrieval_unit": "provision",
            "candidate_k": 10,
            "cutoffs": [1, 3, 5, 10],
            "direct_relevance_grade": 2,
            "context_relevance_grade": 1,
            "recall_and_mrr_positive_grade": 2,
            "recall_definition": "macro_fraction_of_grade2_qrels",
            "hit_rate_definition": "macro_any_grade2_qrel",
            "precision_positive_grades": [1, 2],
            "precision_definition": ("count_grade1_or_grade2_qrels_in_top_k_divided_by_k"),
            "direct_precision_positive_grade": 2,
            "direct_precision_definition": ("count_grade2_qrels_in_top_k_divided_by_k"),
            "precision_denominator": "fixed_k_even_when_fewer_candidates_returned",
            "mrr_cutoff": 10,
            "ndcg_uses_graded_relevance": True,
            "ndcg_gain": "exp2_minus_1",
            "ndcg_discount": "log2_rank_plus_1",
            "facet_positive_grade": 2,
            "hierarchy_policy": "exact_qrel_ids_with_explicit_evidence_closure",
            "query_average": "macro",
            "facet_recall_denominator": "supported_required_facets",
            "corpus_coverage_denominator": "all_required_facets",
            "unjudged_policy": "nonrelevant_in_frozen_pool_benchmark",
            "suite_aggregation": "never_average_with_synthetic_control_suite",
            "retrieved_duplicate_policy": "fail_run",
            "score_order": "raw_cosine_similarity_desc_then_provision_id_asc",
            "boundary_tie_policy": "fail_on_equal_score_at_10_and_11",
            "empty_fully_population_policy": "fail_run",
            "aggregate_decimal_places": 12,
            "primary_split": "test",
            "calibration_aggregation": "diagnostic_only",
            "combined_aggregation": "diagnostic_only",
            "primary_ranking_metric": "ndcg_at_10",
            "completeness_gate_metric": "recall_at_10",
            "top_context_purity_diagnostic": "precision_at_5",
            "report_primary_aggregation": ("scenario_family_macro_of_within_family_case_macro"),
            "legacy_primary_aggregation": "case_macro_backward_compatible",
            "confidence_interval_population": "held_out_test_fully_answerable_only",
            "confidence_interval_metrics": [
                "ndcg_at_10",
                "recall_at_10",
                "precision_at_5",
            ],
            "bootstrap_resampling_unit": "scenario_family_id",
            "bootstrap_algorithm": ("sha256_counter_family_resample_with_replacement_v1"),
            "bootstrap_seed": 20260803,
            "bootstrap_replicates": 2000,
            "bootstrap_confidence_level": 0.95,
            "bootstrap_interval_method": "equal_tailed_percentile_type7",
            "bootstrap_family_order": "scenario_family_id_utf8_lexicographic",
            "bootstrap_draw_method": ("sha256_prefix_uint64_big_endian_mod_family_count"),
            "recall_mrr_ndcg_population": ["fully_answerable"],
            "precision_population": ["fully_answerable"],
            "separate_answerability_reports": [
                "partially_answerable",
                "clarification_required",
                "unanswerable",
            ],
            "empty_separate_population_policy": "report_not_applicable",
        },
        "annotation_protocol": {
            "pool_methods": [
                {
                    "method_id": "manual-path-v1",
                    "kind": "manual_legal_path_lookup",
                    "configuration_sha256": CONFIG_SHA,
                    "top_k": 1,
                },
                {
                    "method_id": "dense-pool-v1",
                    "kind": "dense_candidate_pool",
                    "configuration_sha256": CONFIG_SHA,
                    "top_k": 2,
                },
            ],
            "retrieval_system_labels_hidden_from_annotators": True,
            "test_qrels_sealed_from_retrieval_tuning": True,
            "independent_reviewer_required": True,
            "unjudged_policy": "nonrelevant_in_frozen_pool_benchmark",
        },
        "cases": cases,
    }


def _append_direct_supported_facet(case: dict[str, object]) -> None:
    facet_id = "facet-additional-duty"
    qrel_id = f"{case['id']}-qrel-2"
    provision_id = f"{case['id']}-provision-2"
    case["required_answer_facets"].append(
        {
            "facet_id": facet_id,
            "claim": "추가로 확인해야 할 의무",
            "status": "supported",
            "status_reason": "추가 조문이 직접 규정함",
        }
    )
    qrel = copy.deepcopy(case["qrels"][0])
    qrel.update(
        {
            "qrel_id": qrel_id,
            "provision_id": provision_id,
            "path": "제2조",
            "heading": "추가 의무",
            "facet_ids": [facet_id],
        }
    )
    case["qrels"].append(qrel)
    context = copy.deepcopy(case["reference_contexts"][0])
    context["qrel_id"] = qrel_id
    case["reference_contexts"].append(context)

    coverage = case["judgment_coverage"]
    coverage["candidate_count"] += 1
    coverage["judged_count"] += 1
    coverage["judged_candidate_provision_ids"].append(provision_id)
    coverage["judged_candidate_set_sha256"] = _json_sha256(
        sorted(coverage["judged_candidate_provision_ids"])
    )
    dense_pool = coverage["pool_method_candidates"][1]
    dense_pool["candidate_provision_ids"].append(provision_id)
    dense_pool["top_k"] = len(dense_pool["candidate_provision_ids"])
    dense_pool["candidate_set_sha256"] = _json_sha256(sorted(dense_pool["candidate_provision_ids"]))


def test_valid_gold_case_enforces_direct_evidence_and_frozen_context() -> None:
    case = ExperimentDGoldCase.model_validate(_case(1))

    assert case.answerability == "fully_answerable"
    assert case.question_style == "plain_language_direct_question"
    assert case.qrels[0].relevance == 2
    assert case.reference_contexts[0].content == CONTENT
    assert "pool_manifest_artifact" not in case.judgment_coverage.model_dump()


def test_supported_facet_cannot_use_context_only_qrel() -> None:
    case = _case(1)
    case["qrels"][0]["relevance"] = 1

    with pytest.raises(ValidationError, match="relevance-2 direct evidence"):
        ExperimentDGoldCase.model_validate(case)


@pytest.mark.parametrize("partial", [False, True], ids=["answer", "partial-answer"])
def test_answer_citations_cover_every_supported_facet(partial: bool) -> None:
    case = _case(1)
    _append_direct_supported_facet(case)
    if partial:
        case["required_answer_facets"].append(
            {
                "facet_id": "facet-missing",
                "claim": "현재 corpus 밖의 추가 요건",
                "status": "unsupported",
                "status_reason": "현재 corpus에 직접 근거가 없음",
            }
        )
        case["answerability"] = "partially_answerable"
        case["expected_action"] = "partial_answer_with_limits"
        case["insufficient_reason"] = "추가 요건의 직접 근거가 없음"
        case["reference_response"]["action"] = "partial_answer_with_limits"

    with pytest.raises(ValidationError, match="cover every supported facet"):
        ExperimentDGoldCase.model_validate(case)


def test_every_judged_candidate_must_be_classified_inline() -> None:
    case = _case(1)
    case["judgment_coverage"]["distractor_provision_ids"] = []

    with pytest.raises(ValidationError, match="positive qrel or distractor"):
        ExperimentDGoldCase.model_validate(case)


def test_inline_judged_candidate_set_hash_is_verified() -> None:
    case = _case(1)
    case["judgment_coverage"]["judged_candidate_provision_ids"][1] = "changed-candidate"

    with pytest.raises(ValidationError, match="candidate set hash mismatch"):
        ExperimentDGoldCase.model_validate(case)


def test_pool_method_candidate_hash_is_verified() -> None:
    case = _case(1)
    case["judgment_coverage"]["pool_method_candidates"][1]["candidate_provision_ids"][1] = (
        "changed-candidate"
    )

    with pytest.raises(ValidationError, match="pool candidate set hash mismatch"):
        ExperimentDGoldCase.model_validate(case)


def test_per_method_candidate_union_must_equal_judged_pool() -> None:
    case = _case(1)
    dense_pool = case["judgment_coverage"]["pool_method_candidates"][1]
    dense_pool["candidate_provision_ids"][1] = "other-candidate"
    dense_pool["candidate_set_sha256"] = _json_sha256(sorted(dense_pool["candidate_provision_ids"]))

    with pytest.raises(ValidationError, match="union of per-method candidates"):
        ExperimentDGoldCase.model_validate(case)


def test_independent_reviewer_ids_must_not_be_blank() -> None:
    case = _case(1)
    case["annotation_review"]["annotator_id"] = " "
    case["annotation_review"]["reviewer_id"] = "  "

    with pytest.raises(ValidationError):
        ExperimentDGoldCase.model_validate(case)


def test_clarification_takes_precedence_when_user_fact_is_missing() -> None:
    case = _case(1)
    case["required_answer_facets"][0]["status"] = "needs_clarification"
    case["answerability"] = "clarification_required"
    case["expected_action"] = "ask_clarifying_question"
    case["missing_user_facts"] = ["설비 용량"]
    case["reference_response"] = {
        "action": "ask_clarifying_question",
        "text": "설비 용량이 얼마인지 먼저 알려주세요.",
        "cited_qrel_ids": [],
    }

    validated = ExperimentDGoldCase.model_validate(case)

    assert validated.answerability == "clarification_required"


def test_unanswerable_case_uses_insufficient_response_without_qrels() -> None:
    case = _case(1)
    case["required_answer_facets"][0]["status"] = "unsupported"
    case["answerability"] = "unanswerable"
    case["expected_action"] = "insufficient_evidence"
    case["insufficient_reason"] = "현재 corpus에 직접 근거가 없음"
    case["qrels"] = []
    case["reference_contexts"] = []
    case["judgment_coverage"]["distractor_provision_ids"] = list(
        case["judgment_coverage"]["judged_candidate_provision_ids"]
    )
    case["reference_response"] = {
        "action": "insufficient_evidence",
        "text": "현재 법령 corpus만으로는 답할 근거가 부족합니다.",
        "cited_qrel_ids": [],
    }

    validated = ExperimentDGoldCase.model_validate(case)

    assert validated.answerability == "unanswerable"


def test_reference_context_text_change_is_detected() -> None:
    case = _case(1)
    case["reference_contexts"][0]["content"] = "변경된 본문"

    with pytest.raises(ValidationError, match="content hash mismatch"):
        ExperimentDGoldCase.model_validate(case)


def test_full_gold_preserves_family_level_calibration_test_split() -> None:
    dataset = ExperimentDGoldDataset.model_validate(_dataset())

    assert len(dataset.cases) == 1000
    assert sum(case.split == "calibration" for case in dataset.cases) == 200
    assert dataset.split_manifest.algorithm == "frozen-scenario-family-assignment-v1"
    assert dataset.metric_protocol.primary_split == "test"
    assert dataset.metric_protocol.calibration_aggregation == "diagnostic_only"
    assert dataset.metric_protocol.combined_aggregation == "diagnostic_only"
    assert dataset.metric_protocol.recall_mrr_ndcg_population == ("fully_answerable",)
    assert dataset.metric_protocol.precision_positive_grades == (1, 2)
    assert dataset.metric_protocol.precision_denominator == (
        "fixed_k_even_when_fewer_candidates_returned"
    )
    assert dataset.metric_protocol.precision_population == ("fully_answerable",)
    assert dataset.metric_protocol.primary_ranking_metric == "ndcg_at_10"
    assert dataset.metric_protocol.completeness_gate_metric == "recall_at_10"
    assert dataset.metric_protocol.top_context_purity_diagnostic == "precision_at_5"
    assert dataset.metric_protocol.report_primary_aggregation == (
        "scenario_family_macro_of_within_family_case_macro"
    )
    assert dataset.metric_protocol.bootstrap_resampling_unit == "scenario_family_id"
    assert dataset.metric_protocol.bootstrap_seed == 20260803
    assert dataset.metric_protocol.bootstrap_replicates == 2000
    assert dataset.metric_protocol.confidence_interval_metrics == (
        "ndcg_at_10",
        "recall_at_10",
        "precision_at_5",
    )
    assert set(dataset.metric_protocol.separate_answerability_reports) == {
        "partially_answerable",
        "clarification_required",
        "unanswerable",
    }


def test_dataset_links_case_pools_to_protocol_method_and_top_k() -> None:
    dataset = _dataset()
    dataset["cases"][0]["judgment_coverage"]["pool_method_candidates"][0]["top_k"] = 2

    with pytest.raises(ValidationError, match="top_k must match"):
        ExperimentDGoldDataset.model_validate(dataset)


def test_non_full_pool_requires_exact_min_top_k_candidate_count() -> None:
    dataset = _dataset()
    dataset["annotation_protocol"]["pool_methods"][1]["top_k"] = 3
    for case in dataset["cases"]:
        case["judgment_coverage"]["pool_method_candidates"][1]["top_k"] = 3

    with pytest.raises(ValidationError, match=r"min\(top_k, corpus size\)"):
        ExperimentDGoldDataset.model_validate(dataset)


def test_non_full_pool_uses_corpus_size_when_it_is_below_top_k() -> None:
    dataset = _dataset()
    dataset["corpus_snapshot"]["searchable_provision_count"] = 2
    dataset["annotation_protocol"]["pool_methods"][1]["top_k"] = 3
    for case in dataset["cases"]:
        case["judgment_coverage"]["pool_method_candidates"][1]["top_k"] = 3

    validated = ExperimentDGoldDataset.model_validate(dataset)

    assert validated.annotation_protocol.pool_methods[1].top_k == 3


def test_dataset_requires_every_protocol_pool_method_per_case() -> None:
    dataset = _dataset()
    dataset["cases"][0]["judgment_coverage"]["pool_method_candidates"] = [
        dataset["cases"][0]["judgment_coverage"]["pool_method_candidates"][1]
    ]

    with pytest.raises(ValidationError, match="every annotation pool method"):
        ExperimentDGoldDataset.model_validate(dataset)


def test_metric_protocol_rejects_mixed_retrieval_population() -> None:
    protocol = copy.deepcopy(_dataset()["metric_protocol"])
    protocol["recall_mrr_ndcg_population"] = []

    with pytest.raises(ValidationError, match="fully_answerable only"):
        GoldMetricProtocol.model_validate(protocol)

    protocol = copy.deepcopy(_dataset()["metric_protocol"])
    protocol["precision_population"] = []

    with pytest.raises(ValidationError, match="Precision population"):
        GoldMetricProtocol.model_validate(protocol)


@pytest.mark.parametrize(
    ("field", "invalid_value"),
    [
        ("precision_positive_grades", [2, 1]),
        ("precision_definition", "unspecified"),
        ("direct_precision_positive_grade", 1),
        ("direct_precision_definition", "unspecified"),
        ("precision_denominator", "returned_count"),
        ("primary_ranking_metric", "mrr_at_10"),
        ("completeness_gate_metric", "hit_rate_at_10"),
        ("top_context_purity_diagnostic", "direct_precision_at_5"),
        ("report_primary_aggregation", "case_macro"),
        ("legacy_primary_aggregation", "scenario_family_macro"),
        ("confidence_interval_population", "calibration_and_test"),
        (
            "confidence_interval_metrics",
            ["recall_at_10", "ndcg_at_10", "precision_at_5"],
        ),
        ("bootstrap_resampling_unit", "case_id"),
        ("bootstrap_algorithm", "python_random"),
        ("bootstrap_seed", 7),
        ("bootstrap_replicates", 1000),
        ("bootstrap_confidence_level", 0.9),
        ("bootstrap_interval_method", "normal"),
        ("bootstrap_family_order", "input_order"),
        ("bootstrap_draw_method", "python_random_choices"),
    ],
)
def test_metric_protocol_seals_precision_headlines_and_family_bootstrap(
    field: str,
    invalid_value: object,
) -> None:
    protocol = copy.deepcopy(_dataset()["metric_protocol"])
    protocol[field] = invalid_value

    with pytest.raises(ValidationError):
        GoldMetricProtocol.model_validate(protocol)


@pytest.mark.parametrize(
    ("field", "invalid_value"),
    [
        ("primary_split", "calibration"),
        ("calibration_aggregation", "primary"),
        ("combined_aggregation", "primary"),
    ],
)
def test_metric_protocol_seals_primary_and_diagnostic_split_policy(
    field: str,
    invalid_value: str,
) -> None:
    protocol = copy.deepcopy(_dataset()["metric_protocol"])
    protocol[field] = invalid_value

    with pytest.raises(ValidationError):
        GoldMetricProtocol.model_validate(protocol)


def test_retrieval_metrics_require_fully_answerable_case_in_each_split() -> None:
    dataset = _dataset()
    for case in dataset["cases"]:
        if case["split"] != "calibration":
            continue
        case["required_answer_facets"][0]["status"] = "needs_clarification"
        case["answerability"] = "clarification_required"
        case["expected_action"] = "ask_clarifying_question"
        case["missing_user_facts"] = ["설비 용량"]
        case["reference_response"] = {
            "action": "ask_clarifying_question",
            "text": "설비 용량을 알려주세요.",
            "cited_qrel_ids": [],
        }

    with pytest.raises(ValidationError, match="fully_answerable case in each split"):
        ExperimentDGoldDataset.model_validate(dataset)


def test_split_manifest_rejects_unverified_stratification_claim() -> None:
    split_manifest = copy.deepcopy(_dataset()["split_manifest"])
    split_manifest.update(
        {
            "algorithm": "scenario-family-stratified-v1",
            "seed": 20260803,
            "stratify_fields": [
                "intent",
                "technology",
                "answerability",
                "required_facet_count",
            ],
        }
    )

    with pytest.raises(ValidationError):
        GoldSplitManifest.model_validate(split_manifest)


def test_family_leakage_is_rejected() -> None:
    dataset = copy.deepcopy(_dataset())
    dataset["cases"][0]["split"] = "test"

    with pytest.raises(ValidationError):
        ExperimentDGoldDataset.model_validate(dataset)


def test_control_pair_id_and_expectation_must_be_declared_together() -> None:
    case = _case(1)
    case["control_pair_id"] = "pair-1"

    with pytest.raises(ValidationError, match="declared together"):
        ExperimentDGoldCase.model_validate(case)


def test_control_pair_must_have_exactly_two_cases() -> None:
    dataset = _dataset()
    dataset["cases"][0]["control_pair_id"] = "pair-1"
    dataset["cases"][0]["control_pair_expectation"] = "same_direct_evidence"

    with pytest.raises(ValidationError, match="exactly two cases"):
        ExperimentDGoldDataset.model_validate(dataset)


def test_external_question_approval_manifest_freezes_all_question_hashes() -> None:
    dataset = _dataset()
    manifest = {
        "schema_version": 1,
        "manifest_version": "experiment-d-lay-energy-question-approval-v1",
        "status": "approved",
        "decision_scope": "question_text_and_scope_only",
        "approved_by": "user",
        "approved_at": "2026-08-03T12:00:00+09:00",
        "source_bank": {
            "bank_version": dataset["source_bank"]["bank_version"],
            "question_count": 1000,
            "question_set_sha256": dataset["source_bank"]["question_set_sha256"],
            "question_scope_set_sha256": dataset["source_bank"]["question_scope_set_sha256"],
        },
        "questions": [
            {
                "id": case["id"],
                "question_sha256": case["question_sha256"],
                "question_scope_sha256": question_scope_sha256(case),
                "status": "approved",
            }
            for case in dataset["cases"]
        ],
    }

    approved = ExperimentDQuestionApprovalManifest.model_validate(manifest)

    assert len(approved.questions) == 1000
    assert (
        approved.source_bank.question_scope_set_sha256
        == dataset["source_bank"]["question_scope_set_sha256"]
    )

    manifest["approved_by"] = " "
    with pytest.raises(ValidationError):
        ExperimentDQuestionApprovalManifest.model_validate(manifest)


def test_gold_adjudication_manifest_seals_full_dataset_and_every_case() -> None:
    dataset = _dataset()
    manifest = {
        "schema_version": 1,
        "manifest_version": "experiment-d-lay-energy-gold-adjudication-v1",
        "status": "approved",
        "decision_scope": "full_gold_dataset_and_case_payloads",
        "approved_by": "gold-owner",
        "approved_at": "2026-08-03T14:00:00+09:00",
        "dataset_sha256": canonical_gold_dataset_sha256(dataset),
        "cases": [
            {
                "case_id": case["id"],
                "case_payload_sha256": canonical_gold_case_payload_sha256(case),
            }
            for case in dataset["cases"]
        ],
    }

    adjudication = ExperimentDGoldAdjudicationManifest.model_validate(manifest)

    assert len(adjudication.cases) == 1000
    assert adjudication.dataset_sha256 == canonical_gold_dataset_sha256(dataset)

    manifest["approved_by"] = " "
    with pytest.raises(ValidationError):
        ExperimentDGoldAdjudicationManifest.model_validate(manifest)
