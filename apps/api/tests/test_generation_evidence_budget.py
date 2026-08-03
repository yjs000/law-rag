from datetime import date
from uuid import uuid4

from app.adapters.openai_answerer import select_generation_hits
from app.domain.schemas import SearchHit


def _hit(
    content: str,
    *,
    document_id=None,
    path: str = "제1조",
) -> SearchHit:
    return SearchHit(
        provision_id=uuid4(),
        document_id=document_id or uuid4(),
        document_title="전기사업법",
        source_kind="law",
        version_label="시행 2026-01-01",
        path=path,
        heading="목적",
        content=content,
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


def test_generation_context_keeps_only_highest_ranked_leaf_per_article() -> None:
    document_id = uuid4()
    top = _hit("직접 근거", document_id=document_id, path="제7조/항①")
    duplicate = _hit("같은 조의 다른 항", document_id=document_id, path="제7조/항②")
    other = _hit("다른 조", document_id=document_id, path="제8조")

    selected = select_generation_hits([top, duplicate, other], 10_000)

    assert selected == [top, other]


def test_generation_context_is_limited_to_five_articles() -> None:
    document_id = uuid4()
    hits = [
        _hit(f"제{index}조 본문", document_id=document_id, path=f"제{index}조")
        for index in range(1, 8)
    ]

    selected = select_generation_hits(hits, 100_000)

    assert selected == hits[:5]


def test_flat_body_paths_are_not_collapsed_into_one_article() -> None:
    document_id = uuid4()
    first = _hit("첫 문단", document_id=document_id, path="본문/문단1")
    second = _hit("둘째 문단", document_id=document_id, path="본문/문단2")

    assert select_generation_hits([first, second], 10_000) == [first, second]
