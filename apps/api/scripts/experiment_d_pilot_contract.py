"""Strict, non-gold contract for an Experiment D annotation pilot worklist.

The worklist deliberately contains only user-approved question identity and scope.
It is not an ``ExperimentDGoldDataset`` and cannot contain answers, qrels, or
retriever-produced candidates.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from collections.abc import Mapping
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

Sha256 = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]
NonBlankStr = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class StrictPilotModel(BaseModel):
    """Reject undeclared annotation or gold fields at every contract level."""

    model_config = ConfigDict(extra="forbid")


class PilotSourceBankBinding(StrictPilotModel):
    artifact: NonBlankStr
    bank_version: Literal["experiment-d-lay-energy-query-bank-v1-draft"]
    question_count: Literal[1000]
    question_set_sha256: Sha256
    question_scope_set_sha256: Sha256
    file_sha256: Sha256


class PilotQuestionApprovalBinding(StrictPilotModel):
    artifact: NonBlankStr
    manifest_version: Literal["experiment-d-lay-energy-question-approval-v1"]
    status: Literal["approved"]
    decision_scope: Literal["question_text_and_scope_only"]
    canonical_payload_sha256: Sha256
    file_sha256: Sha256


class PilotSelection(StrictPilotModel):
    method: Literal["explicit_exactly_10_scenario_families"]
    scenario_family_ids: list[NonBlankStr] = Field(min_length=10, max_length=10)
    questions_per_family: Literal[5]
    question_count: Literal[50]

    @model_validator(mode="after")
    def family_ids_are_distinct(self) -> PilotSelection:
        if len(set(self.scenario_family_ids)) != 10:
            raise ValueError("pilot selection must contain 10 distinct scenario family IDs")
        return self


class PilotQuestion(StrictPilotModel):
    id: NonBlankStr
    question: NonBlankStr
    question_sha256: Sha256
    question_scope_sha256: Sha256
    intent: NonBlankStr
    technology: NonBlankStr
    question_style: NonBlankStr
    scenario_family_id: NonBlankStr

    @model_validator(mode="after")
    def identity_hashes_match_question_and_scope(self) -> PilotQuestion:
        if hashlib.sha256(self.question.encode("utf-8")).hexdigest() != self.question_sha256:
            raise ValueError("pilot question text SHA-256 mismatch")
        scope_payload = {
            "id": self.id,
            "question": self.question,
            "scenario_family_id": self.scenario_family_id,
            "intent": self.intent,
            "technology": self.technology,
            "question_style": self.question_style,
        }
        if canonical_json_sha256(scope_payload) != self.question_scope_sha256:
            raise ValueError("pilot question scope SHA-256 mismatch")
        return self


class ExperimentDPilotAnnotationWorklist(StrictPilotModel):
    """A question-only handoff that is explicitly not an approved gold dataset."""

    schema_version: Literal[1]
    worklist_version: Literal["experiment-d-lay-energy-pilot-worklist-v1"]
    artifact_class: Literal["not_gold"]
    status: Literal["draft_for_annotation"]
    purpose: Literal["question_only_pilot_annotation_worklist"]
    source_bank: PilotSourceBankBinding
    question_approval: PilotQuestionApprovalBinding
    selection: PilotSelection
    questions: list[PilotQuestion] = Field(min_length=50, max_length=50)

    @model_validator(mode="after")
    def selection_matches_questions(self) -> ExperimentDPilotAnnotationWorklist:
        question_ids = [question.id for question in self.questions]
        if len(set(question_ids)) != 50:
            raise ValueError("pilot worklist must contain 50 distinct question IDs")

        selected_families = self.selection.scenario_family_ids
        family_counts = Counter(question.scenario_family_id for question in self.questions)
        if set(family_counts) != set(selected_families):
            raise ValueError("pilot questions do not match the selected scenario families")
        if any(family_counts[family_id] != 5 for family_id in selected_families):
            raise ValueError("each selected scenario family must contribute exactly 5 questions")
        return self


def canonical_json_sha256(value: object) -> str:
    """Hash a JSON-compatible value without file formatting bytes."""

    return hashlib.sha256(
        json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()


def canonical_pilot_worklist_payload_sha256(
    worklist: ExperimentDPilotAnnotationWorklist | Mapping[str, object],
) -> str:
    """Return the canonical payload identity, distinct from serialized file bytes."""

    validated = (
        worklist
        if isinstance(worklist, ExperimentDPilotAnnotationWorklist)
        else ExperimentDPilotAnnotationWorklist.model_validate(worklist)
    )
    return canonical_json_sha256(validated.model_dump(mode="json"))


__all__ = [
    "ExperimentDPilotAnnotationWorklist",
    "PilotQuestion",
    "PilotQuestionApprovalBinding",
    "PilotSelection",
    "PilotSourceBankBinding",
    "canonical_json_sha256",
    "canonical_pilot_worklist_payload_sha256",
]
