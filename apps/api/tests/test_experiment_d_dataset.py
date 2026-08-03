import difflib
import json
import re
from datetime import date
from pathlib import Path

from scripts.generate_experiment_d_dataset import (
    SourceProvision,
    _actor,
    _positive_case,
    _unique_semantic_candidates,
    build_dataset,
)
from scripts.render_experiment_d_question_review import render_review

DATASET = Path(__file__).parents[1] / "evaluation" / "experiment-d-v3-1000.json"


def _source(
    provision_id: str,
    path: str,
    content: str,
    *,
    heading: str | None = None,
    parent_path: str | None = None,
    ordinal: int = 0,
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
        path=path,
        parent_path=parent_path,
        heading=heading,
        content=content,
        ordinal=ordinal,
    )


def test_small_dataset_builds_all_control_and_boundary_categories() -> None:
    sources = [
        _source(
            "root-1",
            "제1조",
            "제1조(사업의 허가) 전기사업의 허가에 필요한 사항을 정한다.",
            heading="사업의 허가",
        ),
        _source(
            "child-1",
            "제1조/항①",
            "① 전기사업자는 장관의 허가를 받아야 한다.",
            parent_path="제1조",
            ordinal=1,
        ),
        _source(
            "child-2",
            "제1조/항②",
            "② 장관은 필요한 조건을 붙일 수 있다.",
            parent_path="제1조",
            ordinal=2,
        ),
        _source(
            "root-2",
            "제2조",
            "제2조(변경허가) 전기사업의 변경허가에 필요한 사항을 정한다.",
            heading="변경허가",
            ordinal=3,
        ),
        _source(
            "child-3",
            "제2조/항①",
            "① 전기사업자는 장관의 변경허가를 받아야 한다.",
            parent_path="제2조",
            ordinal=4,
        ),
    ]
    quotas = {
        "exact_path_control": 1,
        "heading_lexical_control": 1,
        "semantic_paraphrase": 1,
        "hierarchy_child": 1,
        "hard_contrast": 1,
        "temporal_before_effective": 1,
        "outside_corpus": 1,
    }

    dataset = build_dataset(sources, quotas)

    assert dataset["counts"]["total"] == 7
    assert set(dataset["counts"]["categories"]) == set(quotas)
    assert sum(not case["answerable"] for case in dataset["cases"]) == 2


def test_subtree_evidence_includes_enumerated_children() -> None:
    parent = _source(
        "parent",
        "제3조/항①",
        "① 다음 각 호의 사업을 실시할 수 있다.",
        parent_path="제3조",
    )
    child = _source(
        "number",
        "제3조/항①/호1.",
        "1. 기술개발 지원 사업",
        parent_path="제3조/항①",
        ordinal=1,
    )
    by_article = {("document-1", "version-1", "제3조"): [parent, child]}

    case = _positive_case(
        case_id="case-1",
        category="semantic_paraphrase",
        question="어떤 사업을 할 수 있나요?",
        item=parent,
        by_article=by_article,
        index=0,
        template="permitted_action",
        evidence_scope="subtree",
    )

    assert [qrel["provision_id"] for qrel in case["qrels"]] == ["parent", "number"]
    assert case["qrels"][0]["relevance"] == 2
    assert case["qrels"][1]["relevance"] == 1
    assert "기술개발 지원 사업" in case["reference"]
    assert len(case["reference_contexts"]) == 2


def test_semantic_candidates_require_one_fixed_evidence_contract() -> None:
    first = _source("first", "제1조/항①", "① 허가를 받아야 한다.")
    second = _source("second", "제1조/항②", "② 변경허가를 받아야 한다.")
    unique = _source("unique", "제2조/항①", "① 신고하여야 한다.")
    specs = {
        "first": ("동일한 질문", "approval_requirement"),
        "second": ("동일한 질문", "approval_requirement"),
        "unique": ("고유한 질문", "reporting_duty"),
    }

    selected = _unique_semantic_candidates([first, second, unique], specs)

    assert selected == [unique]


def test_actor_uses_role_noun_instead_of_korean_verb_ending() -> None:
    received = _source(
        "received",
        "제1조/항①",
        "① 제2항에 따라 과징금을 받은 수납기관은 영수증을 발급하여야 한다.",
    )
    conditional = _source(
        "conditional",
        "제1조/항②",
        "② 설비를 이용하는 발전사업자는 허가를 받아야 한다.",
    )
    universal = _source(
        "universal",
        "제1조/항③",
        "③ 누구든지 보호구역에서 손상행위를 하여서는 아니 된다.",
    )

    assert _actor(received) == "수납기관"
    assert _actor(conditional) == "발전사업자"
    assert _actor(universal) == "누구든지"


def test_committed_experiment_d_dataset_has_balanced_fixed_contract() -> None:
    dataset = json.loads(DATASET.read_text(encoding="utf-8"))
    cases = dataset["cases"]

    assert dataset["schema_version"] == 2
    assert dataset["dataset_version"] == "experiment-d-1000-v3-draft"
    assert len(cases) == 1000
    assert dataset["counts"]["splits"] == {"calibration": 200, "test": 800}
    assert dataset["counts"]["categories"] == {
        "exact_path_control": 200,
        "hard_contrast": 100,
        "heading_lexical_control": 200,
        "hierarchy_child": 150,
        "outside_corpus": 75,
        "semantic_paraphrase": 200,
        "temporal_before_effective": 75,
    }
    assert len({case["id"] for case in cases}) == 1000
    assert len({case["user_input"] for case in cases}) == 1000
    assert sum(case["answerable"] for case in cases) == 850
    assert sum(case["review"]["status"] == "needs_human_review" for case in cases) == 10
    assert dataset["corpus"]["eligible_provision_count"] == 2502
    assert dataset["corpus"]["evidence_provision_count"] == 2833
    assert dataset["corpus"]["ambiguous_semantic_candidate_count"] == 212
    assert sum(
        case["generation"]["template_id"] == "document_outside_corpus"
        for case in cases
    ) == 60
    assert sum(
        case["generation"]["template_id"] == "nonexistent_article" for case in cases
    ) == 15
    for case in cases:
        if case["answerable"]:
            assert case["primary_evidence"] is not None
            assert case["qrels"]
            assert case["generation"]["evidence_scope"] in {"article", "leaf", "subtree"}
            primary_id = case["primary_evidence"]["provision_id"]
            assert any(
                qrel["provision_id"] == primary_id and qrel["relevance"] == 2
                for qrel in case["qrels"]
            )
        else:
            assert case["primary_evidence"] is None
            assert case["qrels"] == []
        assert not re.match(r"^제\d+(?:의\d+)?(?:장|절)", case["reference"])
        assert not re.match(
            r"^\s*(?:제\s*\d+\s*조(?:의\s*\d+)?(?:\([^)]*\))?|"
            r"[①-⑳]|\d+(?:의\d+)?\.|[가-힣]\.)?\s*삭제(?:\s|<|$)",
            case["reference"],
        )
        if case["category"] == "semantic_paraphrase":
            similarity = difflib.SequenceMatcher(
                None, case["user_input"], case["reference"]
            ).ratio()
            assert similarity < 0.8
        if case["category"] == "hard_contrast":
            assert case["generation"]["distractor_similarity"] >= 0.3
            assert case["distractor_provision_ids"]
            assert not set(case["distractor_provision_ids"]).intersection(
                qrel["provision_id"] for qrel in case["qrels"]
            )
        if (
            case["answerable"]
            and case["generation"]["evidence_scope"] == "subtree"
            and re.search(r"다음\s+각\s+(?:호|목)", case["reference"])
            and not re.search(r"(?:^|\s)(?:1\.|가\.)\s*\S", case["reference"])
        ):
            primary_path = f"{case['primary_evidence']['path']}/"
            assert any(qrel["path"].startswith(primary_path) for qrel in case["qrels"])
        assert not re.search(
            r"(?:받|하|되|있|없|필요|변경하려|전기설비)에게", case["user_input"]
        )


def test_question_review_is_explicitly_not_a_search_result() -> None:
    dataset = json.loads(DATASET.read_text(encoding="utf-8"))

    review = render_review(dataset)

    assert "1,000문항 검색 실험은 실행하지 않음" in review
    assert "검색 순위·점수·실험 결과를 포함하지 않는다" in review
    assert "structure_marker_as_answer` | 0" in review
    assert "semantic_near_copy` | 0" in review
    assert "weak_hard_contrast` | 0" in review
    assert "missing_enumerated_context` | 0" in review
