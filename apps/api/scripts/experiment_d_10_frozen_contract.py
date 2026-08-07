"""Preflight the frozen ten-case Experiment D calibration contract without external calls."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Annotated, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    ValidationError,
    model_validator,
)

from scripts.experiment_d_manual_review_contract import (
    DEFAULT_APPROVAL_MANIFEST,
    DEFAULT_SOURCE_BANK,
    load_manual_pilot_artifacts,
)
from scripts.experiment_d_manual_review_results import (
    ExperimentD10ManualReview,
    _final_judgment,
    _validated_result,
)
from scripts.experiment_d_pilot_contract import canonical_json_sha256

REPOSITORY_ROOT = Path(__file__).parents[3]
DEFAULT_CONTRACT = (
    REPOSITORY_ROOT / "experiments" / "d_manual" / "experiment-d-10-m3-frozen-contract.json"
)

Sha256 = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]
NonBlankStr = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
Verdict = Literal[
    "directly_answerable",
    "partially_answerable",
    "clarification_required",
    "not_answerable_from_current_corpus",
]
ContextVerdict = Literal["sufficient", "insufficient", "blocked"]


class FrozenD10ContractError(ValueError):
    """Raised when the frozen D-10 calibration contract is not reproducible."""


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ArtifactBinding(StrictModel):
    path: NonBlankStr
    file_sha256: Sha256


class ArtifactBindings(StrictModel):
    question_input: ArtifactBinding
    retrieval_result: ArtifactBinding
    manual_review: ArtifactBinding
    confirmed_diagnostics: ArtifactBinding
    rerank_comparison: ArtifactBinding


class FrozenRunBinding(StrictModel):
    run_id: NonBlankStr
    as_of_date: Literal["2026-08-05"]
    corpus_snapshot_id: Literal[
        "corpus-sha256:605b1f53b4fbe3edff19000796e56d906415e7648e7e6ae6119a46f5fc8d9578"
    ]
    eligible_provision_count: Literal[3066]
    embedding_profile_key: Literal["nvidia-nemotron-3-embed-1b-512-v1"]
    rerank_profile_key: Literal["d10-parent-heading-directness-v1"]


class FrozenCase(StrictModel):
    case_id: NonBlankStr
    question_sha256: Sha256
    question_scope_sha256: Sha256
    final_verdict: Verdict
    context_verdict: ContextVerdict
    direct_evidence_provision_ids: list[NonBlankStr]
    known_irrelevant_top5_provision_ids: list[NonBlankStr]

    @model_validator(mode="after")
    def labels_are_consistent(self) -> FrozenCase:
        direct = set(self.direct_evidence_provision_ids)
        irrelevant = set(self.known_irrelevant_top5_provision_ids)
        if len(direct) != len(self.direct_evidence_provision_ids):
            raise ValueError("direct evidence IDs must be distinct")
        if len(irrelevant) != len(self.known_irrelevant_top5_provision_ids):
            raise ValueError("known irrelevant IDs must be distinct")
        if direct & irrelevant:
            raise ValueError("direct and irrelevant labels must be disjoint")
        if self.final_verdict == "not_answerable_from_current_corpus" and direct:
            raise ValueError("not-answerable case cannot freeze direct evidence")
        if self.final_verdict == "directly_answerable" and not direct:
            raise ValueError("directly-answerable case must freeze direct evidence")
        return self


class FrozenD10EvaluationContract(StrictModel):
    schema_version: Literal[1]
    experiment: Literal["D-10-M3"]
    artifact_class: Literal["frozen_small_sample_evaluation_not_full_gold"]
    status: Literal["frozen_for_m3_calibration"]
    evaluation_scope: Literal["user_confirmed_labels_within_original_raw_top10_only"]
    run_binding: FrozenRunBinding
    artifact_bindings: ArtifactBindings
    cases: list[FrozenCase] = Field(min_length=10, max_length=10)
    allowed_metrics: list[NonBlankStr]
    prohibited_claims: list[NonBlankStr]
    contract_payload_sha256: Sha256

    @model_validator(mode="after")
    def case_ids_are_distinct(self) -> FrozenD10EvaluationContract:
        case_ids = [case.case_id for case in self.cases]
        if len(set(case_ids)) != 10:
            raise ValueError("frozen contract must contain 10 distinct case IDs")
        return self


def _sha256(path: Path) -> str:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError as error:
        raise FrozenD10ContractError(f"could not read frozen artifact: {path}") from error


def _read_json_object(path: Path, *, label: str) -> dict[str, object]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise FrozenD10ContractError(f"could not read {label}: {path}") from error
    if not isinstance(value, dict):
        raise FrozenD10ContractError(f"{label} root must be an object")
    return value


def _resolve_artifact(root: Path, binding: ArtifactBinding) -> Path:
    candidate = (root / binding.path).resolve()
    if not candidate.is_relative_to(root.resolve()):
        raise FrozenD10ContractError("frozen artifact path escapes repository root")
    return candidate


def _verify_artifact(root: Path, binding: ArtifactBinding) -> Path:
    path = _resolve_artifact(root, binding)
    if _sha256(path) != binding.file_sha256:
        raise FrozenD10ContractError(f"frozen artifact SHA-256 mismatch: {binding.path}")
    return path


def load_frozen_contract(
    contract_path: Path = DEFAULT_CONTRACT,
) -> FrozenD10EvaluationContract:
    raw = _read_json_object(contract_path, label="frozen D-10 contract")
    try:
        contract = FrozenD10EvaluationContract.model_validate(raw)
    except ValidationError as error:
        raise FrozenD10ContractError("frozen D-10 contract schema is invalid") from error
    payload = contract.model_dump(mode="json", exclude={"contract_payload_sha256"})
    if canonical_json_sha256(payload) != contract.contract_payload_sha256:
        raise FrozenD10ContractError("frozen D-10 contract payload SHA-256 mismatch")
    return contract


def _validate_question_bindings(
    contract: FrozenD10EvaluationContract,
    *,
    repository_root: Path,
) -> None:
    question_path = _resolve_artifact(repository_root, contract.artifact_bindings.question_input)
    artifacts = load_manual_pilot_artifacts(
        question_path,
        repository_root / DEFAULT_SOURCE_BANK.relative_to(REPOSITORY_ROOT),
        repository_root / DEFAULT_APPROVAL_MANIFEST.relative_to(REPOSITORY_ROOT),
    )
    if artifacts.question_input_sha256 != contract.artifact_bindings.question_input.file_sha256:
        raise FrozenD10ContractError("frozen question-input SHA-256 mismatch")
    expected = [
        (question.id, question.question_sha256, question.question_scope_sha256)
        for question in artifacts.questions
    ]
    actual = [
        (case.case_id, case.question_sha256, case.question_scope_sha256) for case in contract.cases
    ]
    if actual != expected:
        raise FrozenD10ContractError("frozen case identities do not match D-10 input order")


def _validate_review_labels(
    contract: FrozenD10EvaluationContract,
    *,
    result: Mapping[str, object],
    review: ExperimentD10ManualReview,
) -> None:
    result_cases = result.get("cases")
    if not isinstance(result_cases, list):
        raise FrozenD10ContractError("D-10 result cases are invalid")
    result_by_id = {
        str(case["case_id"]): case
        for case in result_cases
        if isinstance(case, dict) and isinstance(case.get("case_id"), str)
    }
    review_by_id = {case.case_id: case for case in review.cases}
    if [case.case_id for case in contract.cases] != list(result_by_id):
        raise FrozenD10ContractError("frozen cases do not match retrieval result order")
    for frozen in contract.cases:
        review_case = review_by_id.get(frozen.case_id)
        result_case = result_by_id[frozen.case_id]
        if review_case is None:
            raise FrozenD10ContractError(f"missing frozen review case: {frozen.case_id}")
        final = _final_judgment(review_case)
        expected = (
            final.verdict,
            final.context_verdict,
            final.direct_evidence_provision_ids,
            final.irrelevant_top5_provision_ids,
        )
        actual = (
            frozen.final_verdict,
            frozen.context_verdict,
            frozen.direct_evidence_provision_ids,
            frozen.known_irrelevant_top5_provision_ids,
        )
        if actual != expected:
            raise FrozenD10ContractError(f"frozen judgment mismatch: {frozen.case_id}")
        raw_candidates = result_case.get("raw_candidates")
        if not isinstance(raw_candidates, list) or len(raw_candidates) != 10:
            raise FrozenD10ContractError(f"invalid raw top 10: {frozen.case_id}")
        top10 = {
            str(candidate["provision_id"])
            for candidate in raw_candidates
            if isinstance(candidate, dict) and isinstance(candidate.get("provision_id"), str)
        }
        top5 = {
            str(candidate["provision_id"])
            for candidate in raw_candidates[:5]
            if isinstance(candidate, dict) and isinstance(candidate.get("provision_id"), str)
        }
        if not set(frozen.direct_evidence_provision_ids) <= top10:
            raise FrozenD10ContractError(f"direct label escapes original top 10: {frozen.case_id}")
        if not set(frozen.known_irrelevant_top5_provision_ids) <= top5:
            raise FrozenD10ContractError(
                f"irrelevant label escapes original top 5: {frozen.case_id}"
            )


def preflight_frozen_d10(
    contract_path: Path = DEFAULT_CONTRACT,
    *,
    repository_root: Path = REPOSITORY_ROOT,
) -> dict[str, object]:
    contract = load_frozen_contract(contract_path)
    _validate_question_bindings(contract, repository_root=repository_root)
    bindings = contract.artifact_bindings
    result_path = _verify_artifact(repository_root, bindings.retrieval_result)
    review_path = _verify_artifact(repository_root, bindings.manual_review)
    diagnostics_path = _verify_artifact(repository_root, bindings.confirmed_diagnostics)
    rerank_path = _verify_artifact(repository_root, bindings.rerank_comparison)
    _verify_artifact(repository_root, bindings.question_input)

    try:
        result, _ = _validated_result(result_path)
        review = ExperimentD10ManualReview.model_validate(
            _read_json_object(review_path, label="confirmed D-10 review")
        )
    except (ValueError, ValidationError) as error:
        raise FrozenD10ContractError("frozen D-10 result or review is invalid") from error
    if review.status != "confirmed":
        raise FrozenD10ContractError("frozen D-10 review is not confirmed")
    run = contract.run_binding
    inputs = result.get("inputs")
    if not isinstance(inputs, dict):
        raise FrozenD10ContractError("frozen D-10 result inputs are invalid")
    if (
        result.get("run_id") != run.run_id
        or inputs.get("as_of_date") != run.as_of_date
        or inputs.get("corpus_snapshot_id") != run.corpus_snapshot_id
        or inputs.get("eligible_provision_count") != run.eligible_provision_count
        or inputs.get("embedding_profile_key") != run.embedding_profile_key
    ):
        raise FrozenD10ContractError("frozen run binding mismatch")
    _validate_review_labels(contract, result=result, review=review)

    diagnostics = _read_json_object(diagnostics_path, label="confirmed diagnostics")
    if (
        diagnostics.get("artifact_class") != "confirmed_manual_diagnostic_not_gold"
        or diagnostics.get("confirmed_case_count") != 10
        or diagnostics.get("review_file_sha256") != bindings.manual_review.file_sha256
    ):
        raise FrozenD10ContractError("confirmed diagnostics binding mismatch")
    rerank = _read_json_object(rerank_path, label="D-10 rerank comparison")
    rerank_binding = rerank.get("input_binding")
    scoring_profile = rerank.get("scoring_profile")
    if (
        rerank.get("artifact_class") != "calibration_local_rerank_not_gold"
        or not isinstance(rerank_binding, dict)
        or rerank_binding.get("result_file_sha256") != bindings.retrieval_result.file_sha256
        or rerank_binding.get("review_file_sha256") != bindings.manual_review.file_sha256
        or not isinstance(scoring_profile, dict)
        or scoring_profile.get("profile_key") != run.rerank_profile_key
    ):
        raise FrozenD10ContractError("rerank comparison binding mismatch")

    return {
        "status": "valid",
        "experiment": contract.experiment,
        "artifact_class": contract.artifact_class,
        "question_count": len(contract.cases),
        "contract_payload_sha256": contract.contract_payload_sha256,
        "run_id": run.run_id,
        "corpus_snapshot_id": run.corpus_snapshot_id,
        "embedding_profile_key": run.embedding_profile_key,
        "evaluation_scope": contract.evaluation_scope,
        "allowed_metrics": contract.allowed_metrics,
        "prohibited_claims": contract.prohibited_claims,
        "external_calls": 0,
        "m3_calibration_ready": True,
    }


def _arguments(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Preflight frozen D-10 M3 contract")
    parser.add_argument("command", choices=("preflight",))
    parser.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    arguments = _arguments(argv)
    contract_path = (
        arguments.contract
        if arguments.contract.is_absolute()
        else REPOSITORY_ROOT / arguments.contract
    )
    try:
        print(json.dumps(preflight_frozen_d10(contract_path), ensure_ascii=False, indent=2))
        return 0
    except FrozenD10ContractError as error:
        print(
            json.dumps(
                {
                    "status": "failed",
                    "error_code": "d10_frozen_preflight_failed",
                    "message": str(error),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "DEFAULT_CONTRACT",
    "FrozenCase",
    "FrozenD10ContractError",
    "FrozenD10EvaluationContract",
    "load_frozen_contract",
    "preflight_frozen_d10",
]
