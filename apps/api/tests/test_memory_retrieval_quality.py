import json
from datetime import date

import pytest

from app.adapters.memory_repository import MemoryLegalRepository
from app.domain.catalog import SourceKind
from app.parsers.law_json import parse_legal_document


def _document(title: str, source_id: str, articles: list[tuple[str, str]]):
    body = json.dumps(
        {
            "법령": {
                "기본정보": {
                    "법령ID": source_id,
                    "법령일련번호": f"mst-{source_id}",
                    "법령명_한글": title,
                    "시행일자": "20200101",
                },
                "조문": {
                    "조문단위": [
                        {"조문번호": number, "조문내용": content}
                        for number, content in articles
                    ]
                },
            }
        },
        ensure_ascii=False,
    )
    return parse_legal_document(
        body,
        expected_title=title,
        source_kind=SourceKind.LAW,
        source_url="https://open.law.go.kr/mock",
    )


@pytest.mark.asyncio
async def test_korean_particles_and_question_fillers_do_not_hide_relevant_provision() -> None:
    repository = MemoryLegalRepository()
    await repository.upsert_document(
        _document(
            "전기사업법",
            "electricity-business",
            [
                ("1", "제1조(목적) 이 법은 전기사업의 기본 사항을 정한다."),
                ("7", "제7조(사업의 허가) 전기사업을 하려는 자는 허가를 받아야 한다."),
            ],
        )
    )

    hits = await repository.search(
        "전기사업 허가가 필요한가요? 알려주세요.", date(2026, 7, 15), 10
    )

    assert hits
    assert hits[0].path == "제7조"
    assert "허가" in hits[0].content


@pytest.mark.asyncio
async def test_title_heading_and_content_matches_rank_more_specific_evidence_first() -> None:
    repository = MemoryLegalRepository()
    await repository.upsert_document(
        _document(
            "전기사업법 시행규칙",
            "rule",
            [
                ("1", "제1조(목적) 전기사업 허가 절차에 필요한 사항을 정한다."),
                ("4", "제4조(허가의 신청) 허가 신청서와 사업계획서를 제출하여야 한다."),
            ],
        )
    )

    hits = await repository.search(
        "전기사업법 시행규칙에서 허가 신청 서류는 무엇인가요?",
        date(2026, 7, 15),
        10,
    )

    assert [hit.path for hit in hits[:2]] == ["제4조", "제1조"]
    assert hits[0].score > hits[1].score


@pytest.mark.asyncio
async def test_only_question_fillers_return_an_explicit_empty_result() -> None:
    repository = MemoryLegalRepository()
    await repository.upsert_document(
        _document("전기사업법", "empty", [("1", "제1조(목적) 전기사업에 관한 법률")])
    )

    assert await repository.search("무엇인지 알려주세요?", date(2026, 7, 15), 10) == []
