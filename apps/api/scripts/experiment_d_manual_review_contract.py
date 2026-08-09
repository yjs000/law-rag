"""Strict question-only input contract for the Experiment D-10 manual pilot."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
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

from scripts.experiment_d_gold_contract import ExperimentDQuestionApprovalManifest
from scripts.experiment_d_pilot_contract import canonical_json_sha256
from scripts.experiment_d_question_identity import (
    question_scope_set_sha256,
    question_scope_sha256,
)

REPOSITORY_ROOT = Path(__file__).parents[3]
DEFAULT_QUESTION_INPUT = (
    REPOSITORY_ROOT / "experiments" / "d_manual" / "experiment-d-10-questions.json"
)
DEFAULT_SOURCE_BANK = (
    Path(__file__).parents[1]
    / "evaluation"
    / "experiment-d-lay-energy-query-bank-v1-draft.json"
)
DEFAULT_APPROVAL_MANIFEST = (
    Path(__file__).parents[1]
    / "evaluation"
    / "experiment-d-lay-energy-question-approval-v1.json"
)

Sha256 = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]
NonBlankStr = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class ManualPilotInputError(ValueError):
    """Raised when D-10 input is not exactly bound to approved questions."""


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SourceBankBinding(StrictModel):
    artifact: Literal[
        "apps/api/evaluation/experiment-d-lay-energy-query-bank-v1-draft.json"
    ]
    bank_version: Literal["experiment-d-lay-energy-query-bank-v1-draft"]
    question_set_sha256: Sha256
    question_scope_set_sha256: Sha256
    file_sha256: Sha256


class QuestionApprovalBinding(StrictModel):
    artifact: Literal[
        "apps/api/evaluation/experiment-d-lay-energy-question-approval-v1.json"
    ]
    manifest_version: Literal["experiment-d-lay-energy-question-approval-v1"]
    canonical_payload_sha256: Sha256
    file_sha256: Sha256


class FrozenQuestionIdentity(StrictModel):
    id: NonBlankStr
    question_sha256: Sha256
    question_scope_sha256: Sha256


class ExperimentD10QuestionInput(StrictModel):
    schema_version: Literal[1]
    experiment: Literal["D-10"]
    artifact_class: Literal["not_gold"]
    status: Literal["frozen_for_manual_retrieval"]
    purpose: Literal["manual_retrieval_and_context_diagnostic"]
    selection_method: Literal["explicit_mixed_manual_diagnostic_v1"]
    source_bank: SourceBankBinding
    question_approval: QuestionApprovalBinding
    questions: list[FrozenQuestionIdentity] = Field(min_length=10, max_length=10)

    @model_validator(mode="after")
    def question_ids_are_distinct(self) -> ExperimentD10QuestionInput:
        ids = [question.id for question in self.questions]
        if len(set(ids)) != 10:
            raise ValueError("D-10 input must contain 10 distinct question IDs")
        return self


@dataclass(frozen=True, slots=True)
class ManualPilotQuestion:
    id: str
    question: str
    question_sha256: str
    question_scope_sha256: str
    intent: str
    technology: str
    question_style: str
    scenario_family_id: str


@dataclass(frozen=True, slots=True)
class ManualPilotArtifacts:
    question_input: ExperimentD10QuestionInput
    questions: tuple[ManualPilotQuestion, ...]
    question_input_sha256: str
    source_bank_file_sha256: str
    approval_manifest_file_sha256: str
    approval_manifest_payload_sha256: str


def _file_sha256(encoded: bytes) -> str:
    # Git may check text files out with CRLF on Windows and LF in CI. Seal the
    # JSON content independently of that transport-only line-ending difference.
    return hashlib.sha256(encoded.replace(b"\r\n", b"\n")).hexdigest()


def _text_sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _read_json_object(path: Path, *, label: str) -> tuple[Mapping[str, object], bytes]:
    try:
        encoded = path.read_bytes()
        value = json.loads(encoded.decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ManualPilotInputError(f"could not read {label}: {path}") from error
    if not isinstance(value, Mapping):
        raise ManualPilotInputError(f"{label} root must be an object")
    return value, encoded


def _validated_source_questions(
    bank: Mapping[str, object],
) -> tuple[list[Mapping[str, object]], dict[str, Mapping[str, object]]]:
    if (
        bank.get("schema_version") != 1
        or bank.get("bank_version") != "experiment-d-lay-energy-query-bank-v1-draft"
        or bank.get("status") != "draft_for_human_question_review"
        or bank.get("question_count") != 1000
    ):
        raise ManualPilotInputError("source bank contract mismatch")
    raw_questions = bank.get("questions")
    if not isinstance(raw_questions, list) or len(raw_questions) != 1000:
        raise ManualPilotInputError("source bank must contain exactly 1000 questions")
    questions: list[Mapping[str, object]] = []
    by_id: dict[str, Mapping[str, object]] = {}
    for raw in raw_questions:
        if not isinstance(raw, Mapping):
            raise ManualPilotInputError("source-bank question must be an object")
        required = (
            "id",
            "question",
            "intent",
            "technology",
            "question_style",
            "scenario_family_id",
        )
        if any(
            not isinstance(raw.get(field), str) or not str(raw[field]).strip()
            for field in required
        ):
            raise ManualPilotInputError("source-bank question scope is incomplete")
        question_id = str(raw["id"])
        question_text = str(raw["question"])
        if question_id in by_id:
            raise ManualPilotInputError("source bank contains duplicate question IDs")
        if raw.get("evaluation_annotation_status") != "not_annotated":
            raise ManualPilotInputError("D-10 source question must remain unannotated")
        if raw.get("question_sha256") != _text_sha256(question_text):
            raise ManualPilotInputError(f"source question SHA-256 mismatch: {question_id}")
        if question_scope_sha256(raw) is None:
            raise ManualPilotInputError(f"source question scope is invalid: {question_id}")
        questions.append(raw)
        by_id[question_id] = raw

    question_set = canonical_json_sha256(
        [{"id": item["id"], "question": item["question"]} for item in questions]
    )
    scope_set = question_scope_set_sha256(questions)
    if bank.get("question_set_sha256") != question_set:
        raise ManualPilotInputError("source bank question-set SHA-256 mismatch")
    if scope_set is None or bank.get("question_scope_set_sha256") != scope_set:
        raise ManualPilotInputError("source bank question-scope-set SHA-256 mismatch")
    return questions, by_id


def _validated_approval(
    raw_manifest: Mapping[str, object],
    *,
    questions: Sequence[Mapping[str, object]],
    bank: Mapping[str, object],
) -> tuple[ExperimentDQuestionApprovalManifest, str]:
    try:
        manifest = ExperimentDQuestionApprovalManifest.model_validate(raw_manifest)
    except ValidationError as error:
        raise ManualPilotInputError("question approval manifest is invalid") from error
    if manifest.source_bank.bank_version != bank.get("bank_version"):
        raise ManualPilotInputError("approval bank version mismatch")
    if manifest.source_bank.question_set_sha256 != bank.get("question_set_sha256"):
        raise ManualPilotInputError("approval question-set SHA-256 mismatch")
    if manifest.source_bank.question_scope_set_sha256 != bank.get("question_scope_set_sha256"):
        raise ManualPilotInputError("approval question-scope-set SHA-256 mismatch")
    expected = [
        (
            str(question["id"]),
            str(question["question_sha256"]),
            question_scope_sha256(question),
        )
        for question in questions
    ]
    actual = [
        (item.id, item.question_sha256, item.question_scope_sha256)
        for item in manifest.questions
    ]
    if actual != expected:
        raise ManualPilotInputError("approval manifest does not seal the ordered source bank")
    payload_sha256 = canonical_json_sha256(manifest.model_dump(mode="json"))
    return manifest, payload_sha256


def load_manual_pilot_artifacts(
    question_input_path: Path = DEFAULT_QUESTION_INPUT,
    source_bank_path: Path = DEFAULT_SOURCE_BANK,
    approval_manifest_path: Path = DEFAULT_APPROVAL_MANIFEST,
) -> ManualPilotArtifacts:
    raw_input, input_bytes = _read_json_object(question_input_path, label="D-10 input")
    bank, bank_bytes = _read_json_object(source_bank_path, label="source bank")
    raw_approval, approval_bytes = _read_json_object(
        approval_manifest_path, label="question approval manifest"
    )
    try:
        question_input = ExperimentD10QuestionInput.model_validate(raw_input)
    except ValidationError as error:
        raise ManualPilotInputError("D-10 input contract is invalid") from error

    questions, by_id = _validated_source_questions(bank)
    manifest, approval_payload_sha256 = _validated_approval(
        raw_approval, questions=questions, bank=bank
    )
    bank_file_sha256 = _file_sha256(bank_bytes)
    approval_file_sha256 = _file_sha256(approval_bytes)
    if question_input.source_bank.file_sha256 != bank_file_sha256:
        raise ManualPilotInputError("D-10 source-bank file SHA-256 mismatch")
    if question_input.source_bank.question_set_sha256 != bank.get("question_set_sha256"):
        raise ManualPilotInputError("D-10 question-set SHA-256 mismatch")
    if question_input.source_bank.question_scope_set_sha256 != bank.get(
        "question_scope_set_sha256"
    ):
        raise ManualPilotInputError("D-10 question-scope-set SHA-256 mismatch")
    if question_input.question_approval.file_sha256 != approval_file_sha256:
        raise ManualPilotInputError("D-10 approval file SHA-256 mismatch")
    if question_input.question_approval.canonical_payload_sha256 != approval_payload_sha256:
        raise ManualPilotInputError("D-10 approval payload SHA-256 mismatch")

    approved_by_id = {item.id: item for item in manifest.questions}
    selected: list[ManualPilotQuestion] = []
    for frozen in question_input.questions:
        source = by_id.get(frozen.id)
        approved = approved_by_id.get(frozen.id)
        if source is None or approved is None:
            raise ManualPilotInputError(f"D-10 question is not approved: {frozen.id}")
        calculated_scope_sha256 = question_scope_sha256(source)
        if (
            frozen.question_sha256 != source.get("question_sha256")
            or frozen.question_sha256 != approved.question_sha256
        ):
            raise ManualPilotInputError(f"D-10 question SHA-256 mismatch: {frozen.id}")
        if (
            frozen.question_scope_sha256 != calculated_scope_sha256
            or frozen.question_scope_sha256 != approved.question_scope_sha256
        ):
            raise ManualPilotInputError(f"D-10 question scope SHA-256 mismatch: {frozen.id}")
        selected.append(
            ManualPilotQuestion(
                id=frozen.id,
                question=str(source["question"]),
                question_sha256=frozen.question_sha256,
                question_scope_sha256=frozen.question_scope_sha256,
                intent=str(source["intent"]),
                technology=str(source["technology"]),
                question_style=str(source["question_style"]),
                scenario_family_id=str(source["scenario_family_id"]),
            )
        )

    return ManualPilotArtifacts(
        question_input=question_input,
        questions=tuple(selected),
        question_input_sha256=_file_sha256(input_bytes),
        source_bank_file_sha256=bank_file_sha256,
        approval_manifest_file_sha256=approval_file_sha256,
        approval_manifest_payload_sha256=approval_payload_sha256,
    )


__all__ = [
    "DEFAULT_APPROVAL_MANIFEST",
    "DEFAULT_QUESTION_INPUT",
    "DEFAULT_SOURCE_BANK",
    "ExperimentD10QuestionInput",
    "FrozenQuestionIdentity",
    "ManualPilotArtifacts",
    "ManualPilotInputError",
    "ManualPilotQuestion",
    "load_manual_pilot_artifacts",
]
