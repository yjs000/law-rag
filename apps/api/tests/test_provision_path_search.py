import json
from datetime import date
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import app.main as main_module
from app.adapters.memory_repository import MemoryLegalRepository
from app.domain.catalog import SourceKind
from app.domain.provision_queries import parse_provision_reference
from app.parsers.law_json import parse_legal_document


def _document(title: str, source_id: str, effective_date: str = "20200101"):
    body = json.dumps(
        {
            "법령": {
                "기본정보": {
                    "법령ID": source_id,
                    "법령일련번호": f"mst-{source_id}",
                    "법령명_한글": title,
                    "시행일자": effective_date,
                },
                "조문": {
                    "조문단위": [
                        {
                            "조문번호": "1",
                            "조문내용": "제1조(목적)",
                            "항": [
                                {"항번호": "①", "항내용": "첫째 항"},
                                {"항번호": "②", "항내용": "둘째 항"},
                            ],
                        }
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
        source_url="https://open.law.go.kr/법령",
    )


def test_provision_reference_normalizes_article_branch_paragraph_item_and_subitem() -> None:
    reference = parse_provision_reference("제12조의3 제2항 제4호 가목을 보여줘")

    assert reference is not None
    assert reference.path == "제12조의3/항2/호4/목가"
    assert "제12조의3/항②/호4./목가." in reference.storage_paths


def test_postgres_path_query_types_nullable_title_parameter_explicitly() -> None:
    source = (Path(__file__).parents[1] / "app/adapters/postgres_repository.py").read_text(
        encoding="utf-8"
    )

    assert "CAST(:title AS text) IS NULL" in source
    assert "d.exact_title=CAST(:title AS text)" in source


@pytest.mark.asyncio
async def test_path_only_query_returns_same_provision_from_each_matching_law() -> None:
    repository = MemoryLegalRepository()
    await repository.upsert_document(_document("전기사업법", "1"))
    await repository.upsert_document(_document("전기안전관리법", "2"))

    hits = await repository.search("1조2항은?", date(2026, 7, 15), 10)

    assert [(hit.document_title, hit.path) for hit in hits] == [
        ("전기사업법", "제1조/항②"),
        ("전기안전관리법", "제1조/항②"),
    ]


@pytest.mark.asyncio
async def test_explicit_law_title_limits_ambiguous_path_query() -> None:
    repository = MemoryLegalRepository()
    await repository.upsert_document(_document("전기사업법", "1"))
    await repository.upsert_document(_document("전기안전관리법", "2"))

    hits = await repository.search("전기사업법 1조2항", date(2026, 7, 15), 10)

    assert [hit.document_title for hit in hits] == ["전기사업법"]


@pytest.mark.asyncio
async def test_common_law_abbreviation_limits_path_query_to_formal_title() -> None:
    repository = MemoryLegalRepository()
    formal_title = "신에너지 및 재생에너지 개발ㆍ이용ㆍ보급 촉진법"
    await repository.upsert_document(_document(formal_title, "1"))
    await repository.upsert_document(_document("전기사업법", "2"))

    hits = await repository.search("신재생에너지법 제1조", date(2026, 7, 15), 10)

    assert [hit.document_title for hit in hits] == [formal_title]


@pytest.mark.asyncio
async def test_path_query_excludes_version_before_its_effective_date() -> None:
    repository = MemoryLegalRepository()
    await repository.upsert_document(_document("전기사업법", "1", "20270101"))

    assert await repository.search("1조2항", date(2026, 12, 31), 10) == []


def test_question_api_explains_when_requested_path_does_not_exist(monkeypatch) -> None:
    repository = MemoryLegalRepository()
    monkeypatch.setattr(main_module, "repository", repository)

    response = TestClient(main_module.app).post(
        "/v1/questions",
        json={
            "question": "999조2항은?",
            "as_of_date": "2026-07-15",
            "project_stage": "planning",
            "answer_mode": "search_only",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["result_status"] == "no_results"
    assert payload["no_results_reason"] == "requested_path_not_found"
    assert "검색 결과가 없습니다" in payload["summary"]
    assert any("제999조/항2" in limitation for limitation in payload["limitations"])
