from __future__ import annotations

import copy
import hashlib

import pytest
from pydantic import ValidationError

from scripts.experiment_d_gold_contract import ExperimentDGoldDataset
from scripts.experiment_d_pilot_contract import (
    ExperimentDPilotAnnotationWorklist,
    canonical_pilot_worklist_payload_sha256,
)
from scripts.experiment_d_question_identity import question_scope_sha256


def _question(index: int, family_index: int) -> dict[str, str]:
    question = {
        "id": f"question-{index:03d}",
        "question": f"일반 사용자 질문 {index}은 무엇을 준비해야 하나요?",
        "question_sha256": "",
        "intent": f"intent-{family_index:02d}",
        "technology": "renewable_energy",
        "question_style": f"style-{index % 5}",
        "scenario_family_id": f"family-{family_index:02d}",
    }
    question["question_sha256"] = hashlib.sha256(question["question"].encode("utf-8")).hexdigest()
    scope_sha256 = question_scope_sha256(question)
    assert scope_sha256 is not None
    question["question_scope_sha256"] = scope_sha256
    return question


def _worklist() -> dict[str, object]:
    family_ids = [f"family-{family_index:02d}" for family_index in range(10)]
    questions = [
        _question((family_index * 5) + offset + 1, family_index)
        for family_index in range(10)
        for offset in range(5)
    ]
    return {
        "schema_version": 1,
        "worklist_version": "experiment-d-lay-energy-pilot-worklist-v1",
        "artifact_class": "not_gold",
        "status": "draft_for_annotation",
        "purpose": "question_only_pilot_annotation_worklist",
        "source_bank": {
            "artifact": "question-bank.json",
            "bank_version": "experiment-d-lay-energy-query-bank-v1-draft",
            "question_count": 1000,
            "question_set_sha256": "a" * 64,
            "question_scope_set_sha256": "b" * 64,
            "file_sha256": "c" * 64,
        },
        "question_approval": {
            "artifact": "approval.json",
            "manifest_version": "experiment-d-lay-energy-question-approval-v1",
            "status": "approved",
            "decision_scope": "question_text_and_scope_only",
            "canonical_payload_sha256": "d" * 64,
            "file_sha256": "e" * 64,
        },
        "selection": {
            "method": "explicit_exactly_10_scenario_families",
            "scenario_family_ids": family_ids,
            "questions_per_family": 5,
            "question_count": 50,
        },
        "questions": questions,
    }


def test_contract_is_explicitly_non_gold_and_question_only() -> None:
    worklist = ExperimentDPilotAnnotationWorklist.model_validate(_worklist())

    assert worklist.artifact_class == "not_gold"
    assert worklist.status == "draft_for_annotation"
    assert len(worklist.questions) == 50
    with pytest.raises(ValidationError):
        ExperimentDGoldDataset.model_validate(worklist.model_dump(mode="json"))


@pytest.mark.parametrize("forbidden_field", ["answer", "qrels", "retriever_candidates"])
def test_gold_or_generated_fields_are_forbidden(forbidden_field: str) -> None:
    payload = copy.deepcopy(_worklist())
    questions = payload["questions"]
    assert isinstance(questions, list)
    first = questions[0]
    assert isinstance(first, dict)
    first[forbidden_field] = []

    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        ExperimentDPilotAnnotationWorklist.model_validate(payload)


@pytest.mark.parametrize("tamper", ["duplicate_family", "wrong_family_count", "duplicate_question"])
def test_selection_and_question_cardinality_are_fail_closed(tamper: str) -> None:
    payload = copy.deepcopy(_worklist())
    selection = payload["selection"]
    questions = payload["questions"]
    assert isinstance(selection, dict)
    assert isinstance(questions, list)
    if tamper == "duplicate_family":
        family_ids = selection["scenario_family_ids"]
        assert isinstance(family_ids, list)
        family_ids[-1] = family_ids[0]
    elif tamper == "wrong_family_count":
        question = questions[-1]
        assert isinstance(question, dict)
        question["scenario_family_id"] = "family-00"
    else:
        first = questions[0]
        second = questions[1]
        assert isinstance(first, dict)
        assert isinstance(second, dict)
        second["id"] = first["id"]

    with pytest.raises(ValidationError):
        ExperimentDPilotAnnotationWorklist.model_validate(payload)


def test_canonical_payload_hash_is_format_independent_and_tamper_sensitive() -> None:
    payload = _worklist()
    validated = ExperimentDPilotAnnotationWorklist.model_validate(payload)
    baseline = canonical_pilot_worklist_payload_sha256(validated)

    assert baseline == canonical_pilot_worklist_payload_sha256(payload)
    changed = copy.deepcopy(payload)
    questions = changed["questions"]
    assert isinstance(questions, list)
    first = questions[0]
    assert isinstance(first, dict)
    first["question"] = "변경된 질문"
    with pytest.raises(ValidationError, match="text SHA-256 mismatch"):
        canonical_pilot_worklist_payload_sha256(changed)
