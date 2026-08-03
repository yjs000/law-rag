from __future__ import annotations

import copy
import hashlib
import json
from datetime import datetime
from pathlib import Path

import pytest

from scripts.create_experiment_d_question_approval import (
    QuestionApprovalError,
    build_question_approval_manifest,
    create_question_approval,
    main,
    parse_approved_at,
)
from scripts.experiment_d_question_identity import question_scope_set_sha256


def _canonical_sha256(value: object) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()


def _bank() -> dict[str, object]:
    questions: list[dict[str, object]] = []
    for index in range(1, 1001):
        text = f"일반 사용자 질문 {index}은 무엇을 준비해야 하나요?"
        questions.append(
            {
                "id": f"lay-energy-{index:04d}",
                "question": text,
                "intent": f"intent-{(index - 1) // 5:03d}",
                "technology": "renewable_energy",
                "question_style": f"style-{(index - 1) % 5}",
                "scenario_family_id": f"family-{(index - 1) // 5:03d}",
                "evaluation_annotation_status": "not_annotated",
                "question_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
            }
        )
    question_set_sha256 = _canonical_sha256(
        [{"id": item["id"], "question": item["question"]} for item in questions]
    )
    scope_set_sha256 = question_scope_set_sha256(questions)
    assert scope_set_sha256 is not None
    return {
        "schema_version": 1,
        "bank_version": "experiment-d-lay-energy-query-bank-v1-draft",
        "status": "draft_for_human_question_review",
        "question_count": 1000,
        "question_set_sha256": question_set_sha256,
        "question_scope_set_sha256": scope_set_sha256,
        "questions": questions,
    }


def _build(bank: dict[str, object]):
    return build_question_approval_manifest(
        bank,
        approved_by="question-owner",
        approved_at=datetime.fromisoformat("2026-08-03T12:30:00+09:00"),
        confirmed_question_set_sha256=str(bank["question_set_sha256"]),
        confirmed_question_scope_set_sha256=str(bank["question_scope_set_sha256"]),
    )


def test_explicit_confirmations_create_valid_question_only_manifest(tmp_path: Path) -> None:
    bank = _bank()
    input_path = tmp_path / "bank.json"
    output_path = tmp_path / "approval.json"
    input_path.write_text(json.dumps(bank, ensure_ascii=False), encoding="utf-8")

    manifest, canonical_manifest_sha256, manifest_file_sha256 = create_question_approval(
        input_path,
        output_path,
        approved_by="question-owner",
        approved_at=parse_approved_at("2026-08-03T12:30:00+09:00"),
        confirmed_question_set_sha256=str(bank["question_set_sha256"]),
        confirmed_question_scope_set_sha256=str(bank["question_scope_set_sha256"]),
    )

    persisted = json.loads(output_path.read_text(encoding="utf-8"))
    assert manifest.decision_scope == "question_text_and_scope_only"
    assert len(manifest.questions) == 1000
    assert persisted["source_bank"]["question_set_sha256"] == bank["question_set_sha256"]
    assert (
        persisted["source_bank"]["question_scope_set_sha256"] == (bank["question_scope_set_sha256"])
    )
    assert set(persisted["questions"][0]) == {
        "id",
        "question_sha256",
        "question_scope_sha256",
        "status",
    }
    assert "qrels" not in output_path.read_text(encoding="utf-8")
    assert "answer" not in output_path.read_text(encoding="utf-8")
    assert canonical_manifest_sha256 == _canonical_sha256(persisted)
    assert manifest_file_sha256 == hashlib.sha256(output_path.read_bytes()).hexdigest()
    assert canonical_manifest_sha256 != manifest_file_sha256


def test_cli_prints_canonical_binding_hash_and_distinct_file_hash(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    bank = _bank()
    input_path = tmp_path / "bank.json"
    output_path = tmp_path / "approval.json"
    input_path.write_text(json.dumps(bank, ensure_ascii=False), encoding="utf-8")

    exit_code = main(
        [
            "--input",
            str(input_path),
            "--output",
            str(output_path),
            "--approved-by",
            "question-owner",
            "--approved-at",
            "2026-08-03T12:30:00+09:00",
            "--confirm-question-set-sha256",
            str(bank["question_set_sha256"]),
            "--confirm-question-scope-set-sha256",
            str(bank["question_scope_set_sha256"]),
        ]
    )

    output = dict(
        line.split("=", 1) for line in capsys.readouterr().out.splitlines() if "=" in line
    )
    persisted = json.loads(output_path.read_text(encoding="utf-8"))
    assert exit_code == 0
    assert output["approval_manifest_sha256"] == _canonical_sha256(persisted)
    assert (
        output["approval_manifest_file_sha256"]
        == hashlib.sha256(output_path.read_bytes()).hexdigest()
    )
    assert output["approval_manifest_sha256"] != output["approval_manifest_file_sha256"]
    assert output["approved_question_count"] == "1000"


@pytest.mark.parametrize(
    ("question_set_confirmation", "scope_set_confirmation", "message"),
    [
        (None, None, "both question-set SHA-256 confirmations are required"),
        ("0" * 64, "scope", "question-set SHA-256 confirmation does not match"),
        ("question", "0" * 64, "question-scope-set SHA-256 confirmation does not match"),
    ],
)
def test_missing_or_wrong_confirmations_are_rejected(
    question_set_confirmation: str | None,
    scope_set_confirmation: str | None,
    message: str,
) -> None:
    bank = _bank()
    if question_set_confirmation == "question":
        question_set_confirmation = str(bank["question_set_sha256"])
    if scope_set_confirmation == "scope":
        scope_set_confirmation = str(bank["question_scope_set_sha256"])

    with pytest.raises(QuestionApprovalError, match=message):
        build_question_approval_manifest(
            bank,
            approved_by="question-owner",
            approved_at=datetime.fromisoformat("2026-08-03T12:30:00+09:00"),
            confirmed_question_set_sha256=question_set_confirmation,
            confirmed_question_scope_set_sha256=scope_set_confirmation,
        )


@pytest.mark.parametrize("tamper", ["text", "scope", "duplicate_id", "status"])
def test_tampered_source_bank_is_rejected(tamper: str) -> None:
    bank = _bank()
    changed = copy.deepcopy(bank)
    questions = changed["questions"]
    assert isinstance(questions, list)
    first = questions[0]
    assert isinstance(first, dict)
    if tamper == "text":
        first["question"] = "승인 후 몰래 바꾼 질문인가요?"
    elif tamper == "scope":
        first["technology"] = "changed_scope"
    elif tamper == "duplicate_id":
        second = questions[1]
        assert isinstance(second, dict)
        second["id"] = first["id"]
    else:
        changed["status"] = "approved"

    with pytest.raises(QuestionApprovalError):
        _build(changed)


def test_naive_approval_time_is_rejected() -> None:
    bank = _bank()

    with pytest.raises(QuestionApprovalError, match="timezone offset"):
        build_question_approval_manifest(
            bank,
            approved_by="question-owner",
            approved_at=datetime(2026, 8, 3, 12, 30),
            confirmed_question_set_sha256=str(bank["question_set_sha256"]),
            confirmed_question_scope_set_sha256=str(bank["question_scope_set_sha256"]),
        )
    with pytest.raises(QuestionApprovalError, match="timezone offset"):
        parse_approved_at("2026-08-03T12:30:00")


def test_atomic_output_is_never_overwritten(tmp_path: Path) -> None:
    bank = _bank()
    input_path = tmp_path / "bank.json"
    output_path = tmp_path / "approval.json"
    input_path.write_text(json.dumps(bank, ensure_ascii=False), encoding="utf-8")
    kwargs = {
        "approved_by": "question-owner",
        "approved_at": datetime.fromisoformat("2026-08-03T12:30:00+09:00"),
        "confirmed_question_set_sha256": str(bank["question_set_sha256"]),
        "confirmed_question_scope_set_sha256": str(bank["question_scope_set_sha256"]),
    }
    create_question_approval(input_path, output_path, **kwargs)
    original = output_path.read_bytes()

    with pytest.raises(QuestionApprovalError, match="already exists"):
        create_question_approval(input_path, output_path, **kwargs)

    assert output_path.read_bytes() == original
    assert list(tmp_path.glob("*.tmp")) == []
