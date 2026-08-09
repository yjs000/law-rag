from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.experiment_d_manual_review_contract import (
    DEFAULT_APPROVAL_MANIFEST,
    DEFAULT_QUESTION_INPUT,
    DEFAULT_SOURCE_BANK,
    ManualPilotInputError,
    _file_sha256,
    load_manual_pilot_artifacts,
)


def _copy_json(path: Path, destination: Path) -> dict[str, object]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    destination.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return payload


def test_frozen_d10_input_resolves_exactly_ten_approved_questions() -> None:
    artifacts = load_manual_pilot_artifacts()

    assert len(artifacts.questions) == 10
    assert len({question.id for question in artifacts.questions}) == 10
    assert artifacts.questions[0].id == "lay-energy-0201"
    assert artifacts.questions[-1].id == "lay-energy-0943"
    assert all(question.question for question in artifacts.questions)
    assert artifacts.approval_manifest_payload_sha256 == (
        "d41f6a206fec705a2e99b2b9543a6472cd5c5c067fc3a2a530e31a9a08fde869"
    )


def test_d10_input_rejects_answer_or_qrel_fields(tmp_path: Path) -> None:
    input_path = tmp_path / "questions.json"
    payload = _copy_json(DEFAULT_QUESTION_INPUT, input_path)
    questions = payload["questions"]
    assert isinstance(questions, list)
    questions[0]["qrels"] = []
    input_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    with pytest.raises(ManualPilotInputError, match="input contract is invalid"):
        load_manual_pilot_artifacts(input_path)


def test_d10_input_rejects_question_hash_drift(tmp_path: Path) -> None:
    input_path = tmp_path / "questions.json"
    payload = _copy_json(DEFAULT_QUESTION_INPUT, input_path)
    questions = payload["questions"]
    assert isinstance(questions, list)
    questions[0]["question_sha256"] = "0" * 64
    input_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    with pytest.raises(ManualPilotInputError, match="question SHA-256 mismatch"):
        load_manual_pilot_artifacts(input_path)


def test_d10_input_rejects_source_bank_byte_drift(tmp_path: Path) -> None:
    bank_path = tmp_path / "bank.json"
    _copy_json(DEFAULT_SOURCE_BANK, bank_path)

    with pytest.raises(ManualPilotInputError, match="source-bank file SHA-256 mismatch"):
        load_manual_pilot_artifacts(
            DEFAULT_QUESTION_INPUT,
            bank_path,
            DEFAULT_APPROVAL_MANIFEST,
        )


def test_file_sha256_is_independent_of_json_line_endings() -> None:
    assert _file_sha256(b'{"value": 1}\r\n') == _file_sha256(b'{"value": 1}\n')
