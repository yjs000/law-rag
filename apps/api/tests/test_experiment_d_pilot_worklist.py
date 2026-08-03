from __future__ import annotations

import copy
import hashlib
import json
from datetime import datetime
from pathlib import Path

import pytest

from scripts.create_experiment_d_pilot_worklist import (
    PilotWorklistError,
    build_pilot_worklist,
    create_pilot_worklist,
    main,
)
from scripts.experiment_d_gold_contract import ExperimentDQuestionApprovalManifest
from scripts.experiment_d_pilot_contract import canonical_json_sha256
from scripts.experiment_d_question_identity import (
    question_scope_set_sha256,
    question_scope_sha256,
)


def _refresh_bank_hashes(bank: dict[str, object]) -> None:
    questions = bank["questions"]
    assert isinstance(questions, list)
    bank["question_set_sha256"] = canonical_json_sha256(
        [{"id": question["id"], "question": question["question"]} for question in questions]
    )
    scope_set_sha256 = question_scope_set_sha256(questions)
    assert scope_set_sha256 is not None
    bank["question_scope_set_sha256"] = scope_set_sha256


def _bank() -> dict[str, object]:
    questions: list[dict[str, object]] = []
    for index in range(1, 1001):
        family_index = (index - 1) // 5
        text = f"일반 사용자 질문 {index}은 무엇을 준비해야 하나요?"
        questions.append(
            {
                "id": f"lay-energy-{index:04d}",
                "question": text,
                "intent": f"intent-{family_index:03d}",
                "technology": "renewable_energy",
                "question_style": f"style-{(index - 1) % 5}",
                "scenario_family_id": f"family-{family_index:03d}",
                "evaluation_annotation_status": "not_annotated",
                "question_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
            }
        )
    bank: dict[str, object] = {
        "schema_version": 1,
        "bank_version": "experiment-d-lay-energy-query-bank-v1-draft",
        "status": "draft_for_human_question_review",
        "question_count": 1000,
        "questions": questions,
    }
    _refresh_bank_hashes(bank)
    return bank


def _approval(bank: dict[str, object]) -> dict[str, object]:
    questions = bank["questions"]
    assert isinstance(questions, list)
    manifest = ExperimentDQuestionApprovalManifest.model_validate(
        {
            "schema_version": 1,
            "manifest_version": "experiment-d-lay-energy-question-approval-v1",
            "status": "approved",
            "decision_scope": "question_text_and_scope_only",
            "approved_by": "question-owner",
            "approved_at": datetime.fromisoformat("2026-08-03T12:30:00+09:00"),
            "source_bank": {
                "bank_version": bank["bank_version"],
                "question_count": bank["question_count"],
                "question_set_sha256": bank["question_set_sha256"],
                "question_scope_set_sha256": bank["question_scope_set_sha256"],
            },
            "questions": [
                {
                    "id": question["id"],
                    "question_sha256": question["question_sha256"],
                    "question_scope_sha256": question_scope_sha256(question),
                    "status": "approved",
                }
                for question in questions
            ],
        }
    )
    return manifest.model_dump(mode="json")


def _families() -> list[str]:
    return [f"family-{index:03d}" for index in range(10)]


def _write_inputs(tmp_path: Path) -> tuple[Path, Path, dict[str, object], dict[str, object], str]:
    bank = _bank()
    approval = _approval(bank)
    bank_path = tmp_path / "bank.json"
    approval_path = tmp_path / "approval.json"
    bank_path.write_text(json.dumps(bank, ensure_ascii=False, indent=2), encoding="utf-8")
    approval_path.write_text(json.dumps(approval, ensure_ascii=False, indent=2), encoding="utf-8")
    approval_sha256 = canonical_json_sha256(approval)
    return bank_path, approval_path, bank, approval, approval_sha256


def _all_keys(value: object) -> set[str]:
    keys: set[str] = set()
    if isinstance(value, dict):
        keys.update(str(key) for key in value)
        for child in value.values():
            keys.update(_all_keys(child))
    elif isinstance(value, list):
        for child in value:
            keys.update(_all_keys(child))
    return keys


def test_create_question_only_pilot_preserves_all_approved_identity_fields(
    tmp_path: Path,
) -> None:
    bank_path, approval_path, bank, approval, approval_sha256 = _write_inputs(tmp_path)
    output_path = tmp_path / "pilot.json"

    worklist, payload_sha256, file_sha256 = create_pilot_worklist(
        bank_path,
        approval_path,
        output_path,
        confirmed_approval_manifest_sha256=approval_sha256,
        scenario_family_ids=_families(),
    )

    persisted = json.loads(output_path.read_text(encoding="utf-8"))
    source_questions = bank["questions"]
    assert isinstance(source_questions, list)
    expected_first = source_questions[0]
    actual_first = persisted["questions"][0]
    assert worklist.artifact_class == "not_gold"
    assert worklist.status == "draft_for_annotation"
    assert len(worklist.questions) == 50
    assert persisted["selection"]["scenario_family_ids"] == _families()
    for field in (
        "id",
        "question",
        "question_sha256",
        "intent",
        "technology",
        "question_style",
        "scenario_family_id",
    ):
        assert actual_first[field] == expected_first[field]
    assert actual_first["question_scope_sha256"] == question_scope_sha256(expected_first)
    assert persisted["question_approval"]["canonical_payload_sha256"] == approval_sha256
    assert (
        persisted["question_approval"]["file_sha256"]
        == hashlib.sha256(approval_path.read_bytes()).hexdigest()
    )
    assert (
        persisted["source_bank"]["file_sha256"]
        == hashlib.sha256(bank_path.read_bytes()).hexdigest()
    )
    assert payload_sha256 == canonical_json_sha256(persisted)
    assert file_sha256 == hashlib.sha256(output_path.read_bytes()).hexdigest()
    assert payload_sha256 != file_sha256
    assert _all_keys(persisted).isdisjoint(
        {"answer", "qrels", "reference_response", "retriever_candidates", "candidate_nodes"}
    )
    assert approval["status"] == "approved"


def test_cli_requires_explicit_families_and_prints_distinct_hash_identities(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    bank_path, approval_path, _, _, approval_sha256 = _write_inputs(tmp_path)
    output_path = tmp_path / "pilot.json"
    args = [
        "--source-bank",
        str(bank_path),
        "--approval-manifest",
        str(approval_path),
        "--output",
        str(output_path),
        "--confirm-approval-manifest-sha256",
        approval_sha256,
    ]
    for family_id in _families():
        args.extend(["--scenario-family-id", family_id])

    assert main(args) == 0

    output = dict(
        line.split("=", 1) for line in capsys.readouterr().out.splitlines() if "=" in line
    )
    persisted = json.loads(output_path.read_text(encoding="utf-8"))
    assert output["pilot_worklist_payload_sha256"] == canonical_json_sha256(persisted)
    assert (
        output["pilot_worklist_file_sha256"] == hashlib.sha256(output_path.read_bytes()).hexdigest()
    )
    assert output["pilot_worklist_payload_sha256"] != output["pilot_worklist_file_sha256"]
    assert output["artifact_class"] == "not_gold"
    assert output["status"] == "draft_for_annotation"
    assert output["selected_scenario_family_count"] == "10"
    assert output["pilot_question_count"] == "50"


@pytest.mark.parametrize("tamper", ["question_text", "question_scope"])
def test_question_or_scope_change_after_approval_is_rejected(
    tmp_path: Path,
    tamper: str,
) -> None:
    bank_path, approval_path, bank, _, approval_sha256 = _write_inputs(tmp_path)
    changed = copy.deepcopy(bank)
    questions = changed["questions"]
    assert isinstance(questions, list)
    first = questions[0]
    assert isinstance(first, dict)
    if tamper == "question_text":
        first["question"] = "승인 뒤 바뀐 질문은 무엇인가요?"
        first["question_sha256"] = hashlib.sha256(
            str(first["question"]).encode("utf-8")
        ).hexdigest()
    else:
        first["technology"] = "changed_technology"
    _refresh_bank_hashes(changed)
    bank_path.write_text(json.dumps(changed, ensure_ascii=False), encoding="utf-8")

    with pytest.raises(PilotWorklistError, match="approval manifest"):
        create_pilot_worklist(
            bank_path,
            approval_path,
            tmp_path / "must-not-exist.json",
            confirmed_approval_manifest_sha256=approval_sha256,
            scenario_family_ids=_families(),
        )
    assert not (tmp_path / "must-not-exist.json").exists()


def test_unapproved_or_rebound_manifest_is_rejected(tmp_path: Path) -> None:
    bank_path, approval_path, bank, approval, _ = _write_inputs(tmp_path)
    unapproved = copy.deepcopy(approval)
    unapproved["status"] = "draft_for_review"
    approval_path.write_text(json.dumps(unapproved, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(PilotWorklistError, match="invalid or unapproved"):
        create_pilot_worklist(
            bank_path,
            approval_path,
            tmp_path / "unapproved.json",
            confirmed_approval_manifest_sha256=canonical_json_sha256(unapproved),
            scenario_family_ids=_families(),
        )

    changed_approval = _approval(bank)
    approved_questions = changed_approval["questions"]
    assert isinstance(approved_questions, list)
    first = approved_questions[0]
    assert isinstance(first, dict)
    first["question_sha256"] = "f" * 64
    approval_path.write_text(json.dumps(changed_approval, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(PilotWorklistError, match="exact ordered source-bank questions"):
        create_pilot_worklist(
            bank_path,
            approval_path,
            tmp_path / "rebound.json",
            confirmed_approval_manifest_sha256=canonical_json_sha256(changed_approval),
            scenario_family_ids=_families(),
        )


def test_manifest_canonical_confirmation_is_required_and_exact(tmp_path: Path) -> None:
    bank_path, approval_path, _, _, _ = _write_inputs(tmp_path)

    for confirmation in (None, "0" * 64):
        with pytest.raises(PilotWorklistError, match="canonical SHA-256"):
            create_pilot_worklist(
                bank_path,
                approval_path,
                tmp_path / f"no-output-{confirmation}.json",
                confirmed_approval_manifest_sha256=confirmation,
                scenario_family_ids=_families(),
            )


@pytest.mark.parametrize(
    ("family_ids", "message"),
    [
        ([f"family-{index:03d}" for index in range(9)], "exactly 10"),
        ([f"family-{index:03d}" for index in range(11)], "exactly 10"),
        (_families()[:-1] + [_families()[0]], "must be distinct"),
        (_families()[:-1] + ["family-unknown"], "unknown scenario family"),
    ],
)
def test_selection_requires_exactly_10_distinct_existing_families(
    family_ids: list[str],
    message: str,
) -> None:
    bank = _bank()
    approval = _approval(bank)

    with pytest.raises(PilotWorklistError, match=message):
        build_pilot_worklist(
            bank,
            approval,
            source_bank_artifact="bank.json",
            source_bank_file_sha256="a" * 64,
            approval_manifest_artifact="approval.json",
            approval_manifest_file_sha256="b" * 64,
            confirmed_approval_manifest_sha256=canonical_json_sha256(approval),
            scenario_family_ids=family_ids,
        )


def test_source_bank_must_remain_200_families_of_five() -> None:
    bank = _bank()
    questions = bank["questions"]
    assert isinstance(questions, list)
    first = questions[0]
    assert isinstance(first, dict)
    first["scenario_family_id"] = "family-001"
    _refresh_bank_hashes(bank)
    approval = _approval(_bank())

    with pytest.raises(PilotWorklistError, match="200 families"):
        build_pilot_worklist(
            bank,
            approval,
            source_bank_artifact="bank.json",
            source_bank_file_sha256="a" * 64,
            approval_manifest_artifact="approval.json",
            approval_manifest_file_sha256="b" * 64,
            confirmed_approval_manifest_sha256=canonical_json_sha256(approval),
            scenario_family_ids=_families(),
        )


def test_atomic_output_is_never_overwritten(tmp_path: Path) -> None:
    bank_path, approval_path, _, _, approval_sha256 = _write_inputs(tmp_path)
    output_path = tmp_path / "pilot.json"
    kwargs = {
        "confirmed_approval_manifest_sha256": approval_sha256,
        "scenario_family_ids": _families(),
    }
    create_pilot_worklist(bank_path, approval_path, output_path, **kwargs)
    original = output_path.read_bytes()

    with pytest.raises(PilotWorklistError, match="already exists"):
        create_pilot_worklist(bank_path, approval_path, output_path, **kwargs)

    assert output_path.read_bytes() == original
    assert [path for path in tmp_path.iterdir() if path.suffix == ".tmp"] == []
