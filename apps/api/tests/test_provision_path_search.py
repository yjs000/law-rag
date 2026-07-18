import json
from datetime import date
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import app.main as main_module
from app.adapters.memory_repository import MemoryLegalRepository
from app.application.answering import search_only_answer
from app.domain.catalog import SourceKind
from app.domain.provision_queries import parse_provision_reference, parse_provision_references
from app.domain.schemas import QuestionRequest
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
                            "조문번호": str(number),
                            "조문내용": f"제{number}조(시험 {number})",
                            "항": [
                                {"항번호": "①", "항내용": "첫째 항"},
                                {"항번호": "②", "항내용": "둘째 항"},
                                {"항번호": "③", "항내용": "셋째 항"},
                            ],
                        }
                        for number in range(1, 4)
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


@pytest.mark.parametrize(
    "question",
    [
        "1조 2항",
        "제 1 조 제 2 항",
        "제1조제2항",
        "제1조 ②항",
        "제1조제②항",
        "１조 ２항",
        "제1조 제2항.",
    ],
)
def test_provision_reference_accepts_common_paragraph_number_forms(question: str) -> None:
    reference = parse_provision_reference(question)

    assert reference is not None
    assert reference.path == "제1조/항2"
    assert set(reference.storage_paths) == {"제1조/항2", "제1조/항②"}


@pytest.mark.parametrize(
    ("question", "expected"),
    [
        ("제일조 제이항", ("제1조/항2",)),
        ("제십이조 제삼항", ("제12조/항3",)),
        ("제1조 제2항 및 제3항", ("제1조/항2", "제1조/항3")),
        ("제1조부터 제3조", ("제1조", "제2조", "제3조")),
    ],
)
def test_provision_query_expands_korean_numbers_lists_and_ranges(
    question: str, expected: tuple[str, ...]
) -> None:
    parsed = parse_provision_references(question)

    assert parsed is not None
    assert tuple(reference.path for reference in parsed.references) == expected


@pytest.mark.parametrize(
    ("question", "reason"),
    [("제3조부터 제1조", "descending_range"), ("제1조부터 제21조", "range_too_wide")],
)
def test_provision_query_rejects_unsafe_ranges(question: str, reason: str) -> None:
    parsed = parse_provision_references(question)

    assert parsed is not None
    assert parsed.references == ()
    assert parsed.invalid_reason == reason


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("question", "expected_paths"),
    [
        ("제일조 제이항", ["제1조/항②"]),
        ("제1조 제2항 및 제3항", ["제1조/항②", "제1조/항③"]),
        ("제1조부터 제3조", ["제1조", "제2조", "제3조"]),
    ],
)
async def test_direct_path_search_supports_korean_numbers_lists_and_ranges(
    question: str, expected_paths: list[str]
) -> None:
    repository = MemoryLegalRepository()
    await repository.upsert_document(_document("전기사업법", "1"))

    hits = await repository.search(question, date(2026, 7, 15), 10)

    assert [hit.path for hit in hits] == expected_paths


@pytest.mark.asyncio
async def test_invalid_range_does_not_fall_back_to_lexical_search() -> None:
    repository = MemoryLegalRepository()
    await repository.upsert_document(_document("전기사업법", "1"))

    assert await repository.search("전기사업법 제3조부터 제1조", date(2026, 7, 15), 10) == []


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


@pytest.mark.asyncio
async def test_path_query_effective_range_is_start_inclusive_and_end_exclusive() -> None:
    repository = MemoryLegalRepository()
    await repository.upsert_document(_document("전기사업법", "1", "20270101"))
    key = next(iter(repository._effective_to))
    repository._effective_to[key] = date(2028, 1, 1)

    assert await repository.search("1조2항", date(2026, 12, 31), 10) == []
    assert len(await repository.search("1조2항", date(2027, 1, 1), 10)) == 1
    assert len(await repository.search("1조2항", date(2027, 12, 31), 10)) == 1
    assert await repository.search("1조2항", date(2028, 1, 1), 10) == []


@pytest.mark.asyncio
@pytest.mark.parametrize("unknown_title", ["가짜에너지법", "가짜 에너지법"])
async def test_unknown_law_like_title_does_not_fall_back_to_all_laws(
    unknown_title: str,
) -> None:
    repository = MemoryLegalRepository()
    await repository.upsert_document(_document("전기사업법", "1"))
    question = f"{unknown_title} 제1조 제2항"
    reference = parse_provision_reference(question)

    assert reference is not None
    assert reference.document_title is None
    assert reference.unrecognized_document_title == unknown_title
    assert await repository.search(question, date(2026, 7, 15), 10) == []


@pytest.mark.asyncio
async def test_missing_paragraph_does_not_return_upper_article_as_exact_evidence() -> None:
    repository = MemoryLegalRepository()
    await repository.upsert_document(_document("전기사업법", "1"))
    request = QuestionRequest(
        question="전기사업법 제1조 제99항은?",
        as_of_date=date(2026, 7, 15),
        answer_mode="search_only",
    )

    hits = await repository.search(request.question, request.as_of_date, 10)
    answer = search_only_answer(request, hits)

    assert hits == []
    assert answer.citations == []
    assert answer.no_results_reason == "requested_path_not_found"
    assert any(
        "상위 조문을 정확한 검색 결과로 대신 제시하지 않았습니다" in item
        for item in answer.limitations
    )


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
    assert any("대상 법령 전체" in limitation for limitation in payload["limitations"])


def test_question_api_names_law_when_path_is_absent_from_named_document(monkeypatch) -> None:
    repository = MemoryLegalRepository()
    monkeypatch.setattr(main_module, "repository", repository)

    response = TestClient(main_module.app).post(
        "/v1/questions",
        json={
            "question": "전기사업법 제999조 제2항은?",
            "as_of_date": "2026-07-15",
            "project_stage": "planning",
            "answer_mode": "search_only",
        },
    )

    assert response.status_code == 200
    assert any(
        "전기사업법에서 요청한 조문 경로" in limitation
        for limitation in response.json()["limitations"]
    )
    assert any(
        "상위 조문을 정확한 검색 결과로 대신 제시하지 않았습니다" in limitation
        for limitation in response.json()["limitations"]
    )


def test_question_api_explains_unrecognized_law_without_searching_all_laws(monkeypatch) -> None:
    repository = MemoryLegalRepository()
    monkeypatch.setattr(main_module, "repository", repository)

    response = TestClient(main_module.app).post(
        "/v1/questions",
        json={
            "question": "가짜에너지법 제1조 제2항은?",
            "as_of_date": "2026-07-15",
            "project_stage": "planning",
            "answer_mode": "search_only",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["result_status"] == "no_results"
    assert payload["citations"] == []
    assert any("입력한 법령명(가짜에너지법)" in item for item in payload["limitations"])
