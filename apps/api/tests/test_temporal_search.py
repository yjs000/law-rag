from datetime import date

import pytest

from app.adapters.memory_repository import MemoryLegalRepository
from app.domain.catalog import SourceKind
from app.parsers.law_json import parse_legal_document


@pytest.mark.asyncio
async def test_future_version_is_excluded_before_effective_date() -> None:
    body = """{
      "법령": {
        "기본정보": {
          "법령ID": "1", "법령일련번호": "2",
          "법령명_한글": "전기사업법", "시행일자": "20270101"
        },
        "조문": {"조문단위": [{"조문번호": "1", "조문내용": "에너지 사업"}]}
      }
    }"""
    document = parse_legal_document(
        body,
        expected_title="전기사업법",
        source_kind=SourceKind.LAW,
        source_url="https://example.test",
    )
    repository = MemoryLegalRepository()
    await repository.upsert_document(document)
    assert await repository.search("에너지", date(2026, 12, 31), 10) == []
    assert len(await repository.search("에너지", date(2027, 1, 1), 10)) == 1


@pytest.mark.asyncio
async def test_domain_alias_finds_formal_renewable_energy_title() -> None:
    body = """{
      "법령": {
        "기본정보": {
          "법령ID": "1", "법령일련번호": "2",
          "법령명_한글": "신에너지 및 재생에너지 개발ㆍ이용ㆍ보급 촉진법",
          "시행일자": "20200101"
        },
        "조문": {"조문단위": [{"조문번호": "1", "조문내용": "공급의무"}]}
      }
    }"""
    document = parse_legal_document(
        body,
        expected_title="신에너지 및 재생에너지 개발ㆍ이용ㆍ보급 촉진법",
        source_kind=SourceKind.LAW,
        source_url="https://example.test",
    )
    repository = MemoryLegalRepository()
    await repository.upsert_document(document)

    hits = await repository.search("신재생에너지 공급의무", date(2026, 7, 13), 10)

    assert hits
    assert hits[0].document_title == document.title
