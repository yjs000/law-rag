"""Create a 50-question, question-only Experiment D annotation pilot worklist.

The command is deliberately offline.  It reads one frozen 1,000-question bank
and its explicit approval manifest; it never calls PostgreSQL, NVIDIA, an
embedding model, a retriever, or an answer generator.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from contextlib import suppress
from pathlib import Path
from uuid import uuid4

from pydantic import ValidationError

from scripts.experiment_d_gold_contract import ExperimentDQuestionApprovalManifest
from scripts.experiment_d_pilot_contract import (
    ExperimentDPilotAnnotationWorklist,
    canonical_json_sha256,
    canonical_pilot_worklist_payload_sha256,
)
from scripts.experiment_d_question_identity import (
    question_scope_set_sha256,
    question_scope_sha256,
)

DEFAULT_SOURCE_BANK = (
    Path(__file__).parents[1] / "evaluation" / "experiment-d-lay-energy-query-bank-v1-draft.json"
)
DEFAULT_APPROVAL_MANIFEST = (
    Path(__file__).parents[1] / "evaluation" / "experiment-d-lay-energy-question-approval-v1.json"
)
DEFAULT_OUTPUT = (
    Path(__file__).parents[1] / "evaluation" / "experiment-d-lay-energy-pilot-worklist-v1.json"
)

BANK_VERSION = "experiment-d-lay-energy-query-bank-v1-draft"
BANK_STATUS = "draft_for_human_question_review"
QUESTION_STATUS = "not_annotated"


class PilotWorklistError(ValueError):
    """Raised when the pilot cannot be created without weakening its bindings."""


def _file_sha256(encoded: bytes) -> str:
    return hashlib.sha256(encoded).hexdigest()


def _text_sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _question_set_sha256(questions: Sequence[Mapping[str, object]]) -> str:
    return canonical_json_sha256(
        [
            {
                "id": question.get("id"),
                "question": question.get("question"),
            }
            for question in questions
        ]
    )


def _artifact_name(path: Path) -> str:
    return path.resolve().as_posix()


def _load_json_object(path: Path, *, label: str) -> tuple[Mapping[str, object], bytes]:
    try:
        encoded = path.read_bytes()
        value = json.loads(encoded.decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise PilotWorklistError(f"could not read {label}: {path}") from error
    if not isinstance(value, Mapping):
        raise PilotWorklistError(f"{label} root must be an object")
    return value, encoded


def _validated_source_questions(
    bank: Mapping[str, object],
) -> list[Mapping[str, object]]:
    if bank.get("schema_version") != 1:
        raise PilotWorklistError("source bank schema_version must be 1")
    if bank.get("bank_version") != BANK_VERSION:
        raise PilotWorklistError("source bank version is not supported")
    if bank.get("status") != BANK_STATUS:
        raise PilotWorklistError("source bank is not awaiting human question review")
    if bank.get("question_count") != 1000:
        raise PilotWorklistError("source bank must declare exactly 1000 questions")

    raw_questions = bank.get("questions")
    if not isinstance(raw_questions, list) or len(raw_questions) != 1000:
        raise PilotWorklistError("source bank must contain exactly 1000 questions")
    if any(not isinstance(question, Mapping) for question in raw_questions):
        raise PilotWorklistError("every source-bank question must be an object")

    questions: list[Mapping[str, object]] = list(raw_questions)
    question_ids: list[str] = []
    family_counts: Counter[str] = Counter()
    required_scope_fields = (
        "id",
        "question",
        "intent",
        "technology",
        "question_style",
        "scenario_family_id",
    )
    for index, question in enumerate(questions):
        for field in required_scope_fields:
            value = question.get(field)
            if not isinstance(value, str) or not value.strip():
                raise PilotWorklistError(f"source question {index} has invalid {field}")

        question_id = str(question["id"])
        question_text = str(question["question"])
        family_id = str(question["scenario_family_id"])
        if question.get("evaluation_annotation_status") != QUESTION_STATUS:
            raise PilotWorklistError(f"source question {question_id} is not unannotated")
        if question.get("question_sha256") != _text_sha256(question_text):
            raise PilotWorklistError(f"source question {question_id} text SHA-256 mismatch")
        if question_scope_sha256(question) is None:
            raise PilotWorklistError(f"source question {question_id} has incomplete scope")
        question_ids.append(question_id)
        family_counts[family_id] += 1

    if len(set(question_ids)) != 1000:
        raise PilotWorklistError("source bank contains duplicate question IDs")
    if len(family_counts) != 200 or any(count != 5 for count in family_counts.values()):
        raise PilotWorklistError("source bank must contain 200 families of exactly 5 questions")

    calculated_question_set_sha256 = _question_set_sha256(questions)
    calculated_scope_set_sha256 = question_scope_set_sha256(questions)
    if calculated_scope_set_sha256 is None:  # pragma: no cover - checked per question above
        raise PilotWorklistError("source bank has incomplete question scopes")
    if bank.get("question_set_sha256") != calculated_question_set_sha256:
        raise PilotWorklistError("source bank question_set_sha256 mismatch")
    if bank.get("question_scope_set_sha256") != calculated_scope_set_sha256:
        raise PilotWorklistError("source bank question_scope_set_sha256 mismatch")
    return questions


def _validated_approval_manifest(
    raw_manifest: Mapping[str, object],
    *,
    questions: Sequence[Mapping[str, object]],
    bank: Mapping[str, object],
    confirmed_manifest_sha256: str | None,
) -> tuple[ExperimentDQuestionApprovalManifest, str]:
    if confirmed_manifest_sha256 is None:
        raise PilotWorklistError("approval manifest canonical SHA-256 confirmation is required")
    try:
        manifest = ExperimentDQuestionApprovalManifest.model_validate(raw_manifest)
    except ValidationError as error:
        raise PilotWorklistError("question approval manifest is invalid or unapproved") from error

    canonical_manifest_sha256 = canonical_json_sha256(manifest.model_dump(mode="json"))
    if confirmed_manifest_sha256 != canonical_manifest_sha256:
        raise PilotWorklistError("approval manifest canonical SHA-256 confirmation mismatch")

    if manifest.source_bank.bank_version != bank.get("bank_version"):
        raise PilotWorklistError("approval manifest bank version mismatch")
    if manifest.source_bank.question_count != bank.get("question_count"):
        raise PilotWorklistError("approval manifest question count mismatch")
    if manifest.source_bank.question_set_sha256 != bank.get("question_set_sha256"):
        raise PilotWorklistError("approval manifest question-set SHA-256 mismatch")
    if manifest.source_bank.question_scope_set_sha256 != bank.get("question_scope_set_sha256"):
        raise PilotWorklistError("approval manifest question-scope-set SHA-256 mismatch")

    expected_approvals = [
        (
            str(question["id"]),
            str(question["question_sha256"]),
            question_scope_sha256(question),
        )
        for question in questions
    ]
    actual_approvals = [
        (
            approved.id,
            approved.question_sha256,
            approved.question_scope_sha256,
        )
        for approved in manifest.questions
    ]
    if actual_approvals != expected_approvals:
        raise PilotWorklistError(
            "approval manifest does not seal the exact ordered source-bank questions"
        )
    return manifest, canonical_manifest_sha256


def _validated_family_ids(scenario_family_ids: Sequence[str]) -> list[str]:
    family_ids = list(scenario_family_ids)
    if len(family_ids) != 10:
        raise PilotWorklistError("exactly 10 scenario family IDs are required")
    if any(not family_id.strip() for family_id in family_ids):
        raise PilotWorklistError("scenario family IDs must not be blank")
    if len(set(family_ids)) != 10:
        raise PilotWorklistError("the 10 scenario family IDs must be distinct")
    return family_ids


def build_pilot_worklist(
    bank: Mapping[str, object],
    raw_approval_manifest: Mapping[str, object],
    *,
    source_bank_artifact: str,
    source_bank_file_sha256: str,
    approval_manifest_artifact: str,
    approval_manifest_file_sha256: str,
    confirmed_approval_manifest_sha256: str | None,
    scenario_family_ids: Sequence[str],
) -> ExperimentDPilotAnnotationWorklist:
    """Build a sealed question-only worklist after all fail-closed checks pass."""

    questions = _validated_source_questions(bank)
    _, canonical_manifest_sha256 = _validated_approval_manifest(
        raw_approval_manifest,
        questions=questions,
        bank=bank,
        confirmed_manifest_sha256=confirmed_approval_manifest_sha256,
    )
    selected_family_ids = _validated_family_ids(scenario_family_ids)

    by_family: dict[str, list[Mapping[str, object]]] = defaultdict(list)
    for question in questions:
        by_family[str(question["scenario_family_id"])].append(question)

    selected_questions: list[Mapping[str, object]] = []
    for family_id in selected_family_ids:
        family_questions = by_family.get(family_id)
        if family_questions is None:
            raise PilotWorklistError(f"unknown scenario family ID: {family_id}")
        if len(family_questions) != 5:  # pragma: no cover - full-bank check catches this first
            raise PilotWorklistError(
                f"scenario family {family_id} does not contain exactly 5 questions"
            )
        selected_questions.extend(family_questions)

    payload = {
        "schema_version": 1,
        "worklist_version": "experiment-d-lay-energy-pilot-worklist-v1",
        "artifact_class": "not_gold",
        "status": "draft_for_annotation",
        "purpose": "question_only_pilot_annotation_worklist",
        "source_bank": {
            "artifact": source_bank_artifact,
            "bank_version": bank["bank_version"],
            "question_count": bank["question_count"],
            "question_set_sha256": bank["question_set_sha256"],
            "question_scope_set_sha256": bank["question_scope_set_sha256"],
            "file_sha256": source_bank_file_sha256,
        },
        "question_approval": {
            "artifact": approval_manifest_artifact,
            "manifest_version": "experiment-d-lay-energy-question-approval-v1",
            "status": "approved",
            "decision_scope": "question_text_and_scope_only",
            "canonical_payload_sha256": canonical_manifest_sha256,
            "file_sha256": approval_manifest_file_sha256,
        },
        "selection": {
            "method": "explicit_exactly_10_scenario_families",
            "scenario_family_ids": selected_family_ids,
            "questions_per_family": 5,
            "question_count": 50,
        },
        "questions": [
            {
                "id": question["id"],
                "question": question["question"],
                "question_sha256": question["question_sha256"],
                "question_scope_sha256": question_scope_sha256(question),
                "intent": question["intent"],
                "technology": question["technology"],
                "question_style": question["question_style"],
                "scenario_family_id": question["scenario_family_id"],
            }
            for question in selected_questions
        ],
    }
    try:
        return ExperimentDPilotAnnotationWorklist.model_validate(payload)
    except ValidationError as error:  # pragma: no cover - internal invariant safety net
        raise PilotWorklistError("constructed pilot worklist violates its contract") from error


def atomic_write_worklist(
    output: Path,
    worklist: ExperimentDPilotAnnotationWorklist,
) -> str:
    """Publish the worklist atomically without replacing an existing artifact."""

    serialized = (
        json.dumps(
            worklist.model_dump(mode="json"),
            ensure_ascii=False,
            allow_nan=False,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )
    encoded = serialized.encode("utf-8")
    temporary = output.parent / f".{output.name}.{uuid4().hex}.tmp"
    output.parent.mkdir(parents=True, exist_ok=True)
    try:
        with temporary.open("xb") as stream:
            stream.write(encoded)
            stream.flush()
            os.fsync(stream.fileno())
        try:
            os.link(temporary, output)
        except FileExistsError as error:
            raise PilotWorklistError(f"pilot worklist output already exists: {output}") from error
        with suppress(OSError):
            directory_descriptor = os.open(output.parent, os.O_RDONLY)
            try:
                os.fsync(directory_descriptor)
            finally:
                os.close(directory_descriptor)
    finally:
        with suppress(OSError):
            temporary.unlink(missing_ok=True)
    return _file_sha256(encoded)


def create_pilot_worklist(
    source_bank_path: Path,
    approval_manifest_path: Path,
    output_path: Path,
    *,
    confirmed_approval_manifest_sha256: str | None,
    scenario_family_ids: Sequence[str],
) -> tuple[ExperimentDPilotAnnotationWorklist, str, str]:
    """Read, bind, validate, and atomically publish one pilot worklist."""

    bank, bank_bytes = _load_json_object(source_bank_path, label="source bank")
    approval_manifest, approval_bytes = _load_json_object(
        approval_manifest_path,
        label="question approval manifest",
    )
    worklist = build_pilot_worklist(
        bank,
        approval_manifest,
        source_bank_artifact=_artifact_name(source_bank_path),
        source_bank_file_sha256=_file_sha256(bank_bytes),
        approval_manifest_artifact=_artifact_name(approval_manifest_path),
        approval_manifest_file_sha256=_file_sha256(approval_bytes),
        confirmed_approval_manifest_sha256=confirmed_approval_manifest_sha256,
        scenario_family_ids=scenario_family_ids,
    )
    canonical_payload_sha256 = canonical_pilot_worklist_payload_sha256(worklist)
    file_sha256 = atomic_write_worklist(output_path, worklist)
    return worklist, canonical_payload_sha256, file_sha256


def _arguments(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Create an offline, non-gold 50-question Experiment D annotation pilot worklist"
        )
    )
    parser.add_argument("--source-bank", type=Path, default=DEFAULT_SOURCE_BANK)
    parser.add_argument("--approval-manifest", type=Path, default=DEFAULT_APPROVAL_MANIFEST)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--confirm-approval-manifest-sha256",
        required=True,
        help="canonical payload SHA-256 printed when the approval manifest was created",
    )
    parser.add_argument(
        "--scenario-family-id",
        action="append",
        required=True,
        help="repeat exactly 10 times; input order determines worklist family order",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _arguments(argv)
    worklist, canonical_payload_sha256, file_sha256 = create_pilot_worklist(
        args.source_bank,
        args.approval_manifest,
        args.output,
        confirmed_approval_manifest_sha256=args.confirm_approval_manifest_sha256,
        scenario_family_ids=args.scenario_family_id,
    )
    print(f"pilot_worklist={args.output}")
    print(f"pilot_worklist_payload_sha256={canonical_payload_sha256}")
    print(f"pilot_worklist_file_sha256={file_sha256}")
    print(f"artifact_class={worklist.artifact_class}")
    print(f"status={worklist.status}")
    print(f"selected_scenario_family_count={len(worklist.selection.scenario_family_ids)}")
    print(f"pilot_question_count={len(worklist.questions)}")
    return 0


if __name__ == "__main__":  # pragma: no cover - exercised through public functions
    raise SystemExit(main())
