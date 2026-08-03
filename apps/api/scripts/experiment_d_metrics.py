"""Pure dense-retrieval metrics for the approved Experiment D gold suite."""

from __future__ import annotations

import hashlib
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from math import floor, fsum, log2
from typing import Literal

from scripts.experiment_d_gold_contract import ExperimentDGoldDataset

DEFAULT_KS = (1, 3, 5, 10)
PRIMARY_RANKING_METRIC = "ndcg_at_10"
COMPLETENESS_GATE_METRIC = "recall_at_10"
TOP_CONTEXT_PURITY_DIAGNOSTIC = "precision_at_5"
FAMILY_BOOTSTRAP_ALGORITHM = "sha256_counter_family_resample_with_replacement_v1"
FAMILY_BOOTSTRAP_SEED = 20260803
FAMILY_BOOTSTRAP_REPLICATES = 2000
FAMILY_BOOTSTRAP_CONFIDENCE_LEVEL = 0.95
FAMILY_BOOTSTRAP_INTERVAL_METHOD = "equal_tailed_percentile_type7"
FAMILY_BOOTSTRAP_FAMILY_ORDER = "scenario_family_id_utf8_lexicographic"
FAMILY_BOOTSTRAP_DRAW_METHOD = "sha256_prefix_uint64_big_endian_mod_family_count"
HEADLINE_METRICS = (
    PRIMARY_RANKING_METRIC,
    COMPLETENESS_GATE_METRIC,
    TOP_CONTEXT_PURITY_DIAGNOSTIC,
)


@dataclass(frozen=True, slots=True)
class MetricQrel:
    provision_id: str
    relevance: Literal[1, 2]
    facet_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class MetricCase:
    case_id: str
    scenario_family_id: str
    split: Literal["calibration", "test"]
    answerability: str
    supported_facet_ids: tuple[str, ...]
    qrels: tuple[MetricQrel, ...]
    boundary_type: str | None
    control_pair_id: str | None
    distractor_ids: tuple[str, ...] = ()
    control_pair_expectation: str | None = None


def metric_cases_from_gold(dataset: ExperimentDGoldDataset) -> tuple[MetricCase, ...]:
    return tuple(
        MetricCase(
            case_id=case.id,
            scenario_family_id=case.scenario_family_id,
            split=case.split,
            answerability=case.answerability,
            supported_facet_ids=tuple(
                facet.facet_id
                for facet in case.required_answer_facets
                if facet.status == "supported"
            ),
            qrels=tuple(
                MetricQrel(
                    provision_id=qrel.provision_id,
                    relevance=qrel.relevance,
                    facet_ids=tuple(qrel.facet_ids),
                )
                for qrel in case.qrels
            ),
            boundary_type=case.boundary_type,
            control_pair_id=case.control_pair_id,
            distractor_ids=tuple(case.judgment_coverage.distractor_provision_ids),
            control_pair_expectation=case.control_pair_expectation,
        )
        for case in dataset.cases
    )


def _validate_ranking(ranked_ids: Sequence[str]) -> tuple[str, ...]:
    selected: list[str] = []
    seen: set[str] = set()
    for provision_id in ranked_ids:
        if not isinstance(provision_id, str) or not provision_id:
            raise ValueError("ranked provision IDs must be non-empty strings")
        if provision_id in seen:
            raise ValueError("ranked provision IDs must be unique")
        seen.add(provision_id)
        selected.append(provision_id)
    return tuple(selected)


def _dcg(grades: Sequence[int]) -> float:
    return fsum((2**grade - 1) / log2(rank + 1) for rank, grade in enumerate(grades, 1))


def _case_metrics(
    case: MetricCase,
    ranked_ids: Sequence[str],
    ks: tuple[int, ...],
) -> dict[str, object]:
    ranking = _validate_ranking(ranked_ids)
    grade_by_id = {qrel.provision_id: qrel.relevance for qrel in case.qrels}
    relevant_ids = set(grade_by_id)
    direct_ids = {qrel.provision_id for qrel in case.qrels if qrel.relevance == 2}
    direct_facets_by_id = {
        qrel.provision_id: set(qrel.facet_ids) for qrel in case.qrels if qrel.relevance == 2
    }
    supported_facets = set(case.supported_facet_ids)
    if not direct_ids:
        raise ValueError("fully-answerable metric case requires a grade-2 qrel")
    if not supported_facets:
        raise ValueError("fully-answerable metric case requires a supported facet")
    direct_ranks = [
        rank for rank, provision_id in enumerate(ranking, 1) if provision_id in direct_ids
    ]
    values: dict[str, object] = {
        "case_id": case.case_id,
        "scenario_family_id": case.scenario_family_id,
        "split": case.split,
        "answerability": case.answerability,
        "first_direct_rank": direct_ranks[0] if direct_ranks else None,
        "mrr_at_10": (
            1.0 / direct_ranks[0] if direct_ranks and direct_ranks[0] <= max(ks) else 0.0
        ),
    }
    ideal_grades = sorted(grade_by_id.values(), reverse=True)
    for k in ks:
        top = ranking[:k]
        retrieved_relevant = set(top) & relevant_ids
        retrieved_direct = set(top) & direct_ids
        # Precision uses the predeclared cutoff as its denominator. Returning
        # fewer than k candidates must not inflate a sparse result to 1.0.
        values[f"precision_at_{k}"] = len(retrieved_relevant) / k
        values[f"direct_precision_at_{k}"] = len(retrieved_direct) / k
        values[f"recall_at_{k}"] = len(retrieved_direct) / len(direct_ids)
        values[f"hit_rate_at_{k}"] = float(bool(retrieved_direct))
        actual_grades = [grade_by_id.get(item, 0) for item in top]
        ideal = _dcg(ideal_grades[:k])
        values[f"ndcg_at_{k}"] = _dcg(actual_grades) / ideal if ideal else 0.0
        covered_facets: set[str] = set()
        for provision_id in top:
            covered_facets.update(direct_facets_by_id.get(provision_id, set()))
        covered_supported = covered_facets & supported_facets
        values[f"facet_recall_at_{k}"] = (
            len(covered_supported) / len(supported_facets) if supported_facets else 0.0
        )
        values[f"all_required_facets_covered_at_{k}"] = float(
            bool(supported_facets) and supported_facets <= covered_supported
        )
    return values


def _macro_average(
    case_metrics: Sequence[Mapping[str, object]],
    ks: tuple[int, ...],
) -> dict[str, object]:
    if not case_metrics:
        return {
            "evaluated_query_count": 0,
            "mrr_at_10": None,
            **{
                key: None
                for k in ks
                for key in (
                    f"precision_at_{k}",
                    f"direct_precision_at_{k}",
                    f"recall_at_{k}",
                    f"hit_rate_at_{k}",
                    f"ndcg_at_{k}",
                    f"facet_recall_at_{k}",
                    f"all_required_facets_covered_at_{k}",
                )
            },
        }
    keys = [
        "mrr_at_10",
        *(
            key
            for k in ks
            for key in (
                f"precision_at_{k}",
                f"direct_precision_at_{k}",
                f"recall_at_{k}",
                f"hit_rate_at_{k}",
                f"ndcg_at_{k}",
                f"facet_recall_at_{k}",
                f"all_required_facets_covered_at_{k}",
            )
        ),
    ]
    return {
        "evaluated_query_count": len(case_metrics),
        **{
            key: round(
                fsum(float(item[key]) for item in case_metrics) / len(case_metrics),
                12,
            )
            for key in keys
        },
    }


def _family_macro_average(
    case_metrics: Sequence[Mapping[str, object]],
    ks: tuple[int, ...],
) -> tuple[dict[str, object], list[dict[str, object]]]:
    """Average cases within a family, then give every family equal weight."""

    grouped: dict[str, list[Mapping[str, object]]] = defaultdict(list)
    for record in case_metrics:
        grouped[str(record["scenario_family_id"])].append(record)
    per_family = [
        {
            "scenario_family_id": family_id,
            **_macro_average(
                sorted(grouped[family_id], key=lambda item: str(item["case_id"])),
                ks,
            ),
        }
        for family_id in sorted(grouped)
    ]
    family_macro = _macro_average(per_family, ks)
    family_count = int(family_macro.pop("evaluated_query_count"))
    return (
        {
            "evaluated_query_count": len(case_metrics),
            "evaluated_scenario_family_count": family_count,
            **family_macro,
        },
        per_family,
    )


def _percentile_type7(values: Sequence[float], probability: float) -> float:
    """Return the deterministic R/NumPy-style type-7 sample quantile."""

    if not values:
        raise ValueError("a percentile requires at least one value")
    ordered = sorted(values)
    position = (len(ordered) - 1) * probability
    lower_index = floor(position)
    upper_index = min(lower_index + 1, len(ordered) - 1)
    fraction = position - lower_index
    return ordered[lower_index] + fraction * (ordered[upper_index] - ordered[lower_index])


def _family_bootstrap_confidence_intervals(
    per_family: Sequence[Mapping[str, object]],
) -> dict[str, dict[str, float]]:
    """Bootstrap whole scenario families without depending on Python's RNG.

    Family IDs are sorted once. Each replacement draw is the first unsigned
    64-bit big-endian integer of SHA-256(seed|replicate|draw), modulo the family
    count. The same family sample is used for every predeclared headline metric.
    """

    if not per_family:
        raise ValueError("family bootstrap requires at least one scenario family")
    ordered_families = sorted(per_family, key=lambda item: str(item["scenario_family_id"]))
    family_count = len(ordered_families)
    replicates: dict[str, list[float]] = {metric: [] for metric in HEADLINE_METRICS}
    for replicate_index in range(FAMILY_BOOTSTRAP_REPLICATES):
        totals = {metric: 0.0 for metric in HEADLINE_METRICS}
        for draw_index in range(family_count):
            draw_key = (
                f"experiment-d-family-bootstrap-v1|{FAMILY_BOOTSTRAP_SEED}|"
                f"{replicate_index}|{draw_index}"
            ).encode("ascii")
            digest = hashlib.sha256(draw_key).digest()
            family_index = int.from_bytes(digest[:8], "big") % family_count
            selected = ordered_families[family_index]
            for metric in HEADLINE_METRICS:
                totals[metric] += float(selected[metric])
        for metric in HEADLINE_METRICS:
            replicates[metric].append(totals[metric] / family_count)

    tail_probability = (1.0 - FAMILY_BOOTSTRAP_CONFIDENCE_LEVEL) / 2.0
    return {
        metric: {
            "lower": round(_percentile_type7(values, tail_probability), 12),
            "upper": round(_percentile_type7(values, 1.0 - tail_probability), 12),
        }
        for metric, values in replicates.items()
    }


def _family_primary_report(
    primary_case_metrics: Sequence[Mapping[str, object]],
    ks: tuple[int, ...],
) -> dict[str, object]:
    family_metrics, per_family = _family_macro_average(primary_case_metrics, ks)
    confidence_intervals = _family_bootstrap_confidence_intervals(per_family)
    roles = {
        PRIMARY_RANKING_METRIC: "primary_ranking_metric",
        COMPLETENESS_GATE_METRIC: "completeness_gate",
        TOP_CONTEXT_PURITY_DIAGNOSTIC: "top_context_purity_diagnostic",
    }
    return {
        "population": {
            "split": "test",
            "answerability": "fully_answerable",
        },
        "aggregation": "scenario_family_macro_of_within_family_case_macro",
        "metrics": family_metrics,
        "headline_metrics": {
            metric: {
                "role": roles[metric],
                "value": family_metrics[metric],
                "confidence_interval_95": confidence_intervals[metric],
            }
            for metric in HEADLINE_METRICS
        },
        "bootstrap": {
            "resampling_unit": "scenario_family_id",
            "algorithm": FAMILY_BOOTSTRAP_ALGORITHM,
            "seed": FAMILY_BOOTSTRAP_SEED,
            "replicates": FAMILY_BOOTSTRAP_REPLICATES,
            "confidence_level": FAMILY_BOOTSTRAP_CONFIDENCE_LEVEL,
            "interval_method": FAMILY_BOOTSTRAP_INTERVAL_METHOD,
            "family_order": FAMILY_BOOTSTRAP_FAMILY_ORDER,
            "draw_method": FAMILY_BOOTSTRAP_DRAW_METHOD,
            "confidence_intervals": confidence_intervals,
        },
        "per_family": per_family,
    }


def _separate_case_diagnostic(
    case: MetricCase,
    ranking: Sequence[str],
    ks: tuple[int, ...],
) -> dict[str, object]:
    direct_ids = {qrel.provision_id for qrel in case.qrels if qrel.relevance == 2}
    direct_facets_by_id = {
        qrel.provision_id: set(qrel.facet_ids) for qrel in case.qrels if qrel.relevance == 2
    }
    supported_facets = set(case.supported_facet_ids)
    distractors = set(case.distractor_ids)
    direct_ranks = [
        rank for rank, provision_id in enumerate(ranking, 1) if provision_id in direct_ids
    ]
    values: dict[str, object] = {
        "case_id": case.case_id,
        "scenario_family_id": case.scenario_family_id,
        "split": case.split,
        "answerability": case.answerability,
        "grade2_qrel_count": len(direct_ids),
        "supported_facet_count": len(supported_facets),
        "first_grade2_rank": direct_ranks[0] if direct_ranks else None,
    }
    for k in ks:
        top = tuple(ranking[:k])
        retrieved_direct = set(top) & direct_ids
        values[f"grade2_recall_at_{k}"] = (
            len(retrieved_direct) / len(direct_ids) if direct_ids else None
        )
        covered_facets: set[str] = set()
        for provision_id in top:
            covered_facets.update(direct_facets_by_id.get(provision_id, set()))
        values[f"supported_facet_recall_at_{k}"] = (
            len(covered_facets & supported_facets) / len(supported_facets)
            if supported_facets
            else None
        )
        values[f"known_distractor_fraction_at_{k}"] = (
            len(set(top) & distractors) / len(top) if top else 0.0
        )
    return values


def _optional_macro(
    records: Sequence[Mapping[str, object]],
    key: str,
) -> float | None:
    values = [float(record[key]) for record in records if record[key] is not None]
    return round(fsum(values) / len(values), 12) if values else None


def _answerability_diagnostic_report(
    per_case: Sequence[Mapping[str, object]],
    diagnostic_keys: Sequence[str],
) -> dict[str, object]:
    if not per_case:
        return {
            "case_count": 0,
            "status": "not_applicable",
            "core_retrieval_metrics": None,
            "diagnostic_denominators": {
                "grade2_qrel_cases": 0,
                "supported_facet_cases": 0,
                "known_distractor_cases": 0,
            },
            "diagnostics": None,
            "per_case": [],
        }
    return {
        "case_count": len(per_case),
        "status": "diagnostic_only_evidence_gate_pending",
        "core_retrieval_metrics": None,
        "diagnostic_denominators": {
            "grade2_qrel_cases": sum(bool(record["grade2_qrel_count"]) for record in per_case),
            "supported_facet_cases": sum(
                bool(record["supported_facet_count"]) for record in per_case
            ),
            "known_distractor_cases": len(per_case),
        },
        "diagnostics": {key: _optional_macro(per_case, key) for key in diagnostic_keys},
        "per_case": list(per_case),
    }


def _separate_answerability_diagnostics(
    cases: Sequence[MetricCase],
    rankings_by_case: Mapping[str, Sequence[str]],
    ks: tuple[int, ...],
) -> dict[str, object]:
    reports: dict[str, object] = {}
    for status in (
        "partially_answerable",
        "clarification_required",
        "unanswerable",
    ):
        population = [case for case in cases if case.answerability == status]
        per_case = [
            _separate_case_diagnostic(case, rankings_by_case[case.case_id], ks)
            for case in population
        ]
        diagnostic_keys = [
            key
            for k in ks
            for key in (
                f"grade2_recall_at_{k}",
                f"supported_facet_recall_at_{k}",
                f"known_distractor_fraction_at_{k}",
            )
        ]
        report = _answerability_diagnostic_report(per_case, diagnostic_keys)
        report["by_split"] = {
            split: _answerability_diagnostic_report(
                [record for record in per_case if record["split"] == split],
                diagnostic_keys,
            )
            for split in ("calibration", "test")
        }
        reports[status] = report
    return reports


def _fully_answerable_diagnostic(
    case_metrics: Sequence[Mapping[str, object]],
    ks: tuple[int, ...],
    *,
    scope: str,
) -> dict[str, object]:
    if not case_metrics:
        return {
            "status": "not_applicable",
            "scope": scope,
            "metrics": None,
        }
    return {
        "status": "diagnostic_only",
        "scope": scope,
        "metrics": _macro_average(case_metrics, ks),
    }


def _first_direct_rank(case: MetricCase, ranking: Sequence[str]) -> int | None:
    direct_ids = {qrel.provision_id for qrel in case.qrels if qrel.relevance == 2}
    return next(
        (rank for rank, provision_id in enumerate(ranking[:10], 1) if provision_id in direct_ids),
        None,
    )


def _control_pair_diagnostics(
    cases: Sequence[MetricCase],
    rankings_by_case: Mapping[str, Sequence[str]],
) -> dict[str, object]:
    groups: dict[str, list[MetricCase]] = defaultdict(list)
    for case in cases:
        if case.control_pair_id is not None:
            groups[case.control_pair_id].append(case)
    if not groups:
        return {
            "status": "not_applicable",
            "pair_count": 0,
            "relation_met_rate": None,
            "mean_absolute_reciprocal_rank_delta": None,
            "mean_top10_jaccard": None,
            "pairs": [],
        }
    pair_records: list[dict[str, object]] = []
    for pair_id, pair_cases in sorted(groups.items()):
        if len(pair_cases) != 2:
            raise ValueError(f"control pair {pair_id} must contain exactly two cases")
        first, second = sorted(pair_cases, key=lambda item: item.case_id)
        if first.control_pair_expectation != second.control_pair_expectation:
            raise ValueError("control pair expectations must match")
        first_ranking = tuple(rankings_by_case[first.case_id][:10])
        second_ranking = tuple(rankings_by_case[second.case_id][:10])
        first_rank = _first_direct_rank(first, first_ranking)
        second_rank = _first_direct_rank(second, second_ranking)
        first_rr = 1.0 / first_rank if first_rank is not None else 0.0
        second_rr = 1.0 / second_rank if second_rank is not None else 0.0
        union = set(first_ranking) | set(second_ranking)
        jaccard = len(set(first_ranking) & set(second_ranking)) / len(union) if union else 1.0
        expectation = first.control_pair_expectation
        relation_met: bool | None
        if expectation in {"same_direct_evidence", "different_direct_evidence"}:
            relation_met = first_rank is not None and second_rank is not None
        else:
            relation_met = None
        pair_records.append(
            {
                "control_pair_id": pair_id,
                "expectation": expectation,
                "case_ids": [first.case_id, second.case_id],
                "first_grade2_ranks": [first_rank, second_rank],
                "absolute_reciprocal_rank_delta": abs(first_rr - second_rr),
                "top10_jaccard": jaccard,
                "same_top1": bool(first_ranking and second_ranking)
                and first_ranking[0] == second_ranking[0],
                "relation_met": relation_met,
            }
        )
    applicable_relation_values = [
        float(record["relation_met"])
        for record in pair_records
        if record["relation_met"] is not None
    ]
    return {
        "status": "descriptive_control_diagnostics",
        "pair_count": len(pair_records),
        "relation_met_rate": (
            round(fsum(applicable_relation_values) / len(applicable_relation_values), 12)
            if applicable_relation_values
            else None
        ),
        "mean_absolute_reciprocal_rank_delta": round(
            fsum(float(record["absolute_reciprocal_rank_delta"]) for record in pair_records)
            / len(pair_records),
            12,
        ),
        "mean_top10_jaccard": round(
            fsum(float(record["top10_jaccard"]) for record in pair_records) / len(pair_records),
            12,
        ),
        "pairs": pair_records,
    }


def evaluate_dense_retrieval(
    cases: Sequence[MetricCase],
    rankings_by_case: Mapping[str, Sequence[str]],
    *,
    ks: tuple[int, ...] = DEFAULT_KS,
) -> dict[str, object]:
    """Use held-out fully-answerable cases as primary.

    Report all other aggregates as diagnostics.
    """

    if (
        not ks
        or tuple(sorted(set(ks))) != ks
        or any(k <= 0 for k in ks)
        or 5 not in ks
        or ks[-1] != 10
    ):
        raise ValueError(
            "metric cutoffs must be unique positive integers in ascending order "
            "including 5 and ending at 10"
        )
    case_ids = [case.case_id for case in cases]
    if len(set(case_ids)) != len(case_ids):
        raise ValueError("metric cases must have unique IDs")
    if any(not case.scenario_family_id for case in cases):
        raise ValueError("metric cases must have non-empty scenario family IDs")
    family_splits: dict[str, set[str]] = defaultdict(set)
    for case in cases:
        family_splits[case.scenario_family_id].add(case.split)
    if any(len(splits) != 1 for splits in family_splits.values()):
        raise ValueError("scenario families cannot cross calibration and test splits")
    ranking_ids = set(rankings_by_case)
    expected_ids = set(case_ids)
    if ranking_ids != expected_ids:
        missing = sorted(expected_ids - ranking_ids)
        extra = sorted(ranking_ids - expected_ids)
        raise ValueError(f"rankings do not match cases: missing={missing[:5]}, extra={extra[:5]}")
    validated_rankings = {
        case_id: _validate_ranking(rankings_by_case[case_id]) for case_id in sorted(expected_ids)
    }

    fully_answerable = [case for case in cases if case.answerability == "fully_answerable"]
    primary_cases = [case for case in fully_answerable if case.split == "test"]
    if not primary_cases:
        raise ValueError("primary retrieval metrics require held-out test fully_answerable cases")
    per_case = [
        _case_metrics(case, validated_rankings[case.case_id], ks) for case in fully_answerable
    ]
    by_split = {
        split: _macro_average(
            [item for item in per_case if item["split"] == split],
            ks,
        )
        for split in ("calibration", "test")
    }
    primary = by_split["test"]
    primary_case_metrics = [item for item in per_case if item["split"] == "test"]
    family_primary = _family_primary_report(primary_case_metrics, ks)
    diagnostic_aggregates = {
        "calibration_fully_answerable": _fully_answerable_diagnostic(
            [item for item in per_case if item["split"] == "calibration"],
            ks,
            scope="calibration_fully_answerable",
        ),
        "combined_fully_answerable": _fully_answerable_diagnostic(
            per_case,
            ks,
            scope="calibration_and_test_fully_answerable",
        ),
    }
    boundary_types = sorted(
        {case.boundary_type for case in primary_cases if case.boundary_type is not None}
    )
    metrics_by_id = {str(item["case_id"]): item for item in per_case}
    by_boundary_type = {
        boundary_type: _macro_average(
            [
                metrics_by_id[case.case_id]
                for case in primary_cases
                if case.boundary_type == boundary_type
            ],
            ks,
        )
        for boundary_type in boundary_types
    }
    separate_answerability = _separate_answerability_diagnostics(
        cases,
        validated_rankings,
        ks,
    )
    control_pairs = _control_pair_diagnostics(cases, validated_rankings)
    return {
        "population_policy": "held_out_test_fully_answerable_primary",
        "cutoffs": list(ks),
        "primary_population": {
            "split": "test",
            "answerability": "fully_answerable",
        },
        "primary": primary,
        "primary_semantics": "backward_compatible_held_out_test_case_macro",
        "overall": primary,
        "overall_semantics": "backward_compatible_alias_of_primary",
        "reporting_primary_key": "family_primary",
        "family_primary": family_primary,
        "diagnostic_aggregates": diagnostic_aggregates,
        "by_split": by_split,
        "by_split_semantics": {
            "calibration": "diagnostic_only",
            "test": "primary",
        },
        "by_boundary_type": by_boundary_type,
        "by_boundary_type_scope": "held_out_test_fully_answerable",
        "separate_answerability_counts": {
            status: item["case_count"] for status, item in separate_answerability.items()
        },
        "separate_answerability_counts_by_split": {
            split: {
                status: item["by_split"][split]["case_count"]
                for status, item in separate_answerability.items()
            }
            for split in ("calibration", "test")
        },
        "separate_answerability": separate_answerability,
        "control_pair_count": control_pairs["pair_count"],
        "control_pair_diagnostics": control_pairs,
        "per_case": per_case,
    }


__all__ = [
    "COMPLETENESS_GATE_METRIC",
    "DEFAULT_KS",
    "FAMILY_BOOTSTRAP_ALGORITHM",
    "FAMILY_BOOTSTRAP_CONFIDENCE_LEVEL",
    "FAMILY_BOOTSTRAP_REPLICATES",
    "FAMILY_BOOTSTRAP_SEED",
    "HEADLINE_METRICS",
    "MetricCase",
    "MetricQrel",
    "PRIMARY_RANKING_METRIC",
    "TOP_CONTEXT_PURITY_DIAGNOSTIC",
    "evaluate_dense_retrieval",
    "metric_cases_from_gold",
]
