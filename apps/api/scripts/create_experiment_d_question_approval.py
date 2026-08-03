"""Create an explicit, question-only approval manifest for Experiment D.

This command does not annotate answers or qrels and does not access a database,
an embedding provider, or an evaluation runner.  It only seals the reviewed
question text and scope from the draft question bank.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from collections.abc import Mapping, Sequence
from contextlib import suppress
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from scripts.experiment_d_gold_contract import ExperimentDQuestionApprovalManifest
from scripts.experiment_d_question_identity import (
    question_scope_set_sha256,
    question_scope_sha256,
)

DEFAULT_INPUT = (
    Path(__file__).parents[1] / "evaluation" / "experiment-d-lay-energy-query-bank-v1-draft.json"
)
DEFAULT_OUTPUT = (
    Path(__file__).parents[1] / "evaluation" / "experiment-d-lay-energy-question-approval-v1.json"
)

BANK_VERSION = "experiment-d-lay-energy-query-bank-v1-draft"
BANK_STATUS = "draft_for_human_question_review"
QUESTION_STATUS = "not_annotated"


class QuestionApprovalError(ValueError):
    """Raised when an approval cannot safely be created."""


def _canonical_sha256(value: object) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _question_set_sha256(questions: Sequence[Mapping[str, object]]) -> str:
    return _canonical_sha256(
        [
            {
                "id": question.get("id"),
                "question": question.get("question"),
            }
            for question in questions
        ]
    )


def _text_sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _timezone_aware(value: datetime) -> bool:
    return value.tzinfo is not None and value.utcoffset() is not None


def parse_approved_at(value: str) -> datetime:
    """Parse an ISO 8601 approval time and reject a time without an offset."""

    try:
        approved_at = datetime.fromisoformat(value)
    except ValueError as error:
        raise QuestionApprovalError("approved_at must be a valid ISO 8601 timestamp") from error
    if not _timezone_aware(approved_at):
        raise QuestionApprovalError("approved_at must include a timezone offset")
    return approved_at


def _validated_questions(bank: Mapping[str, object]) -> list[Mapping[str, object]]:
    if bank.get("schema_version") != 1:
        raise QuestionApprovalError("source bank schema_version must be 1")
    if bank.get("bank_version") != BANK_VERSION:
        raise QuestionApprovalError("source bank version is not approvable")
    if bank.get("status") != BANK_STATUS:
        raise QuestionApprovalError("source bank status is not approvable")
    if bank.get("question_count") != 1000:
        raise QuestionApprovalError("source bank must declare exactly 1000 questions")

    raw_questions = bank.get("questions")
    if not isinstance(raw_questions, list) or len(raw_questions) != 1000:
        raise QuestionApprovalError("source bank must contain exactly 1000 questions")
    if any(not isinstance(question, Mapping) for question in raw_questions):
        raise QuestionApprovalError("every source-bank question must be an object")

    questions: list[Mapping[str, object]] = list(raw_questions)
    ids: list[str] = []
    for index, question in enumerate(questions):
        question_id = question.get("id")
        text = question.get("question")
        if not isinstance(question_id, str) or not question_id.strip():
            raise QuestionApprovalError(f"question {index} has an invalid ID")
        if not isinstance(text, str) or not text.strip():
            raise QuestionApprovalError(f"question {question_id} has invalid text")
        if question.get("evaluation_annotation_status") != QUESTION_STATUS:
            raise QuestionApprovalError(f"question {question_id} is not an unannotated draft")
        if question.get("question_sha256") != _text_sha256(text):
            raise QuestionApprovalError(f"question {question_id} text SHA-256 mismatch")
        if question_scope_sha256(question) is None:
            raise QuestionApprovalError(f"question {question_id} has incomplete approval scope")
        ids.append(question_id)

    if len(set(ids)) != 1000:
        raise QuestionApprovalError("source bank contains duplicate question IDs")
    return questions


def build_question_approval_manifest(
    bank: Mapping[str, object],
    *,
    approved_by: str,
    approved_at: datetime,
    confirmed_question_set_sha256: str | None,
    confirmed_question_scope_set_sha256: str | None,
) -> ExperimentDQuestionApprovalManifest:
    """Validate explicit confirmations and build the question-only manifest."""

    if not approved_by.strip():
        raise QuestionApprovalError("approved_by must not be blank")
    if not _timezone_aware(approved_at):
        raise QuestionApprovalError("approved_at must include a timezone offset")
    if confirmed_question_set_sha256 is None or confirmed_question_scope_set_sha256 is None:
        raise QuestionApprovalError("both question-set SHA-256 confirmations are required")

    questions = _validated_questions(bank)
    calculated_question_set_sha256 = _question_set_sha256(questions)
    calculated_scope_set_sha256 = question_scope_set_sha256(questions)
    if calculated_scope_set_sha256 is None:  # pragma: no cover - guarded per question above
        raise QuestionApprovalError("question scope set is incomplete")

    declared_question_set_sha256 = bank.get("question_set_sha256")
    declared_scope_set_sha256 = bank.get("question_scope_set_sha256")
    if declared_question_set_sha256 != calculated_question_set_sha256:
        raise QuestionApprovalError("source bank question_set_sha256 does not match its questions")
    if declared_scope_set_sha256 != calculated_scope_set_sha256:
        raise QuestionApprovalError(
            "source bank question_scope_set_sha256 does not match its question scopes"
        )
    if confirmed_question_set_sha256 != declared_question_set_sha256:
        raise QuestionApprovalError("question-set SHA-256 confirmation does not match")
    if confirmed_question_scope_set_sha256 != declared_scope_set_sha256:
        raise QuestionApprovalError("question-scope-set SHA-256 confirmation does not match")

    payload = {
        "schema_version": 1,
        "manifest_version": "experiment-d-lay-energy-question-approval-v1",
        "status": "approved",
        "decision_scope": "question_text_and_scope_only",
        "approved_by": approved_by,
        "approved_at": approved_at,
        "source_bank": {
            "bank_version": BANK_VERSION,
            "question_count": 1000,
            "question_set_sha256": calculated_question_set_sha256,
            "question_scope_set_sha256": calculated_scope_set_sha256,
        },
        "questions": [
            {
                "id": str(question["id"]),
                "question_sha256": str(question["question_sha256"]),
                "question_scope_sha256": question_scope_sha256(question),
                "status": "approved",
            }
            for question in questions
        ],
    }
    return ExperimentDQuestionApprovalManifest.model_validate(payload)


def load_question_bank(path: Path) -> Mapping[str, object]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise QuestionApprovalError(f"could not read source bank: {path}") from error
    if not isinstance(value, Mapping):
        raise QuestionApprovalError("source bank root must be an object")
    return value


def atomic_write_manifest(
    output: Path,
    manifest: ExperimentDQuestionApprovalManifest,
) -> str:
    """Atomically publish a manifest without replacing an existing approval."""

    serialized = (
        json.dumps(
            manifest.model_dump(mode="json"),
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
            raise QuestionApprovalError(f"approval output already exists: {output}") from error
        with suppress(OSError):
            directory_descriptor = os.open(output.parent, os.O_RDONLY)
            try:
                os.fsync(directory_descriptor)
            finally:
                os.close(directory_descriptor)
    finally:
        with suppress(OSError):
            temporary.unlink(missing_ok=True)
    return hashlib.sha256(encoded).hexdigest()


def create_question_approval(
    input_path: Path,
    output_path: Path,
    *,
    approved_by: str,
    approved_at: datetime,
    confirmed_question_set_sha256: str | None,
    confirmed_question_scope_set_sha256: str | None,
) -> tuple[ExperimentDQuestionApprovalManifest, str]:
    bank = load_question_bank(input_path)
    manifest = build_question_approval_manifest(
        bank,
        approved_by=approved_by,
        approved_at=approved_at,
        confirmed_question_set_sha256=confirmed_question_set_sha256,
        confirmed_question_scope_set_sha256=confirmed_question_scope_set_sha256,
    )
    output_sha256 = atomic_write_manifest(output_path, manifest)
    return manifest, output_sha256


def _arguments(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create an explicit question-only approval manifest for Experiment D"
    )
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--approved-by", required=True)
    parser.add_argument(
        "--approved-at",
        required=True,
        help="ISO 8601 timestamp with an explicit timezone offset",
    )
    parser.add_argument("--confirm-question-set-sha256", required=True)
    parser.add_argument("--confirm-question-scope-set-sha256", required=True)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _arguments(argv)
    manifest, output_sha256 = create_question_approval(
        args.input,
        args.output,
        approved_by=args.approved_by,
        approved_at=parse_approved_at(args.approved_at),
        confirmed_question_set_sha256=args.confirm_question_set_sha256,
        confirmed_question_scope_set_sha256=args.confirm_question_scope_set_sha256,
    )
    print(f"approval_manifest={args.output}")
    print(f"approval_manifest_sha256={output_sha256}")
    print(f"approved_question_count={len(manifest.questions)}")
    return 0


if __name__ == "__main__":  # pragma: no cover - exercised through the public functions
    raise SystemExit(main())
