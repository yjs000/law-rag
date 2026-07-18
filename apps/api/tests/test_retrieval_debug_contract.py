import json
from pathlib import Path

import pytest

from app.domain.search_queries import (
    SearchStageTrace,
    SearchTrace,
    prepare_search_query,
)

DATASET_PATH = (
    Path(__file__).resolve().parents[1] / "evaluation" / "retrieval-debug-v1.json"
)
DATASET = json.loads(DATASET_PATH.read_text(encoding="utf-8"))


@pytest.mark.parametrize("case", DATASET, ids=lambda case: case["id"])
def test_fixed_debug_queries_have_reproducible_rewrite_contract(case: dict) -> None:
    prepared = prepare_search_query(case["question"])

    assert list(prepared.terms) == case["expected_terms"]
    assert prepared.anchor_term == case["expected_anchor"]
    assert prepared.strict_query
    assert prepared.minimum_match_query
    if case["expected_anchor"] is None:
        assert prepared.anchored_query == ""
    else:
        assert prepared.anchored_query


def test_debug_dataset_fixes_pipeline_versions_and_both_outcomes() -> None:
    outcomes = {case["expected_outcome"] for case in DATASET}

    assert {case["pipeline_version"] for case in DATASET} == {
        "four-stage-keyword-v1/parser-schema-v2"
    }
    assert outcomes == {"evidence_expected", "no_evidence"}
    assert 5 <= len(DATASET) <= 10
    assert all("as_of_date" in case for case in DATASET)
    assert all(isinstance(case["expected_documents"], list) for case in DATASET)


def test_retrieval_diagnostics_serialize_every_stage_and_timing() -> None:
    stages = (
        SearchStageTrace("strict_all", "A B C", 0, 0, 12.25, "no_candidates"),
        SearchStageTrace(
            "minimum_two",
            "(A B) OR (A C) OR (B C)",
            3,
            2,
            18.5,
            "accepted",
        ),
        SearchStageTrace("anchor_required", None, 0, 0, 0.0, "skipped"),
        SearchStageTrace("insufficient_evidence", None, 0, 0, 0.0, "skipped"),
    )
    trace = SearchTrace(
        strategy="minimum_two",
        normalized_query="A B C",
        terms=("A", "B", "C"),
        executed_query=stages[1].query,
        relaxed=True,
        reference_title=None,
        reference_path=None,
        candidate_count=2,
        anchor_term="A",
        stages=stages,
        total_duration_ms=30.75,
    ).as_dict()

    assert trace["anchor_term"] == "A"
    assert trace["candidate_count"] == 2
    assert trace["total_duration_ms"] == 30.75
    assert [stage["stage"] for stage in trace["stages"]] == [
        "strict_all",
        "minimum_two",
        "anchor_required",
        "insufficient_evidence",
    ]
    assert all("duration_ms" in stage for stage in trace["stages"])
    assert all("raw_candidate_count" in stage for stage in trace["stages"])
    assert all("accepted_candidate_count" in stage for stage in trace["stages"])
