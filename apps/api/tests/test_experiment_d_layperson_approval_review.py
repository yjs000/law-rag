from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

import pytest

from scripts.render_experiment_d_layperson_approval_review import (
    BANK_STATUS,
    BANK_VERSION,
    BROAD_OR_MISSING_FACTS,
    OUTSIDE_CORPUS,
    QUESTION_SCOPE_SET_SHA256,
    QUESTION_SET_SHA256,
    REPRESENTATIVE_IDS,
    RISK_GROUPS,
    TIME_OR_LIVE_DATA,
    ApprovalReviewError,
    main,
    render_approval_review,
    validated_questions,
)

REPOSITORY_ROOT = Path(__file__).parents[3]
BANK_PATH = (
    Path(__file__).parents[1] / "evaluation" / "experiment-d-lay-energy-query-bank-v1-draft.json"
)
REVIEW_PATH = (
    REPOSITORY_ROOT / "docs" / "generated" / "experiment-d-lay-energy-approval-review-v1.md"
)


def _bank() -> dict[str, object]:
    value = json.loads(BANK_PATH.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def test_committed_bank_and_review_match_the_fixed_human_review_contract() -> None:
    bank = _bank()

    rendered = render_approval_review(bank)

    assert rendered == REVIEW_PATH.read_text(encoding="utf-8")
    assert bank["bank_version"] == BANK_VERSION
    assert bank["status"] == BANK_STATUS
    assert bank["question_set_sha256"] == QUESTION_SET_SHA256
    assert bank["question_scope_set_sha256"] == QUESTION_SCOPE_SET_SHA256
    assert len(validated_questions(bank)) == 1000
    assert len(REPRESENTATIVE_IDS) == 15
    assert len(BROAD_OR_MISSING_FACTS) == 14
    assert len(TIME_OR_LIVE_DATA) == 8
    assert len(OUTSIDE_CORPUS) == 13
    assert sum(len(entries) for _title, _key, entries in RISK_GROUPS) == 35
    assert (
        len(
            {
                question_id
                for _title, _key, entries in RISK_GROUPS
                for question_id, _reason in entries
            }
        )
        == 35
    )
    assert "[전체 1,000문항 읽기본](experiment-d-lay-energy-query-bank-v1.md)" in rendered
    assert f"question set SHA-256: `{QUESTION_SET_SHA256}`" in rendered
    assert f"question scope set SHA-256: `{QUESTION_SCOPE_SET_SHA256}`" in rendered
    assert "정답·qrels·검색 후보·점수·검색 결과를 생성하지 않음" in rendered
    assert "clarification_required" in rendered
    assert "partially_answerable" in rendered
    assert "unanswerable" in rendered

    questions = {question["id"]: question for question in bank["questions"]}
    representative_intents = {
        str(questions[question_id]["intent"]) for question_id in REPRESENTATIVE_IDS
    }
    assert len(representative_intents) == 15
    for question_id in REPRESENTATIVE_IDS:
        assert str(questions[question_id]["question"]) in rendered
    for _title, _key, entries in RISK_GROUPS:
        for question_id, reason in entries:
            assert str(questions[question_id]["question"]) in rendered
            assert reason in rendered


def test_render_and_cli_output_are_deterministic(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    bank = _bank()
    first_render = render_approval_review(bank)
    second_render = render_approval_review(copy.deepcopy(bank))
    first_path = tmp_path / "first.md"
    second_path = tmp_path / "second.md"

    assert first_render == second_render
    assert main(["--input", str(BANK_PATH), "--output", str(first_path)]) == 0
    first_stdout = capsys.readouterr().out
    assert main(["--input", str(BANK_PATH), "--output", str(second_path)]) == 0
    second_stdout = capsys.readouterr().out

    assert first_path.read_bytes() == second_path.read_bytes()
    assert hashlib.sha256(first_path.read_bytes()).hexdigest() in first_stdout
    assert hashlib.sha256(second_path.read_bytes()).hexdigest() in second_stdout
    for output in (first_stdout, second_stdout):
        assert "question_count=1000" in output
        assert "answers_generated=false" in output
        assert "qrels_generated=false" in output
        assert "search_executed=false" in output


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("bank_version", "changed-bank"),
        ("status", "approved"),
        ("question_count", 999),
        ("question_set_sha256", "0" * 64),
        ("question_scope_set_sha256", "0" * 64),
    ],
)
def test_changed_bank_identity_is_rejected(field: str, value: object) -> None:
    bank = _bank()
    bank[field] = value

    with pytest.raises(ApprovalReviewError):
        validated_questions(bank)


@pytest.mark.parametrize(
    "tamper",
    [
        "text",
        "id",
        "family",
        "annotation",
        "corpus_title",
        "corpus_date_window",
        "annotation_contract",
    ],
)
def test_changed_question_or_review_context_is_rejected(tamper: str) -> None:
    bank = _bank()
    questions = bank["questions"]
    assert isinstance(questions, list)
    first = questions[0]
    assert isinstance(first, dict)

    if tamper == "text":
        first["question"] = "승인 검토 뒤 바뀐 질문인가요?"
    elif tamper == "id":
        first["id"] = "lay-energy-9999"
    elif tamper == "family":
        first["scenario_family_id"] = "changed-family"
    elif tamper == "annotation":
        first["evaluation_annotation_status"] = "annotated"
    elif tamper == "corpus_title":
        corpus = bank["corpus_context"]
        assert isinstance(corpus, dict)
        titles = corpus["catalog_titles"]
        assert isinstance(titles, list)
        titles[0] = "바뀐 법령"
    elif tamper == "corpus_date_window":
        corpus = bank["corpus_context"]
        assert isinstance(corpus, dict)
        corpus["supported_as_of_from"] = "2026-06-02"
    else:
        contract = bank["annotation_contract"]
        assert isinstance(contract, dict)
        contract["qrels_included"] = True

    with pytest.raises(ApprovalReviewError):
        validated_questions(bank)
