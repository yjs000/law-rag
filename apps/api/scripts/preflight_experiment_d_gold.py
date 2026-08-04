"""Read-only preflight for the future Experiment D gold evaluation runner.

This command is read-only.  It compares the frozen question/qrel metadata with
the current searchable corpus and never embeds a question or calls search.  A
runner must repeat this audit while holding the corpus read lock for the whole
retrieval window; this standalone command is not that runtime lock.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import sys
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path
from typing import Any

from law_rag_core.domain.identifiers import PARSER_SCHEMA_VERSION
from pydantic import ValidationError

from app.adapters.postgres_repository import PostgresLegalRepository
from app.domain.corpus_temporal_contract import canonical_corpus_population_fingerprint
from app.domain.embedding_profiles import embedding_text_sha256, legal_provision_embedding_text
from app.settings import get_settings
from scripts.experiment_d_corpus import SourceProvision, load_provisions
from scripts.experiment_d_gold_contract import (
    ExperimentDGoldAdjudicationManifest,
    ExperimentDGoldDataset,
    ExperimentDQuestionApprovalManifest,
    canonical_gold_case_payload_sha256,
    canonical_gold_corpus_snapshot_id,
    canonical_gold_dataset_sha256,
)
from scripts.experiment_d_question_identity import (
    APPROVAL_SCOPE_FIELDS,
    question_scope_set_sha256,
    question_scope_sha256,
)

APPROVED_GOLD_STATUS = "approved_gold"
DEFAULT_SOURCE_BANK = (
    Path(__file__).parents[1] / "evaluation" / "experiment-d-lay-energy-query-bank-v1-draft.json"
)
DEFAULT_APPROVAL_MANIFEST = (
    Path(__file__).parents[1] / "evaluation" / "experiment-d-lay-energy-question-approval-v1.json"
)
DEFAULT_ADJUDICATION_MANIFEST = (
    Path(__file__).parents[1] / "evaluation" / "experiment-d-lay-energy-gold-adjudication-v1.json"
)


class NonCurrentParserIdError(ValueError):
    """Raised before gold validation when an ID is absent from the current parser corpus."""

    def __init__(self, provision_ids: Sequence[str]) -> None:
        unique_ids = tuple(sorted(set(provision_ids)))
        self.parser_contract_version = PARSER_SCHEMA_VERSION
        self.count = len(unique_ids)
        self.sample = unique_ids[:10]
        super().__init__(
            "non_current_parser_provision_ids: "
            f"expected_parser={PARSER_SCHEMA_VERSION}, count={self.count}, "
            f"sample={','.join(self.sample)}"
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "code": "non_current_parser_provision_ids",
            "expected_parser_contract_version": self.parser_contract_version,
            "count": self.count,
            "sample": list(self.sample),
        }


def _linked_provision_ids(value: object) -> set[str]:
    linked: set[str] = set()
    if isinstance(value, Mapping):
        for key, nested in value.items():
            if key == "provision_id" and isinstance(nested, str) and nested:
                linked.add(nested)
            elif key.endswith("_provision_ids") and isinstance(nested, list):
                linked.update(item for item in nested if isinstance(item, str) and item)
            else:
                linked.update(_linked_provision_ids(nested))
    elif isinstance(value, list):
        for nested in value:
            linked.update(_linked_provision_ids(nested))
    return linked


def require_current_parser_ids(
    dataset: Mapping[str, object],
    provisions: Sequence[SourceProvision],
) -> None:
    """Fail immediately if any evaluation link is not in the current parser corpus."""

    current_ids = {provision.provision_id for provision in provisions}
    non_current_ids = _linked_provision_ids(dataset) - current_ids
    if non_current_ids:
        raise NonCurrentParserIdError(tuple(non_current_ids))


@dataclass(frozen=True, slots=True)
class AsOfPopulationFingerprint:
    as_of_date: str
    eligible_provision_count: int
    fingerprint_sha256: str


@dataclass(frozen=True, slots=True)
class GoldPreflightReport:
    ready: bool
    reasons: tuple[str, ...]
    corpus_search_ready: bool
    corpus_search_ready_reason: str | None
    dataset_version: str | None
    evaluation_status: str | None
    case_count: int
    qrel_count: int
    unique_qrel_count: int
    missing_qrel_count: int
    changed_qrel_count: int
    metadata_mismatch_count: int
    missing_judged_candidate_count: int
    missing_pool_candidate_count: int
    qrel_not_effective_as_of_count: int
    distractor_not_effective_as_of_count: int
    pool_candidate_not_effective_as_of_count: int
    full_corpus_pool_mismatch_count: int
    missing_qrel_sample: tuple[str, ...]
    changed_qrel_sample: tuple[str, ...]
    missing_judged_candidate_sample: tuple[str, ...]
    missing_pool_candidate_sample: tuple[str, ...]
    qrel_not_effective_as_of_sample: tuple[str, ...]
    distractor_not_effective_as_of_sample: tuple[str, ...]
    pool_candidate_not_effective_as_of_sample: tuple[str, ...]
    full_corpus_pool_mismatch_sample: tuple[str, ...]
    gold_contract_valid: bool
    gold_contract_error_count: int
    gold_contract_error_sample: tuple[str, ...]
    source_bank_binding_valid: bool
    approval_manifest_valid: bool
    approval_manifest_contract_error_count: int
    approval_manifest_contract_error_sample: tuple[str, ...]
    adjudication_manifest_valid: bool
    adjudication_manifest_contract_error_count: int
    adjudication_manifest_contract_error_sample: tuple[str, ...]
    adjudication_manifest_error_count: int
    adjudication_manifest_error_sample: tuple[str, ...]
    declared_gold_dataset_sha256: str | None
    calculated_gold_dataset_sha256: str | None
    declared_question_set_sha256: str | None
    calculated_question_set_sha256: str | None
    declared_question_scope_set_sha256: str | None
    calculated_question_scope_set_sha256: str | None
    declared_corpus_snapshot_id: str | None
    current_corpus_snapshot_id: str | None
    declared_as_of_populations: tuple[AsOfPopulationFingerprint, ...]
    current_as_of_populations: tuple[AsOfPopulationFingerprint, ...]
    as_of_population_mismatch_count: int
    as_of_population_mismatch_sample: tuple[str, ...]
    declared_parser_contract_version: str | None
    current_parser_contract_version: str
    current_stored_searchable_provision_count: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "실험 D gold의 승인 상태·질문 해시·qrels·기준일별 corpus 해시를 "
            "검색 실행 전에 읽기 전용으로 검증"
        )
    )
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--source-bank", type=Path, default=DEFAULT_SOURCE_BANK)
    parser.add_argument("--approval-manifest", type=Path, default=DEFAULT_APPROVAL_MANIFEST)
    parser.add_argument(
        "--adjudication-manifest",
        type=Path,
        default=DEFAULT_ADJUDICATION_MANIFEST,
    )
    return parser.parse_args()


def eligible_population_fingerprint_sha256(
    provisions: Sequence[SourceProvision],
) -> str:
    """Hash content identity for one already-filtered as-of population.

    ``effective_to`` is intentionally excluded.  Closing an existing version
    when a later version is collected must not change an earlier date's
    population identity when the eligible IDs and source content are unchanged.
    """

    rows = [
        [
            PARSER_SCHEMA_VERSION,
            item.document_id,
            item.version_id,
            item.provision_id,
            item.document_title,
            item.source_kind,
            item.effective_from.isoformat(),
            item.path,
            item.parent_path,
            item.heading,
            item.content_sha256,
        ]
        for item in provisions
    ]
    return canonical_corpus_population_fingerprint(rows)


def as_of_population_fingerprints(
    provisions: Sequence[SourceProvision],
    as_of_dates: Sequence[date],
) -> tuple[AsOfPopulationFingerprint, ...]:
    """Return deterministic fingerprints for each date's searchable population."""

    populations: list[AsOfPopulationFingerprint] = []
    for as_of_date in sorted(set(as_of_dates)):
        eligible = [
            provision for provision in provisions if _is_effective_at(provision, as_of_date)
        ]
        populations.append(
            AsOfPopulationFingerprint(
                as_of_date=as_of_date.isoformat(),
                eligible_provision_count=len(eligible),
                fingerprint_sha256=eligible_population_fingerprint_sha256(eligible),
            )
        )
    return tuple(populations)


def question_set_sha256(cases: Sequence[Mapping[str, object]]) -> str | None:
    frozen: list[dict[str, str]] = []
    for case in cases:
        case_id = case.get("id")
        question = case.get("question", case.get("user_input"))
        if not isinstance(case_id, str) or not case_id or not isinstance(question, str):
            return None
        frozen.append({"id": case_id, "question": question})
    return hashlib.sha256(
        json.dumps(
            frozen,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()


def _declared_question_set_sha256(dataset: Mapping[str, object]) -> str | None:
    direct = dataset.get("question_set_sha256")
    if isinstance(direct, str):
        return direct
    source_bank = dataset.get("source_bank")
    if isinstance(source_bank, Mapping):
        value = source_bank.get("question_set_sha256")
        if isinstance(value, str):
            return value
    return None


def _declared_corpus_snapshot_id(dataset: Mapping[str, object]) -> str | None:
    snapshot = dataset.get("corpus_snapshot")
    if not isinstance(snapshot, Mapping):
        return None
    value = snapshot.get("snapshot_id")
    return value if isinstance(value, str) else None


def _declared_as_of_populations(
    dataset: Mapping[str, object],
) -> tuple[AsOfPopulationFingerprint, ...]:
    snapshot = dataset.get("corpus_snapshot")
    raw_populations = snapshot.get("as_of_populations") if isinstance(snapshot, Mapping) else None
    if not isinstance(raw_populations, list):
        return ()
    populations: list[AsOfPopulationFingerprint] = []
    for raw in raw_populations:
        if not isinstance(raw, Mapping):
            continue
        raw_date = raw.get("as_of_date")
        count = raw.get("eligible_provision_count")
        fingerprint = raw.get("fingerprint_sha256")
        if (
            not isinstance(raw_date, str)
            or isinstance(count, bool)
            or not isinstance(count, int)
            or not isinstance(fingerprint, str)
        ):
            continue
        populations.append(
            AsOfPopulationFingerprint(
                as_of_date=raw_date,
                eligible_provision_count=count,
                fingerprint_sha256=fingerprint,
            )
        )
    return tuple(sorted(populations, key=lambda item: item.as_of_date))


def _source_bank_binding_errors(
    dataset: Mapping[str, object],
    source_bank: Mapping[str, object] | None,
    approval_manifest: Mapping[str, object] | None,
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    unavailable_approval_reason = (
        "approval_manifest_missing"
        if approval_manifest is None
        else "approval_manifest_unverifiable"
    )
    if source_bank is None:
        return ("source_bank_missing",), (unavailable_approval_reason,)
    raw_questions = source_bank.get("questions")
    if not isinstance(raw_questions, list) or any(
        not isinstance(item, Mapping) for item in raw_questions
    ):
        return ("source_bank_questions_invalid",), (unavailable_approval_reason,)
    bank_questions = [item for item in raw_questions if isinstance(item, Mapping)]
    calculated_bank_hash = question_set_sha256(bank_questions)
    declared_bank_hash = source_bank.get("question_set_sha256")
    if calculated_bank_hash is None or calculated_bank_hash != declared_bank_hash:
        return ("source_bank_self_hash_mismatch",), (unavailable_approval_reason,)
    calculated_scope_hash = question_scope_set_sha256(bank_questions)
    declared_scope_hash = source_bank.get("question_scope_set_sha256")
    if calculated_scope_hash is None or calculated_scope_hash != declared_scope_hash:
        return ("source_bank_scope_hash_mismatch",), (unavailable_approval_reason,)

    binding = dataset.get("source_bank")
    if not isinstance(binding, Mapping):
        return ("gold_source_bank_binding_missing",), (unavailable_approval_reason,)
    expected_binding = {
        "bank_version": source_bank.get("bank_version"),
        "question_count": source_bank.get("question_count"),
        "question_set_sha256": declared_bank_hash,
        "question_scope_set_sha256": declared_scope_hash,
    }
    errors: set[str] = set()
    for key, expected in expected_binding.items():
        if binding.get(key) != expected:
            errors.add("gold_source_bank_binding_mismatch")

    raw_cases = dataset.get("cases")
    if not isinstance(raw_cases, list):
        return tuple(sorted(errors | {"gold_cases_missing"})), (unavailable_approval_reason,)
    gold_by_id = {
        str(case.get("id")): case
        for case in raw_cases
        if isinstance(case, Mapping) and case.get("id") is not None
    }
    if len(gold_by_id) != len(bank_questions):
        errors.add("gold_source_bank_question_count_mismatch")
    for bank_case in bank_questions:
        case_id = bank_case.get("id")
        gold_case = gold_by_id.get(str(case_id))
        if gold_case is None:
            errors.add("gold_source_bank_question_missing")
            continue
        if gold_case.get("question") != bank_case.get("question"):
            errors.add("gold_source_bank_question_text_mismatch")
        if gold_case.get("question_sha256") != bank_case.get("question_sha256"):
            errors.add("gold_source_bank_question_hash_mismatch")
        if gold_case.get("question_review_status") != "approved":
            errors.add("gold_source_bank_question_unapproved")
        for field in APPROVAL_SCOPE_FIELDS:
            if gold_case.get(field) != bank_case.get(field):
                errors.add("gold_source_bank_question_scope_mismatch")

    approval_errors: set[str] = set()
    if approval_manifest is None:
        approval_errors.add("approval_manifest_missing")
    else:
        if approval_manifest.get("status") != "approved":
            approval_errors.add("approval_manifest_not_approved")
        approved_source = approval_manifest.get("source_bank")
        if not isinstance(approved_source, Mapping):
            approval_errors.add("approval_manifest_source_bank_missing")
        else:
            for key, expected in expected_binding.items():
                if approved_source.get(key) != expected:
                    approval_errors.add("approval_manifest_source_bank_mismatch")
        reviews = approval_manifest.get("questions")
        if not isinstance(reviews, list):
            approval_errors.add("approval_manifest_questions_invalid")
        else:
            review_by_id = {
                str(review.get("id")): review
                for review in reviews
                if isinstance(review, Mapping) and review.get("id") is not None
            }
            if len(review_by_id) != len(bank_questions):
                approval_errors.add("approval_manifest_question_count_mismatch")
            for bank_case in bank_questions:
                review = review_by_id.get(str(bank_case.get("id")))
                if review is None:
                    approval_errors.add("approval_manifest_question_missing")
                    continue
                if review.get("status") != "approved":
                    approval_errors.add("approval_manifest_question_unapproved")
                if review.get("question_sha256") != bank_case.get("question_sha256"):
                    approval_errors.add("approval_manifest_question_hash_mismatch")
                if review.get("question_scope_sha256") != question_scope_sha256(bank_case):
                    approval_errors.add("approval_manifest_question_scope_hash_mismatch")
        approval_sha = hashlib.sha256(
            json.dumps(
                approval_manifest,
                ensure_ascii=False,
                separators=(",", ":"),
                sort_keys=True,
            ).encode("utf-8")
        ).hexdigest()
        if binding.get("approval_manifest_sha256") != approval_sha:
            approval_errors.add("gold_approval_manifest_hash_mismatch")
    return tuple(sorted(errors)), tuple(sorted(approval_errors))


def gold_adjudication_manifest_errors(
    dataset: ExperimentDGoldDataset,
    question_approval: ExperimentDQuestionApprovalManifest,
    adjudication_manifest: ExperimentDGoldAdjudicationManifest,
) -> tuple[str, ...]:
    """Return deterministic cross-artifact errors for the sealed gold decision."""

    errors: set[str] = set()
    if adjudication_manifest.dataset_sha256 != canonical_gold_dataset_sha256(dataset):
        errors.add("adjudication_dataset_hash_mismatch")

    manifest_by_case = {case.case_id: case for case in adjudication_manifest.cases}
    dataset_by_case = {case.id: case for case in dataset.cases}
    if set(manifest_by_case) != set(dataset_by_case):
        errors.add("adjudication_case_set_mismatch")

    for case_id, case in dataset_by_case.items():
        sealed_case = manifest_by_case.get(case_id)
        if sealed_case is None:
            continue
        if sealed_case.case_payload_sha256 != canonical_gold_case_payload_sha256(case):
            errors.add(f"adjudication_case_payload_hash_mismatch:{case_id}")
        if not question_approval.approved_at < case.annotation_review.reviewed_at:
            errors.add(f"case_review_not_after_question_approval:{case_id}")
        if not case.annotation_review.reviewed_at < adjudication_manifest.approved_at:
            errors.add(f"gold_adjudication_not_after_case_review:{case_id}")
    return tuple(sorted(errors))


def _reason_code(error: str) -> str:
    return error.split(":", maxsplit=1)[0]


def _is_effective_at(provision: SourceProvision, as_of_date: date) -> bool:
    return provision.effective_from <= as_of_date and (
        provision.effective_to is None or as_of_date < provision.effective_to
    )


def audit_gold_dataset(
    dataset: Mapping[str, object],
    provisions: Sequence[SourceProvision],
    source_bank: Mapping[str, object] | None = None,
    approval_manifest: Mapping[str, object] | None = None,
    adjudication_manifest: Mapping[str, object] | None = None,
    *,
    corpus_search_ready: bool = True,
    corpus_search_ready_reason: str | None = None,
) -> GoldPreflightReport:
    require_current_parser_ids(dataset, provisions)
    reasons: set[str] = set()
    if not corpus_search_ready:
        reasons.add("corpus_search_unready")
    contract_errors: tuple[str, ...] = ()
    approval_contract_errors: tuple[str, ...] = ()
    adjudication_contract_errors: tuple[str, ...] = ()
    adjudication_errors: tuple[str, ...] = ()
    validated_dataset: ExperimentDGoldDataset | None = None
    validated_approval: ExperimentDQuestionApprovalManifest | None = None
    validated_adjudication: ExperimentDGoldAdjudicationManifest | None = None
    try:
        validated_dataset = ExperimentDGoldDataset.model_validate(dataset)
    except ValidationError as error:
        contract_errors = tuple(
            f"{'.'.join(str(part) for part in item['loc'])}:{item['type']}"
            for item in error.errors(include_url=False, include_input=False)
        )
        reasons.add("gold_contract_invalid")
    if approval_manifest is not None:
        try:
            validated_approval = ExperimentDQuestionApprovalManifest.model_validate(
                approval_manifest
            )
        except ValidationError as error:
            approval_contract_errors = tuple(
                f"{'.'.join(str(part) for part in item['loc'])}:{item['type']}"
                for item in error.errors(include_url=False, include_input=False)
            )
            reasons.add("approval_manifest_contract_invalid")
    if adjudication_manifest is None:
        reasons.add("adjudication_manifest_missing")
    else:
        try:
            validated_adjudication = ExperimentDGoldAdjudicationManifest.model_validate(
                adjudication_manifest
            )
        except ValidationError as error:
            adjudication_contract_errors = tuple(
                f"{'.'.join(str(part) for part in item['loc'])}:{item['type']}"
                for item in error.errors(include_url=False, include_input=False)
            )
            reasons.add("adjudication_manifest_contract_invalid")
    if (
        validated_dataset is not None
        and validated_approval is not None
        and validated_adjudication is not None
    ):
        adjudication_errors = gold_adjudication_manifest_errors(
            validated_dataset,
            validated_approval,
            validated_adjudication,
        )
        reasons.update(_reason_code(error) for error in adjudication_errors)
    source_binding_errors, approval_errors = _source_bank_binding_errors(
        dataset, source_bank, approval_manifest
    )
    reasons.update(source_binding_errors)
    reasons.update(approval_errors)
    evaluation_status = dataset.get("evaluation_status")
    if evaluation_status != APPROVED_GOLD_STATUS:
        reasons.add("dataset_not_approved_gold")

    raw_cases = dataset.get("cases")
    if not isinstance(raw_cases, list) or not raw_cases:
        raw_cases = []
        reasons.add("invalid_or_empty_cases")
    cases = [case for case in raw_cases if isinstance(case, Mapping)]
    if len(cases) != len(raw_cases):
        reasons.add("invalid_case_shape")

    declared_question_hash = _declared_question_set_sha256(dataset)
    calculated_question_hash = question_set_sha256(cases)
    if declared_question_hash is None:
        reasons.add("question_set_hash_missing")
    elif calculated_question_hash != declared_question_hash:
        reasons.add("question_set_hash_mismatch")
    binding = dataset.get("source_bank")
    declared_scope_hash = (
        binding.get("question_scope_set_sha256") if isinstance(binding, Mapping) else None
    )
    calculated_scope_hash = question_scope_set_sha256(cases)
    if declared_scope_hash is None:
        reasons.add("question_scope_set_hash_missing")
    elif calculated_scope_hash != declared_scope_hash:
        reasons.add("question_scope_set_hash_mismatch")

    snapshot = dataset.get("corpus_snapshot")
    declared_parser_version = (
        snapshot.get("parser_contract_version") if isinstance(snapshot, Mapping) else None
    )
    if declared_parser_version != PARSER_SCHEMA_VERSION:
        reasons.add("parser_contract_version_mismatch")

    declared_snapshot_id = _declared_corpus_snapshot_id(dataset)
    declared_populations = _declared_as_of_populations(dataset)
    current_populations: tuple[AsOfPopulationFingerprint, ...] = ()
    current_snapshot_id: str | None = None
    population_mismatches: set[str] = set()
    if validated_dataset is not None:
        as_of_dates = [
            population.as_of_date
            for population in validated_dataset.corpus_snapshot.as_of_populations
        ]
        current_populations = as_of_population_fingerprints(provisions, as_of_dates)
        declared_by_date = {
            population.as_of_date: population for population in declared_populations
        }
        current_by_date = {population.as_of_date: population for population in current_populations}
        for as_of_date in sorted(set(declared_by_date) | set(current_by_date)):
            declared = declared_by_date.get(as_of_date)
            current = current_by_date.get(as_of_date)
            if declared is None or current is None:
                population_mismatches.add(f"{as_of_date}:population_missing")
                continue
            if declared.eligible_provision_count != current.eligible_provision_count:
                population_mismatches.add(f"{as_of_date}:count")
            if declared.fingerprint_sha256 != current.fingerprint_sha256:
                population_mismatches.add(f"{as_of_date}:fingerprint")
        if any(item.endswith(":count") for item in population_mismatches):
            reasons.add("as_of_population_count_mismatch")
        if any(item.endswith(":fingerprint") for item in population_mismatches):
            reasons.add("as_of_population_fingerprint_mismatch")
        if any(item.endswith(":population_missing") for item in population_mismatches):
            reasons.add("as_of_population_date_mismatch")
        current_snapshot_id = canonical_gold_corpus_snapshot_id(
            parser_contract_version=PARSER_SCHEMA_VERSION,
            retrieval_unit="provision",
            as_of_populations=[asdict(population) for population in current_populations],
        )
        if declared_snapshot_id != current_snapshot_id:
            reasons.add("corpus_snapshot_id_mismatch")

    # Both qrels and the complete judgment pool must be checked against the
    # full runtime-searchable population.  Dataset-generation evidence
    # heuristics intentionally do not participate in this map: a human-approved
    # gold qrel or distractor can legitimately use a flat ``본문/단락1`` path.
    all_searchable_by_id = {item.provision_id: item for item in provisions}
    qrel_count = 0
    qrel_ids: set[str] = set()
    missing_ids: set[str] = set()
    changed_ids: set[str] = set()
    metadata_mismatches: set[tuple[str, str]] = set()
    missing_judged_candidate_ids: set[str] = set()
    missing_pool_candidates: set[str] = set()
    qrels_not_effective_as_of: set[str] = set()
    distractors_not_effective_as_of: set[str] = set()
    pool_candidates_not_effective_as_of: set[str] = set()
    full_corpus_pool_mismatches: set[str] = set()

    if validated_dataset is not None:
        pool_method_kinds = {
            method.method_id: method.kind
            for method in validated_dataset.annotation_protocol.pool_methods
        }
        for validated_case in validated_dataset.cases:
            effective_population = {
                provision_id
                for provision_id, provision in all_searchable_by_id.items()
                if _is_effective_at(provision, validated_case.as_of_date)
            }
            for provision_id in validated_case.judgment_coverage.distractor_provision_ids:
                provision = all_searchable_by_id.get(provision_id)
                if provision is not None and not _is_effective_at(
                    provision, validated_case.as_of_date
                ):
                    distractors_not_effective_as_of.add(f"{validated_case.id}:{provision_id}")
            for pool in validated_case.judgment_coverage.pool_method_candidates:
                for provision_id in pool.candidate_provision_ids:
                    provision = all_searchable_by_id.get(provision_id)
                    candidate_identity = f"{validated_case.id}:{pool.method_id}:{provision_id}"
                    if provision is None:
                        missing_pool_candidates.add(candidate_identity)
                    elif not _is_effective_at(provision, validated_case.as_of_date):
                        pool_candidates_not_effective_as_of.add(candidate_identity)
                if (
                    pool_method_kinds[pool.method_id] == "full_corpus_manual_review"
                    and set(pool.candidate_provision_ids) != effective_population
                ):
                    full_corpus_pool_mismatches.add(f"{validated_case.id}:{pool.method_id}")

    for case in cases:
        case_id = case.get("id")
        raw_as_of_date = case.get("as_of_date")
        try:
            case_as_of_date = (
                date.fromisoformat(raw_as_of_date)
                if isinstance(raw_as_of_date, str)
                else raw_as_of_date
                if isinstance(raw_as_of_date, date)
                else None
            )
        except ValueError:
            case_as_of_date = None
        qrels = case.get("qrels")
        if not isinstance(qrels, list):
            reasons.add("invalid_qrels_shape")
            continue
        answerability = case.get("answerability")
        legacy_answerable = case.get("answerable")
        if answerability == "unanswerable" and qrels:
            reasons.add("unanswerable_case_has_qrels")
        if legacy_answerable is False and qrels:
            reasons.add("unanswerable_case_has_qrels")
        if answerability in {"fully_answerable", "partially_answerable"} and not qrels:
            reasons.add("answerable_case_has_no_qrels")
        if legacy_answerable is True and not qrels:
            reasons.add("answerable_case_has_no_qrels")
        judgment_coverage = case.get("judgment_coverage")
        if isinstance(judgment_coverage, Mapping):
            judged_candidate_ids = judgment_coverage.get("judged_candidate_provision_ids")
            if isinstance(judged_candidate_ids, list) and all(
                isinstance(item, str) and item for item in judged_candidate_ids
            ):
                missing_judged_candidate_ids.update(
                    item for item in judged_candidate_ids if item not in all_searchable_by_id
                )
            else:
                reasons.add("invalid_judged_candidate_ids")
        else:
            reasons.add("judgment_coverage_missing")
        for qrel in qrels:
            qrel_count += 1
            if not isinstance(qrel, Mapping):
                reasons.add("invalid_qrel_shape")
                continue
            provision_id = qrel.get("provision_id")
            source_sha = qrel.get("content_sha256")
            relevance = qrel.get("relevance")
            if not isinstance(provision_id, str) or not provision_id:
                reasons.add("invalid_qrel_identity")
                continue
            qrel_ids.add(provision_id)
            if relevance not in {1, 2}:
                reasons.add("invalid_qrel_relevance")
            source = all_searchable_by_id.get(provision_id)
            if source is None:
                missing_ids.add(provision_id)
                continue
            if case_as_of_date is not None and not _is_effective_at(source, case_as_of_date):
                qrels_not_effective_as_of.add(f"{case_id}:{provision_id}")
            if source_sha != source.content_sha256:
                changed_ids.add(provision_id)
            passage_sha = qrel.get("passage_text_sha256")
            if passage_sha is not None:
                current_passage_sha = embedding_text_sha256(
                    legal_provision_embedding_text(
                        document_title=source.document_title,
                        path=source.path,
                        heading=source.heading,
                        content=source.content,
                    )
                )
                if passage_sha != current_passage_sha:
                    metadata_mismatches.add((provision_id, "passage_text_sha256"))
            expected_metadata = {
                "document_id": source.document_id,
                "version_id": source.version_id,
                "path": source.path,
                "heading": source.heading,
                "effective_from": source.effective_from.isoformat(),
            }
            for field, expected_value in expected_metadata.items():
                declared_value = qrel.get(field)
                if field in qrel and str(declared_value) != str(expected_value):
                    metadata_mismatches.add((provision_id, field))

    if not qrel_count:
        reasons.add("dataset_has_no_qrels")
    if missing_ids:
        reasons.add("qrel_source_missing")
    if changed_ids:
        reasons.add("qrel_source_changed")
    if metadata_mismatches:
        reasons.add("qrel_metadata_mismatch")
    if missing_judged_candidate_ids:
        reasons.add("judged_candidate_source_missing")
    if missing_pool_candidates:
        reasons.add("pool_candidate_source_missing")
    if qrels_not_effective_as_of:
        reasons.add("qrel_not_effective_as_of")
    if distractors_not_effective_as_of:
        reasons.add("distractor_not_effective_as_of")
    if pool_candidates_not_effective_as_of:
        reasons.add("pool_candidate_not_effective_as_of")
    if full_corpus_pool_mismatches:
        reasons.add("full_corpus_pool_mismatch")

    declared_gold_dataset_sha256 = (
        adjudication_manifest.get("dataset_sha256")
        if isinstance(adjudication_manifest, Mapping)
        and isinstance(adjudication_manifest.get("dataset_sha256"), str)
        else None
    )
    calculated_gold_dataset_sha256 = (
        canonical_gold_dataset_sha256(validated_dataset) if validated_dataset is not None else None
    )

    dataset_version = dataset.get("dataset_version", dataset.get("bank_version"))
    return GoldPreflightReport(
        ready=not reasons,
        reasons=tuple(sorted(reasons)),
        corpus_search_ready=corpus_search_ready,
        corpus_search_ready_reason=corpus_search_ready_reason,
        dataset_version=dataset_version if isinstance(dataset_version, str) else None,
        evaluation_status=(evaluation_status if isinstance(evaluation_status, str) else None),
        case_count=len(cases),
        qrel_count=qrel_count,
        unique_qrel_count=len(qrel_ids),
        missing_qrel_count=len(missing_ids),
        changed_qrel_count=len(changed_ids),
        metadata_mismatch_count=len(metadata_mismatches),
        missing_judged_candidate_count=len(missing_judged_candidate_ids),
        missing_pool_candidate_count=len(missing_pool_candidates),
        qrel_not_effective_as_of_count=len(qrels_not_effective_as_of),
        distractor_not_effective_as_of_count=len(distractors_not_effective_as_of),
        pool_candidate_not_effective_as_of_count=len(pool_candidates_not_effective_as_of),
        full_corpus_pool_mismatch_count=len(full_corpus_pool_mismatches),
        missing_qrel_sample=tuple(sorted(missing_ids)[:10]),
        changed_qrel_sample=tuple(sorted(changed_ids)[:10]),
        missing_judged_candidate_sample=tuple(sorted(missing_judged_candidate_ids)[:10]),
        missing_pool_candidate_sample=tuple(sorted(missing_pool_candidates)[:10]),
        qrel_not_effective_as_of_sample=tuple(sorted(qrels_not_effective_as_of)[:10]),
        distractor_not_effective_as_of_sample=tuple(sorted(distractors_not_effective_as_of)[:10]),
        pool_candidate_not_effective_as_of_sample=tuple(
            sorted(pool_candidates_not_effective_as_of)[:10]
        ),
        full_corpus_pool_mismatch_sample=tuple(sorted(full_corpus_pool_mismatches)[:10]),
        gold_contract_valid=not contract_errors,
        gold_contract_error_count=len(contract_errors),
        gold_contract_error_sample=contract_errors[:10],
        source_bank_binding_valid=not source_binding_errors,
        approval_manifest_valid=not approval_errors and not approval_contract_errors,
        approval_manifest_contract_error_count=len(approval_contract_errors),
        approval_manifest_contract_error_sample=approval_contract_errors[:10],
        adjudication_manifest_valid=(
            validated_adjudication is not None
            and validated_dataset is not None
            and validated_approval is not None
            and not adjudication_contract_errors
            and not adjudication_errors
        ),
        adjudication_manifest_contract_error_count=len(adjudication_contract_errors),
        adjudication_manifest_contract_error_sample=adjudication_contract_errors[:10],
        adjudication_manifest_error_count=len(adjudication_errors),
        adjudication_manifest_error_sample=adjudication_errors[:10],
        declared_gold_dataset_sha256=declared_gold_dataset_sha256,
        calculated_gold_dataset_sha256=calculated_gold_dataset_sha256,
        declared_question_set_sha256=declared_question_hash,
        calculated_question_set_sha256=calculated_question_hash,
        declared_question_scope_set_sha256=(
            declared_scope_hash if isinstance(declared_scope_hash, str) else None
        ),
        calculated_question_scope_set_sha256=calculated_scope_hash,
        declared_corpus_snapshot_id=declared_snapshot_id,
        current_corpus_snapshot_id=current_snapshot_id,
        declared_as_of_populations=declared_populations,
        current_as_of_populations=current_populations,
        as_of_population_mismatch_count=len(population_mismatches),
        as_of_population_mismatch_sample=tuple(sorted(population_mismatches)[:10]),
        declared_parser_contract_version=(
            str(declared_parser_version) if declared_parser_version is not None else None
        ),
        current_parser_contract_version=PARSER_SCHEMA_VERSION,
        current_stored_searchable_provision_count=len(provisions),
    )


async def _run(arguments: argparse.Namespace) -> GoldPreflightReport:
    settings = get_settings()
    if not settings.database_url:
        raise SystemExit("DATABASE_URL이 필요합니다.")
    dataset = json.loads(arguments.dataset.read_text(encoding="utf-8"))
    if not isinstance(dataset, dict):
        raise SystemExit("평가셋 JSON의 최상위 값은 객체여야 합니다.")
    source_bank = json.loads(arguments.source_bank.read_text(encoding="utf-8"))
    if not isinstance(source_bank, dict):
        raise SystemExit("질문은행 JSON의 최상위 값은 객체여야 합니다.")
    approval_manifest = None
    if arguments.approval_manifest.exists():
        approval_manifest = json.loads(arguments.approval_manifest.read_text(encoding="utf-8"))
        if not isinstance(approval_manifest, dict):
            raise SystemExit("질문 승인 manifest의 최상위 값은 객체여야 합니다.")
    adjudication_manifest = None
    if arguments.adjudication_manifest.exists():
        adjudication_manifest = json.loads(
            arguments.adjudication_manifest.read_text(encoding="utf-8")
        )
        if not isinstance(adjudication_manifest, dict):
            raise SystemExit("gold adjudication manifest must be a top-level JSON object")
    repository = PostgresLegalRepository(settings.database_url)
    try:
        corpus_status = await repository.corpus_search_status()
        provisions = await load_provisions(repository)
    finally:
        await repository.engine.dispose()
    return audit_gold_dataset(
        dataset,
        provisions,
        source_bank,
        approval_manifest,
        adjudication_manifest,
        corpus_search_ready=corpus_status.ready,
        corpus_search_ready_reason=corpus_status.reason,
    )


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    try:
        report = asyncio.run(_run(_arguments()))
    except NonCurrentParserIdError as error:
        print(json.dumps(error.to_dict(), ensure_ascii=False, indent=2), file=sys.stderr)
        raise SystemExit(2) from error
    print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))
    if not report.ready:
        raise SystemExit(2)
