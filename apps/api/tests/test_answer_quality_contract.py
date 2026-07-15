import json
from datetime import date
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

import pytest

from app.application.answering import search_only_answer
from app.domain.catalog import CATALOG_BY_TITLE, SourceKind
from app.domain.schemas import ProjectStage, QuestionRequest, SearchHit

CASES_PATH = Path(__file__).parent / "fixtures" / "answer_quality_cases.json"
CASES = json.loads(CASES_PATH.read_text(encoding="utf-8"))


def _hits(case: dict) -> list[SearchHit]:
    return [
        SearchHit(
            provision_id=uuid5(NAMESPACE_URL, f"{case['id']}:provision:{index}"),
            document_id=uuid5(NAMESPACE_URL, f"{case['id']}:document:{hit['document_title']}"),
            document_title=hit["document_title"],
            source_kind=SourceKind(hit["source_kind"]),
            version_label=hit["version_label"],
            effective_from=date.fromisoformat(hit["effective_from"]),
            effective_to=None,
            path=hit["path"],
            heading=hit["heading"],
            content=hit["content"],
            source_url=hit["source_url"],
            score=1.0,
        )
        for index, hit in enumerate(case["mock_hits"], 1)
    ]


def _answer_text(answer) -> str:
    parts = [answer.summary, answer.scope]
    parts.extend(section.claim for section in answer.sections)
    parts.extend(section.explanation for section in answer.sections)
    parts.extend(answer.limitations)
    return "\n".join(parts)


def _assert_terms(text: str, expected: dict) -> None:
    for term in expected["required_terms"]:
        assert term in text, f"기대 필수 용어 누락: {term}"
    for conclusion in expected["forbidden_overclaims"]:
        assert conclusion not in text, f"근거를 넘는 결론 포함: {conclusion}"


def test_dataset_covers_the_five_required_answer_scenarios() -> None:
    assert {case["category"] for case in CASES} >= {
        "허가",
        "신고/변경",
        "전기저장시설 안전",
        "직접 조문 경로",
        "범위 밖/근거 없음",
    }
    assert len(CASES) >= 5


@pytest.mark.parametrize("case", CASES, ids=lambda case: case["id"])
def test_expected_evidence_is_allowlisted_and_answer_contract_is_explicit(case: dict) -> None:
    expected = case["expected"]
    hit_titles = {hit["document_title"] for hit in case["mock_hits"]}
    hit_paths = {hit["path"] for hit in case["mock_hits"]}

    assert hit_titles == set(expected["document_titles"])
    assert hit_paths == set(expected["paths"])
    assert all(title in CATALOG_BY_TITLE for title in hit_titles)
    assert all(hit["source_url"].startswith("https://www.law.go.kr/") for hit in case["mock_hits"])
    assert expected["required_terms"]
    assert expected["forbidden_overclaims"]
    _assert_terms(expected["reference_answer"], expected)


@pytest.mark.parametrize("case", CASES, ids=lambda case: case["id"])
def test_search_only_answer_preserves_expected_evidence_and_avoids_overclaims(case: dict) -> None:
    expected = case["expected"]
    answer = search_only_answer(
        QuestionRequest(
            question=case["question"],
            as_of_date=date.fromisoformat(case["as_of_date"]),
            project_stage=ProjectStage(case["project_stage"]),
            answer_mode="search_only",
        ),
        _hits(case),
    )

    assert answer.result_status == expected["result_status"]
    assert answer.no_results_reason == expected.get("no_results_reason")
    assert {citation.document_title for citation in answer.citations} == set(
        expected["document_titles"]
    )
    assert {citation.path for citation in answer.citations} == set(expected["paths"])
    assert all(
        citation.quote == hit.content
        for citation, hit in zip(answer.citations, _hits(case), strict=True)
    )
    _assert_terms(_answer_text(answer), expected)
