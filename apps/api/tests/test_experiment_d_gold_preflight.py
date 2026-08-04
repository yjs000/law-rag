from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import replace
from datetime import date

import pytest

from app.domain.embedding_profiles import (
    embedding_text_sha256,
    legal_provision_embedding_text,
)
from scripts.experiment_d_corpus import SourceProvision
from scripts.experiment_d_gold_contract import (
    canonical_gold_case_payload_sha256,
    canonical_gold_dataset_sha256,
)
from scripts.experiment_d_question_identity import (
    question_scope_set_sha256,
    question_scope_sha256,
)
from scripts.preflight_experiment_d_gold import (
    APPROVED_GOLD_STATUS,
    NonCurrentParserIdError,
    audit_gold_dataset,
    corpus_fingerprint_sha256,
    question_set_sha256,
)
from tests import test_experiment_d_gold_contract as gold_fixture


def _source(
    provision_id: str = "provision-1",
    *,
    content: str = "제1조(목적) 이 법은 전기사업에 관한 기본 사항을 정한다.",
) -> SourceProvision:
    return SourceProvision(
        provision_id=provision_id,
        version_id="version-1",
        document_id="document-1",
        document_title="전기사업법",
        source_kind="law",
        mst="1",
        effective_from=date(2026, 1, 1),
        effective_to=None,
        source_url="https://open.law.go.kr/mock",
        path="제1조",
        parent_path=None,
        heading="목적",
        content=content,
        ordinal=1,
    )


def _approved_dataset(source: SourceProvision) -> dict[str, object]:
    question = "전기사업 관련 법은 어떤 기본 사항을 정하나요?"
    cases: list[dict[str, object]] = [
        {
            "id": "lay-energy-0001",
            "question": question,
            "question_sha256": hashlib.sha256(question.encode("utf-8")).hexdigest(),
            "question_review_status": "approved",
            "scenario_family_id": "family-001",
            "intent": "법 목적 확인",
            "technology": "electricity",
            "question_style": "plain_question",
            "answerability": "fully_answerable",
            "qrels": [
                {
                    "provision_id": source.provision_id,
                    "document_id": source.document_id,
                    "version_id": source.version_id,
                    "path": source.path,
                    "heading": source.heading,
                    "effective_from": source.effective_from.isoformat(),
                    "effective_to": None,
                    "content_sha256": source.content_sha256,
                    "relevance": 2,
                }
            ],
        }
    ]
    frozen_question_hash = question_set_sha256(cases)
    frozen_scope_hash = question_scope_set_sha256(cases)
    assert frozen_scope_hash is not None
    return {
        "dataset_version": "experiment-d-lay-energy-gold-v1",
        "evaluation_status": APPROVED_GOLD_STATUS,
        "question_set_sha256": frozen_question_hash,
        "source_bank": {
            "artifact": "source-bank.json",
            "bank_version": "source-bank-v1",
            "question_count": 1,
            "question_set_sha256": frozen_question_hash,
            "question_scope_set_sha256": frozen_scope_hash,
            "approval_manifest_artifact": "approval-manifest.json",
            "approval_manifest_sha256": "0" * 64,
        },
        "corpus_snapshot": {
            "snapshot_id": "mvp-current-corpus-2026-08-03",
            "parser_contract_version": "3",
            "searchable_provision_count": 1,
            "fingerprint_sha256": corpus_fingerprint_sha256([source]),
        },
        "cases": cases,
    }


def _source_bank(dataset: dict[str, object]) -> dict[str, object]:
    cases = dataset["cases"]
    scope_hash = question_scope_set_sha256(cases)
    assert scope_hash is not None
    return {
        "bank_version": "source-bank-v1",
        "question_count": 1,
        "question_set_sha256": question_set_sha256(cases),
        "question_scope_set_sha256": scope_hash,
        "questions": [
            {
                "id": case["id"],
                "question": case["question"],
                "scenario_family_id": case["scenario_family_id"],
                "intent": case["intent"],
                "technology": case["technology"],
                "question_style": case["question_style"],
                "question_sha256": hashlib.sha256(case["question"].encode("utf-8")).hexdigest(),
            }
            for case in cases
        ],
    }


def _approval_manifest(source_bank: dict[str, object]) -> dict[str, object]:
    return {
        "schema_version": 1,
        "manifest_version": "experiment-d-lay-energy-question-approval-v1",
        "status": "approved",
        "decision_scope": "question_text_and_scope_only",
        "approved_by": "test-reviewer",
        "approved_at": "2026-08-03T12:00:00+09:00",
        "source_bank": {
            "bank_version": source_bank["bank_version"],
            "question_count": source_bank["question_count"],
            "question_set_sha256": source_bank["question_set_sha256"],
            "question_scope_set_sha256": source_bank["question_scope_set_sha256"],
        },
        "questions": [
            {
                "id": question["id"],
                "question_sha256": question["question_sha256"],
                "question_scope_sha256": question_scope_sha256(question),
                "status": "approved",
            }
            for question in source_bank["questions"]
        ],
    }


def _approval_manifest_sha256(manifest: dict[str, object]) -> str:
    return hashlib.sha256(
        json.dumps(
            manifest,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()


def _full_contract_sources() -> list[SourceProvision]:
    sources: list[SourceProvision] = []
    for index in range(1, 1001):
        for provision_id in (f"provision-{index}", f"distractor-{index}"):
            sources.append(
                SourceProvision(
                    provision_id=provision_id,
                    version_id="version-1",
                    document_id="document-1",
                    document_title="전기사업법",
                    source_kind="law",
                    mst="1",
                    effective_from=date(2026, 1, 1),
                    effective_to=None,
                    source_url="https://open.law.go.kr/mock",
                    path="제1조",
                    parent_path=None,
                    heading="목적",
                    content=gold_fixture.CONTENT,
                    ordinal=index,
                )
            )
    return sources


def _full_source_bank(dataset: dict[str, object]) -> dict[str, object]:
    cases = dataset["cases"]
    assert isinstance(cases, list)
    return {
        "bank_version": dataset["source_bank"]["bank_version"],
        "question_count": 1000,
        "question_set_sha256": dataset["source_bank"]["question_set_sha256"],
        "question_scope_set_sha256": dataset["source_bank"]["question_scope_set_sha256"],
        "questions": [
            {
                "id": case["id"],
                "question": case["question"],
                "question_sha256": case["question_sha256"],
                "scenario_family_id": case["scenario_family_id"],
                "intent": case["intent"],
                "technology": case["technology"],
                "question_style": case["question_style"],
            }
            for case in cases
        ],
    }


def _full_approval_manifest(source_bank: dict[str, object]) -> dict[str, object]:
    questions = source_bank["questions"]
    assert isinstance(questions, list)
    return {
        "schema_version": 1,
        "manifest_version": "experiment-d-lay-energy-question-approval-v1",
        "status": "approved",
        "decision_scope": "question_text_and_scope_only",
        "approved_by": "test-reviewer",
        "approved_at": "2026-08-03T12:00:00+09:00",
        "source_bank": {
            "bank_version": source_bank["bank_version"],
            "question_count": source_bank["question_count"],
            "question_set_sha256": source_bank["question_set_sha256"],
            "question_scope_set_sha256": source_bank["question_scope_set_sha256"],
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


def _full_adjudication_manifest(dataset: dict[str, object]) -> dict[str, object]:
    cases = dataset["cases"]
    assert isinstance(cases, list)
    return {
        "schema_version": 1,
        "manifest_version": "experiment-d-lay-energy-gold-adjudication-v1",
        "status": "approved",
        "decision_scope": "full_gold_dataset_and_case_payloads",
        "approved_by": "gold-owner",
        "approved_at": "2026-08-03T14:00:00+09:00",
        "dataset_sha256": canonical_gold_dataset_sha256(dataset),
        "cases": [
            {
                "case_id": case["id"],
                "case_payload_sha256": canonical_gold_case_payload_sha256(case),
            }
            for case in cases
        ],
    }


def _full_ready_inputs() -> tuple[
    dict[str, object],
    list[SourceProvision],
    dict[str, object],
    dict[str, object],
    dict[str, object],
]:
    dataset = gold_fixture._dataset()
    sources = _full_contract_sources()
    source_bank = _full_source_bank(dataset)
    approval_manifest = _full_approval_manifest(source_bank)
    dataset["source_bank"]["approval_manifest_sha256"] = _approval_manifest_sha256(
        approval_manifest
    )
    dataset["corpus_snapshot"]["searchable_provision_count"] = len(sources)
    dataset["corpus_snapshot"]["fingerprint_sha256"] = corpus_fingerprint_sha256(sources)
    adjudication_manifest = _full_adjudication_manifest(dataset)
    return dataset, sources, source_bank, approval_manifest, adjudication_manifest


def _audit(dataset: dict[str, object], provisions: list[SourceProvision]):
    source_bank = _source_bank(dataset)
    approval_manifest = _approval_manifest(source_bank)
    dataset["source_bank"]["approval_manifest_sha256"] = _approval_manifest_sha256(
        approval_manifest
    )
    return audit_gold_dataset(
        dataset,
        provisions,
        source_bank,
        approval_manifest,
    )


def test_matching_one_case_fixture_has_no_binding_or_corpus_errors() -> None:
    source = _source()

    report = _audit(_approved_dataset(source), [source])

    assert report.ready is False
    assert report.source_bank_binding_valid is True
    assert "qrel_source_missing" not in report.reasons
    assert "qrel_source_changed" not in report.reasons
    assert "corpus_fingerprint_mismatch" not in report.reasons
    assert "gold_contract_invalid" in report.reasons
    assert "approval_manifest_contract_invalid" in report.reasons
    assert report.qrel_count == 1
    assert report.unique_qrel_count == 1


def test_full_valid_gold_contract_is_ready_against_matching_corpus() -> None:
    dataset, sources, source_bank, approval_manifest, adjudication_manifest = _full_ready_inputs()

    report = audit_gold_dataset(
        dataset,
        sources,
        source_bank,
        approval_manifest,
        adjudication_manifest,
    )

    assert report.ready is True
    assert report.reasons == ()
    assert report.case_count == 1000
    assert report.missing_judged_candidate_count == 0
    assert report.adjudication_manifest_valid is True


def test_flat_body_qrel_and_judged_candidate_are_searchable_ready_path() -> None:
    dataset = gold_fixture._dataset()
    qrel_source = SourceProvision(
        provision_id="provision-1",
        version_id="version-1",
        document_id="document-1",
        document_title="전기사업법",
        source_kind="law",
        mst="1",
        effective_from=date(2026, 1, 1),
        effective_to=None,
        source_url="https://open.law.go.kr/mock",
        path="본문/단락1",
        parent_path="본문",
        heading=None,
        content="이 단락은 전기사업에 관한 기본 사항을 정한다.",
        ordinal=1,
    )
    judged_only_source = SourceProvision(
        provision_id="distractor-1",
        version_id="version-1",
        document_id="document-1",
        document_title="전기사업법",
        source_kind="law",
        mst="1",
        effective_from=date(2026, 1, 1),
        effective_to=None,
        source_url="https://open.law.go.kr/mock",
        path="본문/단락2",
        parent_path="본문",
        heading=None,
        content="이 단락은 별도의 일반 본문을 담는다.",
        ordinal=2,
    )
    first_case = dataset["cases"][0]
    qrel = first_case["qrels"][0]
    qrel.update(
        {
            "path": qrel_source.path,
            "heading": qrel_source.heading,
            "content_sha256": qrel_source.content_sha256,
            "passage_text_sha256": embedding_text_sha256(
                legal_provision_embedding_text(
                    document_title=qrel_source.document_title,
                    path=qrel_source.path,
                    heading=qrel_source.heading,
                    content=qrel_source.content,
                )
            ),
        }
    )
    reference_context = first_case["reference_contexts"][0]
    reference_context.update(
        {
            "content": qrel_source.content,
            "content_sha256": qrel_source.content_sha256,
        }
    )

    sources = [
        qrel_source
        if source.provision_id == qrel_source.provision_id
        else judged_only_source
        if source.provision_id == judged_only_source.provision_id
        else source
        for source in _full_contract_sources()
    ]
    source_bank = _full_source_bank(dataset)
    approval_manifest = _full_approval_manifest(source_bank)
    dataset["source_bank"]["approval_manifest_sha256"] = _approval_manifest_sha256(
        approval_manifest
    )
    dataset["corpus_snapshot"]["searchable_provision_count"] = len(sources)
    dataset["corpus_snapshot"]["fingerprint_sha256"] = corpus_fingerprint_sha256(sources)
    adjudication_manifest = _full_adjudication_manifest(dataset)

    report = audit_gold_dataset(
        dataset,
        sources,
        source_bank,
        approval_manifest,
        adjudication_manifest,
    )

    assert report.ready is True
    assert report.reasons == ()
    assert report.missing_qrel_count == 0
    assert report.missing_judged_candidate_count == 0


def test_structure_marker_returned_as_distractor_is_present_in_searchable_pool() -> None:
    source = _source()
    structure = SourceProvision(
        provision_id="structure-marker-1",
        version_id="version-1",
        document_id="document-1",
        document_title="전기사업법",
        source_kind="law",
        mst="1",
        effective_from=date(2026, 1, 1),
        effective_to=None,
        source_url="https://open.law.go.kr/mock",
        path="제1장",
        parent_path=None,
        heading="총칙",
        content="제1장 총칙",
        ordinal=2,
    )
    dataset = _approved_dataset(source)
    candidate_ids = [source.provision_id, structure.provision_id]
    dataset["cases"][0]["judgment_coverage"] = {
        "candidate_count": 2,
        "judged_count": 2,
        "judged_candidate_provision_ids": candidate_ids,
        "judged_candidate_set_sha256": hashlib.sha256(
            json.dumps(
                sorted(candidate_ids),
                ensure_ascii=False,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest(),
        "all_candidates_judged": True,
        "alternative_positive_search_completed": True,
        "completeness_status": "adjudicated",
        "distractor_provision_ids": [structure.provision_id],
    }
    sources = [source, structure]
    dataset["corpus_snapshot"]["searchable_provision_count"] = len(sources)
    dataset["corpus_snapshot"]["fingerprint_sha256"] = corpus_fingerprint_sha256(sources)

    report = _audit(dataset, sources)

    assert report.missing_judged_candidate_count == 0
    assert "judged_candidate_source_missing" not in report.reasons


def test_draft_is_not_ready_even_when_qrels_match() -> None:
    source = _source()
    dataset = _approved_dataset(source)
    dataset["evaluation_status"] = "draft_for_review"

    report = _audit(dataset, [source])

    assert report.ready is False
    assert "dataset_not_approved_gold" in report.reasons


def test_question_change_after_approval_is_detected() -> None:
    source = _source()
    dataset = _approved_dataset(source)
    dataset["cases"][0]["question"] = "승인 후 바뀐 질문인가요?"

    report = _audit(dataset, [source])

    assert report.ready is False
    assert "question_set_hash_mismatch" in report.reasons


def test_rehashing_changed_gold_cannot_replace_the_approved_source_bank() -> None:
    source = _source()
    dataset = _approved_dataset(source)
    approved_source_bank = _source_bank(dataset)
    approved_manifest = _approval_manifest(approved_source_bank)
    dataset["source_bank"]["approval_manifest_sha256"] = _approval_manifest_sha256(
        approved_manifest
    )
    changed_question = "승인된 질문을 gold 안에서만 바꾼 경우인가요?"
    dataset["cases"][0]["question"] = changed_question
    dataset["cases"][0]["question_sha256"] = hashlib.sha256(
        changed_question.encode("utf-8")
    ).hexdigest()
    changed_set_sha = question_set_sha256(dataset["cases"])
    dataset["question_set_sha256"] = changed_set_sha
    dataset["source_bank"]["question_set_sha256"] = changed_set_sha

    report = audit_gold_dataset(
        dataset,
        [source],
        approved_source_bank,
        approved_manifest,
    )

    assert report.ready is False
    assert report.source_bank_binding_valid is False
    assert "gold_source_bank_question_text_mismatch" in report.reasons


def test_scope_change_after_approval_is_detected() -> None:
    source = _source()
    dataset = _approved_dataset(source)
    approved_source_bank = _source_bank(dataset)
    approved_manifest = _approval_manifest(approved_source_bank)
    dataset["source_bank"]["approval_manifest_sha256"] = _approval_manifest_sha256(
        approved_manifest
    )
    dataset["cases"][0]["technology"] = "changed-after-approval"
    changed_scope_hash = question_scope_set_sha256(dataset["cases"])
    assert changed_scope_hash is not None
    dataset["source_bank"]["question_scope_set_sha256"] = changed_scope_hash

    report = audit_gold_dataset(
        dataset,
        [source],
        approved_source_bank,
        approved_manifest,
    )

    assert report.ready is False
    assert report.source_bank_binding_valid is False
    assert "gold_source_bank_question_scope_mismatch" in report.reasons


def test_non_current_parser_id_fails_before_the_rest_of_gold_validation() -> None:
    old_source = _source("old-id")
    current_source = _source("parser-v3-id")

    with pytest.raises(NonCurrentParserIdError) as captured:
        _audit(_approved_dataset(old_source), [current_source])

    assert captured.value.parser_contract_version == "3"
    assert captured.value.count == 1
    assert captured.value.sample == ("old-id",)
    assert str(captured.value).startswith("non_current_parser_provision_ids:")


def test_same_id_with_changed_text_marks_qrel_stale() -> None:
    old_source = _source(content="제1조(목적) 이전 본문이다.")
    current_source = _source(content="제1조(목적) 현재 본문이다.")

    report = _audit(_approved_dataset(old_source), [current_source])

    assert report.ready is False
    assert report.changed_qrel_count == 1
    assert "qrel_source_changed" in report.reasons


def test_unanswerable_case_cannot_carry_positive_qrels() -> None:
    source = _source()
    dataset = copy.deepcopy(_approved_dataset(source))
    dataset["cases"][0]["answerability"] = "unanswerable"

    report = _audit(dataset, [source])

    assert report.ready is False
    assert "unanswerable_case_has_qrels" in report.reasons


def test_gold_adjudication_manifest_is_required_for_ready_status() -> None:
    dataset, sources, source_bank, approval_manifest, _ = _full_ready_inputs()

    report = audit_gold_dataset(dataset, sources, source_bank, approval_manifest)

    assert report.ready is False
    assert "adjudication_manifest_missing" in report.reasons
    assert report.adjudication_manifest_valid is False


def test_post_adjudication_case_change_breaks_dataset_and_case_seals() -> None:
    dataset, sources, source_bank, approval_manifest, adjudication_manifest = _full_ready_inputs()
    dataset["cases"][0]["reference_response"]["text"] = "changed after adjudication"

    report = audit_gold_dataset(
        dataset,
        sources,
        source_bank,
        approval_manifest,
        adjudication_manifest,
    )

    assert report.ready is False
    assert "adjudication_dataset_hash_mismatch" in report.reasons
    assert "adjudication_case_payload_hash_mismatch" in report.reasons
    assert report.adjudication_manifest_error_count == 2


def test_case_review_must_be_strictly_after_question_approval() -> None:
    dataset, sources, source_bank, approval_manifest, _ = _full_ready_inputs()
    dataset["cases"][0]["annotation_review"]["reviewed_at"] = approval_manifest["approved_at"]
    adjudication_manifest = _full_adjudication_manifest(dataset)

    report = audit_gold_dataset(
        dataset,
        sources,
        source_bank,
        approval_manifest,
        adjudication_manifest,
    )

    assert report.ready is False
    assert "case_review_not_after_question_approval" in report.reasons


def test_gold_adjudication_must_be_strictly_after_every_case_review() -> None:
    dataset, sources, source_bank, approval_manifest, adjudication_manifest = _full_ready_inputs()
    adjudication_manifest["approved_at"] = dataset["cases"][0]["annotation_review"]["reviewed_at"]

    report = audit_gold_dataset(
        dataset,
        sources,
        source_bank,
        approval_manifest,
        adjudication_manifest,
    )

    assert report.ready is False
    assert "gold_adjudication_not_after_case_review" in report.reasons


def test_distractor_and_pool_candidates_must_be_effective_at_case_as_of() -> None:
    dataset, sources, source_bank, approval_manifest, _ = _full_ready_inputs()
    sources = [
        replace(source, effective_from=date(2026, 9, 1))
        if source.provision_id == "distractor-1"
        else source
        for source in sources
    ]
    dataset["corpus_snapshot"]["fingerprint_sha256"] = corpus_fingerprint_sha256(sources)
    adjudication_manifest = _full_adjudication_manifest(dataset)

    report = audit_gold_dataset(
        dataset,
        sources,
        source_bank,
        approval_manifest,
        adjudication_manifest,
    )

    assert report.ready is False
    assert "distractor_not_effective_as_of" in report.reasons
    assert "pool_candidate_not_effective_as_of" in report.reasons
    assert report.distractor_not_effective_as_of_count == 1
    assert report.pool_candidate_not_effective_as_of_count == 1


def test_full_corpus_manual_review_must_equal_case_as_of_population() -> None:
    dataset, sources, source_bank, approval_manifest, _ = _full_ready_inputs()
    dataset["annotation_protocol"]["pool_methods"] = [
        {
            "method_id": "full-corpus-review-v1",
            "kind": "full_corpus_manual_review",
            "configuration_sha256": gold_fixture.CONFIG_SHA,
            "top_k": None,
        }
    ]
    for case in dataset["cases"]:
        candidate_ids = case["judgment_coverage"]["judged_candidate_provision_ids"]
        case["judgment_coverage"]["pool_method_candidates"] = [
            {
                "method_id": "full-corpus-review-v1",
                "top_k": None,
                "candidate_provision_ids": candidate_ids,
                "candidate_set_sha256": gold_fixture._json_sha256(sorted(candidate_ids)),
            }
        ]
    adjudication_manifest = _full_adjudication_manifest(dataset)

    report = audit_gold_dataset(
        dataset,
        sources,
        source_bank,
        approval_manifest,
        adjudication_manifest,
    )

    assert report.ready is False
    assert "full_corpus_pool_mismatch" in report.reasons
    assert report.full_corpus_pool_mismatch_count == 1000
