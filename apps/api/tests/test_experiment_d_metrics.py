from __future__ import annotations

from dataclasses import replace
from math import isclose, log2

import pytest

from scripts.experiment_d_metrics import MetricCase, MetricQrel, evaluate_dense_retrieval


def _case(
    case_id: str,
    *,
    split: str = "test",
    answerability: str = "fully_answerable",
    boundary_type: str | None = None,
) -> MetricCase:
    return MetricCase(
        case_id=case_id,
        split=split,  # type: ignore[arg-type]
        answerability=answerability,
        supported_facet_ids=("permit",),
        qrels=(
            MetricQrel("context", 1, ("permit",)),
            MetricQrel("direct", 2, ("permit",)),
        ),
        boundary_type=boundary_type,
        control_pair_id=None,
    )


def test_dense_metrics_use_direct_grade_two_and_graded_ndcg() -> None:
    case = _case("q1", boundary_type="near_threshold")

    result = evaluate_dense_retrieval([case], {"q1": ["context", "direct", "noise"]})

    primary = result["primary"]
    assert result["primary_population"] == {
        "split": "test",
        "answerability": "fully_answerable",
    }
    assert primary["recall_at_1"] == 0.0
    assert primary["recall_at_3"] == 1.0
    assert primary["mrr_at_10"] == 0.5
    assert isclose(primary["ndcg_at_1"], 1 / 3)
    expected_ndcg_at_3 = (1 + 3 / log2(3)) / (3 + 1 / log2(3))
    assert isclose(primary["ndcg_at_3"], expected_ndcg_at_3)
    assert primary["facet_recall_at_1"] == 0.0
    assert primary["facet_recall_at_3"] == 1.0
    assert primary["all_required_facets_covered_at_3"] == 1.0
    assert result["overall"] == primary
    assert result["overall_semantics"] == "backward_compatible_alias_of_primary"
    assert result["by_boundary_type"]["near_threshold"]["recall_at_3"] == 1.0


def test_duplicate_hit_fails_closed() -> None:
    case = _case("q1")

    with pytest.raises(ValueError, match="must be unique"):
        evaluate_dense_retrieval([case], {"q1": ["noise", "noise", "direct"]})


def test_recall_is_fraction_of_direct_qrels_and_hit_rate_is_separate() -> None:
    case = MetricCase(
        case_id="q1",
        split="test",
        answerability="fully_answerable",
        supported_facet_ids=("permit",),
        qrels=(
            MetricQrel("direct-1", 2, ("permit",)),
            MetricQrel("direct-2", 2, ("permit",)),
        ),
        boundary_type=None,
        control_pair_id=None,
    )

    result = evaluate_dense_retrieval([case], {"q1": ["direct-1"]})

    assert result["primary"]["recall_at_1"] == 0.5
    assert result["primary"]["hit_rate_at_1"] == 1.0


def test_primary_is_held_out_test_and_other_fully_answerable_aggregates_are_diagnostics() -> None:
    calibration = _case("calibration", split="calibration")
    held_out = _case("held-out")

    result = evaluate_dense_retrieval(
        [calibration, held_out],
        {
            "calibration": ["direct"],
            "held-out": ["noise"],
        },
    )

    assert result["primary"]["evaluated_query_count"] == 1
    assert result["primary"]["recall_at_1"] == 0.0
    assert result["overall"] == result["primary"]
    diagnostic_aggregates = result["diagnostic_aggregates"]
    calibration_diagnostic = diagnostic_aggregates["calibration_fully_answerable"]
    assert calibration_diagnostic["status"] == "diagnostic_only"
    assert calibration_diagnostic["metrics"]["recall_at_1"] == 1.0
    combined_diagnostic = diagnostic_aggregates["combined_fully_answerable"]
    assert combined_diagnostic["status"] == "diagnostic_only"
    assert combined_diagnostic["metrics"]["evaluated_query_count"] == 2
    assert combined_diagnostic["metrics"]["recall_at_1"] == 0.5


def test_non_fully_answerable_cases_are_not_mixed_into_retrieval_average() -> None:
    full = _case("full")
    partial = _case(
        "partial-calibration",
        split="calibration",
        answerability="partially_answerable",
    )
    partial_test = _case("partial-test", answerability="partially_answerable")
    unanswerable = _case(
        "unanswerable-calibration",
        split="calibration",
        answerability="unanswerable",
    )

    result = evaluate_dense_retrieval(
        [full, partial, partial_test, unanswerable],
        {
            "full": ["direct"],
            "partial-calibration": ["noise"],
            "partial-test": ["direct"],
            "unanswerable-calibration": ["noise"],
        },
    )

    assert result["primary"]["evaluated_query_count"] == 1
    assert result["primary"]["recall_at_1"] == 1.0
    assert result["separate_answerability_counts"]["partially_answerable"] == 2
    partial_report = result["separate_answerability"]["partially_answerable"]
    assert partial_report["case_count"] == 2
    assert partial_report["status"] == "diagnostic_only_evidence_gate_pending"
    assert partial_report["core_retrieval_metrics"] is None
    assert partial_report["diagnostics"]["grade2_recall_at_1"] == 0.5
    assert partial_report["by_split"]["calibration"]["case_count"] == 1
    assert partial_report["by_split"]["calibration"]["diagnostics"]["grade2_recall_at_1"] == 0.0
    assert partial_report["by_split"]["test"]["case_count"] == 1
    assert partial_report["by_split"]["test"]["diagnostics"]["grade2_recall_at_1"] == 1.0
    unanswerable_report = result["separate_answerability"]["unanswerable"]
    assert unanswerable_report["case_count"] == 1
    assert unanswerable_report["status"] == "diagnostic_only_evidence_gate_pending"
    assert unanswerable_report["core_retrieval_metrics"] is None
    assert unanswerable_report["by_split"]["test"]["case_count"] == 0
    assert unanswerable_report["by_split"]["test"]["status"] == "not_applicable"
    assert unanswerable_report["by_split"]["test"]["diagnostics"] is None
    clarification_report = result["separate_answerability"]["clarification_required"]
    assert clarification_report["case_count"] == 0
    assert clarification_report["status"] == "not_applicable"
    assert clarification_report["by_split"]["calibration"]["status"] == "not_applicable"
    assert clarification_report["by_split"]["test"]["status"] == "not_applicable"


def test_primary_requires_held_out_fully_answerable_population() -> None:
    calibration = _case("calibration", split="calibration")

    with pytest.raises(ValueError, match="held-out test fully_answerable"):
        evaluate_dense_retrieval([calibration], {"calibration": ["direct"]})


def test_missing_or_extra_rankings_fail_closed() -> None:
    case = _case("q1")

    with pytest.raises(ValueError, match="rankings do not match cases"):
        evaluate_dense_retrieval([case], {})
    with pytest.raises(ValueError, match="rankings do not match cases"):
        evaluate_dense_retrieval([case], {"q1": [], "extra": []})


def test_cutoffs_must_be_unique_positive_and_sorted() -> None:
    case = _case("q1")

    with pytest.raises(ValueError, match="metric cutoffs"):
        evaluate_dense_retrieval([case], {"q1": []}, ks=(3, 1))
    with pytest.raises(ValueError, match="metric cutoffs"):
        evaluate_dense_retrieval([case], {"q1": []}, ks=(1, 1))
    with pytest.raises(ValueError, match="ending at 10"):
        evaluate_dense_retrieval([case], {"q1": []}, ks=(1, 3, 5))


def test_core_metrics_require_a_fully_answerable_population() -> None:
    case = _case("q1", answerability="unanswerable")

    with pytest.raises(ValueError, match="held-out test fully_answerable"):
        evaluate_dense_retrieval([case], {"q1": []})


def test_fully_answerable_case_requires_direct_qrel_and_supported_facet() -> None:
    missing_direct = MetricCase(
        case_id="missing-direct",
        split="test",
        answerability="fully_answerable",
        supported_facet_ids=("permit",),
        qrels=(MetricQrel("context", 1, ("permit",)),),
        boundary_type=None,
        control_pair_id=None,
    )
    missing_facet = MetricCase(
        case_id="missing-facet",
        split="test",
        answerability="fully_answerable",
        supported_facet_ids=(),
        qrels=(MetricQrel("direct", 2, ()),),
        boundary_type=None,
        control_pair_id=None,
    )

    with pytest.raises(ValueError, match="grade-2 qrel"):
        evaluate_dense_retrieval([missing_direct], {"missing-direct": []})
    with pytest.raises(ValueError, match="supported facet"):
        evaluate_dense_retrieval([missing_facet], {"missing-facet": []})


def test_control_pairs_report_descriptive_rank_comparison() -> None:
    first = replace(
        _case("first"),
        control_pair_id="pair-1",
        control_pair_expectation="same_direct_evidence",
    )
    second = replace(
        _case("second"),
        control_pair_id="pair-1",
        control_pair_expectation="same_direct_evidence",
    )

    result = evaluate_dense_retrieval(
        [first, second],
        {
            "first": ["direct", "noise-a"],
            "second": ["noise-b", "direct"],
        },
    )

    controls = result["control_pair_diagnostics"]
    assert controls["status"] == "descriptive_control_diagnostics"
    assert controls["pair_count"] == 1
    assert controls["relation_met_rate"] == 1.0
    assert controls["mean_absolute_reciprocal_rank_delta"] == 0.5
    assert controls["pairs"][0]["first_grade2_ranks"] == [1, 2]
