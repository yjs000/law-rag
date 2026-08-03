import json
from datetime import date
from pathlib import Path

from scripts.generate_experiment_d_dataset import SourceProvision, build_dataset

DATASET = Path(__file__).parents[1] / "evaluation" / "experiment-d-v2-1000.json"


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


def test_committed_experiment_d_dataset_has_balanced_fixed_contract() -> None:
    dataset = json.loads(DATASET.read_text(encoding="utf-8"))
    cases = dataset["cases"]

    assert dataset["schema_version"] == 2
    assert dataset["dataset_version"] == "experiment-d-1000-v2"
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
    assert sum(case["review"]["status"] == "needs_human_review" for case in cases) == 12
    for case in cases:
        if case["answerable"]:
            assert case["primary_evidence"] is not None
            assert case["qrels"]
            primary_id = case["primary_evidence"]["provision_id"]
            assert any(
                qrel["provision_id"] == primary_id and qrel["relevance"] == 2
                for qrel in case["qrels"]
            )
        else:
            assert case["primary_evidence"] is None
            assert case["qrels"] == []
