from datetime import date
from uuid import uuid4

import pytest

from app.application.answering import search_only_answer
from app.domain.catalog import SourceKind
from app.domain.schemas import ProjectStage, QuestionRequest, SearchHit
from scripts.evaluate_retrieval import citation_quality, enforce_quality


def _answer_and_hit():
    hit = SearchHit(
        provision_id=uuid4(),
        document_id=uuid4(),
        document_title="전기사업법",
        source_kind=SourceKind.LAW,
        version_label="MST 1",
        effective_from=date(2026, 1, 1),
        effective_to=None,
        path="제7조",
        content="허가를 받아야 한다.",
        source_url="https://www.law.go.kr/법령/전기사업법",
        score=1,
    )
    request = QuestionRequest(
        question="허가가 필요한가요?",
        as_of_date=date(2026, 7, 14),
        project_stage=ProjectStage.PLANNING,
    )
    return search_only_answer(request, [hit]), hit


def test_evaluator_measures_existing_and_exact_original_citations() -> None:
    answer, hit = _answer_and_hit()
    assert citation_quality(answer, [hit]) == (1.0, 1.0)
    enforce_quality(0.9, 1.0, 1.0)


@pytest.mark.parametrize("metrics", [(0.89, 1.0, 1.0), (1.0, 0.99, 1.0), (1.0, 1.0, 0.99)])
def test_evaluator_exits_nonzero_on_any_quality_regression(metrics) -> None:
    with pytest.raises(SystemExit):
        enforce_quality(*metrics)


def test_changed_quote_is_not_an_exact_original_match() -> None:
    answer, hit = _answer_and_hit()
    answer.citations[0].quote = "모델이 바꾼 원문"
    assert citation_quality(answer, [hit]) == (1.0, 0.0)
