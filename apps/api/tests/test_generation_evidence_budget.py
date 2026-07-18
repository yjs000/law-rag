from datetime import date
from uuid import uuid4

from app.adapters.openai_answerer import select_generation_hits
from app.domain.schemas import SearchHit


def _hit(content: str) -> SearchHit:
    return SearchHit(
        provision_id=uuid4(), document_id=uuid4(), document_title="전기사업법", source_kind="law",
        version_label="시행 2026-01-01", path="제1조", heading="목적", content=content,
        effective_from=date(2026, 1, 1), effective_to=None,
        source_url="https://www.law.go.kr/법령/전기사업법", score=1.0,
    )


def test_budget_keeps_whole_ranked_provisions() -> None:
    first, second = _hit("가" * 100), _hit("나" * 100)
    budget = len(first.document_title) + len(first.path) + len(first.version_label) + 150

    selected = select_generation_hits([first, second], budget)

    assert selected == [first]
    assert selected[0].content == first.content


def test_budget_keeps_one_oversized_top_provision() -> None:
    first = _hit("가" * 100)

    assert select_generation_hits([first], 1) == [first]
