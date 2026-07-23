import json
from datetime import date
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

import pytest
from law_rag_collector.client import RawResponse, SearchRecord
from law_rag_core.domain.catalog import SourceKind
from law_rag_core.domain.entities import LegalDocumentRecord, ProvisionRecord

import scripts.experiment_search as search_module
from scripts.experiment_search import (
    DEFAULT_EVALUATION_QUESTIONS,
    DIMENSIONS,
    SOURCE_SPECS,
    LoadedSource,
    SourceSpec,
    _exact_record,
    _load_evaluation_cases,
    build_corpus,
    evaluate_cases,
    load_corpus,
    run_cli,
    save_corpus,
    save_evaluation_result,
    search_corpus,
)


class FixedEmbedder:
    def __init__(self, vectors: list[list[float]]) -> None:
        self.vectors = vectors
        self.inputs: list[list[str]] = []
        self.offset = 0

    async def embed(self, texts: list[str]) -> list[list[float]]:
        self.inputs.append(texts)
        vectors = self.vectors[self.offset : self.offset + len(texts)]
        self.offset += len(texts)
        return vectors


def _basis(index: int) -> list[float]:
    vector = [0.0] * DIMENSIONS
    vector[index] = 1.0
    return vector


def _source(
    spec: SourceSpec,
    index: int,
    records: list[tuple[str, str, str | None]],
) -> LoadedSource:
    mst = spec.mst or f"current-{index}"
    provisions = [
        ProvisionRecord(
            id=uuid5(NAMESPACE_URL, f"{mst}:{path}"),
            path=path,
            heading=f"표제 {path}",
            content=content,
            parent_path=parent_path,
            ordinal=ordinal,
        )
        for ordinal, (path, content, parent_path) in enumerate(records)
    ]
    document = LegalDocumentRecord(
        source_id=f"source-{index}",
        mst=mst,
        title=spec.title,
        source_kind=SourceKind.LAW,
        promulgation_number=None,
        promulgated_on=None,
        effective_from=spec.effective_date or date(2026, 1, index + 1),
        ministry="테스트 부처",
        source_url=f"https://www.law.go.kr/DRF/lawService.do?OC=%5Bredacted%5D&ID={index}",
        raw_format="JSON",
        raw_sha256=f"sha-{index}",
        provisions=provisions,
    )
    raw = RawResponse("{}", "JSON", document.source_url)
    return LoadedSource(spec, document, raw)


def _selected_sources() -> tuple[list[LoadedSource], list[str]]:
    records_by_source = [
        [
            ("제1조", "제1장 총칙 제1조 실제 조문", None),
            ("제1조/항①", "① 목적", "제1조"),
            ("제2조", "제2조 실제 조문", None),
            ("제4조", "제2장 저작권 제4조 실제 조문", None),
            ("제99조", "제5장 영상저작물 제99조 실제 조문", None),
            ("제99조/항①", "① 영상저작물 특례", "제99조"),
            ("제101조의2", "제5장의2 프로그램 제101조의2", None),
        ],
        [
            ("제1조", "제1장 총칙 제1조 실제 조문", None),
            ("제1조/항①", "① 목적", "제1조"),
            ("제7조", "제2장 전기사업 제7조", None),
            ("제53조", "제6장 전기위원회 제53조", None),
            ("제53조/항①", "① 전기위원회", "제53조"),
            ("제61조", "제7장 안전관리 제61조", None),
        ],
        [
            ("제1조", "제1조 실제 조문", None),
            ("제1조/항①", "① 목적", "제1조"),
            ("제2조", "제2조 실제 조문", None),
            ("제2조의2", "제2조의2 실제 조문", None),
            ("제2조의2/항①", "① 가지조문", "제2조의2"),
            ("제3조", "제3조 실제 조문", None),
            ("제4조", "제4조 실제 조문", None),
            ("제5조", "제5조 실제 조문", None),
            ("제6조", "제6조 제외", None),
        ],
    ]
    sources = [
        _source(spec, index, records_by_source[index]) for index, spec in enumerate(SOURCE_SPECS)
    ]
    expected_paths = [
        "제1조",
        "제1조/항①",
        "제2조",
        "제99조",
        "제99조/항①",
        "제1조",
        "제1조/항①",
        "제53조",
        "제53조/항①",
        "제1조",
        "제1조/항①",
        "제2조",
        "제2조의2",
        "제2조의2/항①",
        "제3조",
        "제4조",
        "제5조",
    ]
    return sources, expected_paths


@pytest.mark.asyncio
async def test_builds_only_configured_chapters_and_articles_with_all_descendants(
    tmp_path: Path,
) -> None:
    sources, expected_paths = _selected_sources()
    embedder = FixedEmbedder([_basis(index) for index in range(len(expected_paths))])

    corpus = await build_corpus(
        sources,
        embedder=embedder,
        generated_at="2026-07-23T07:00:00Z",
        embedding_batch_size=2,
    )
    path = tmp_path / "corpus.json"
    save_corpus(path, corpus)
    loaded = load_corpus(path)

    assert loaded["source_count"] == 3
    assert loaded["chunk_count"] == len(expected_paths)
    assert [chunk["path"] for chunk in loaded["chunks"]] == expected_paths
    assert loaded["selection"]["sources"][0]["chapters"] == ["제1장", "제5장"]
    assert loaded["selection"]["sources"][1]["chapters"] == ["제1장", "제6장"]
    assert loaded["selection"]["sources"][2]["article_range"] == ["제1조", "제5조"]
    assert all(len(chunk["embedding"]) == 512 for chunk in loaded["chunks"])
    assert all("redacted" in chunk["source_url"] for chunk in loaded["chunks"])
    assert [len(batch) for batch in embedder.inputs] == [2] * 8 + [1]
    assert embedder.inputs[0][0].startswith("저작권법\n제1조")
    assert "실제 조문" in embedder.inputs[0][0]

    del corpus["selection"]
    save_corpus(path, corpus)
    with pytest.raises(ValueError, match="selection contract mismatch"):
        load_corpus(path)


@pytest.mark.asyncio
async def test_search_returns_cosine_top_three_in_score_order() -> None:
    sources, expected_paths = _selected_sources()
    corpus = await build_corpus(
        sources,
        embedder=FixedEmbedder([_basis(index) for index in range(len(expected_paths))]),
    )
    query = [0.8, 0.48, 0.36, *([0.0] * 509)]

    result = await search_corpus(
        "무엇이 필요한가?",
        corpus,
        embedder=FixedEmbedder([query]),
        candidate_k=3,
    )

    assert result["corpus_chunks"] == len(expected_paths)
    assert result["candidate_k"] == 3
    assert [item["rank"] for item in result["raw_chunk_candidates"]] == [1, 2, 3]
    assert [item["path"] for item in result["raw_chunk_candidates"]] == [
        "제1조",
        "제1조/항①",
        "제2조",
    ]
    assert [item["score"] for item in result["raw_chunk_candidates"]] == pytest.approx(
        [0.8, 0.48, 0.36]
    )
    assert [item["article_path"] for item in result["article_candidates"][:2]] == [
        "제1조",
        "제2조",
    ]
    assert [item["path"] for item in result["article_candidates"][0]["matched_chunks"]] == [
        "제1조",
        "제1조/항①",
    ]


@pytest.mark.asyncio
async def test_empty_parser_result_stops_before_embedding() -> None:
    sources, _ = _selected_sources()
    sources[0].document.provisions.clear()
    embedder = FixedEmbedder([_basis(0)])

    with pytest.raises(ValueError, match="parser returned no chunks"):
        await build_corpus(sources, embedder=embedder)

    assert embedder.inputs == []


@pytest.mark.asyncio
async def test_invalid_embedding_batch_size_stops_before_embedding() -> None:
    sources, _ = _selected_sources()
    embedder = FixedEmbedder([_basis(0)])

    with pytest.raises(ValueError, match="batch size must be positive"):
        await build_corpus(sources, embedder=embedder, embedding_batch_size=0)

    assert embedder.inputs == []


@pytest.mark.asyncio
async def test_embedder_batch_size_mismatch_is_rejected() -> None:
    sources, _ = _selected_sources()
    embedder = FixedEmbedder([_basis(0)])

    with pytest.raises(ValueError, match="unexpected batch size"):
        await build_corpus(sources, embedder=embedder, embedding_batch_size=2)

    assert [len(batch) for batch in embedder.inputs] == [2]


@pytest.mark.asyncio
async def test_missing_requested_chapter_stops_before_embedding() -> None:
    sources, _ = _selected_sources()
    sources[0].document.provisions = [
        item for item in sources[0].document.provisions if item.path != "제99조"
    ]
    embedder = FixedEmbedder([_basis(0)])

    with pytest.raises(ValueError, match="missing requested chapters"):
        await build_corpus(sources, embedder=embedder)

    assert embedder.inputs == []


@pytest.mark.asyncio
async def test_missing_requested_article_stops_before_embedding() -> None:
    sources, _ = _selected_sources()
    sources[2].document.provisions = [
        item for item in sources[2].document.provisions if item.path != "제4조"
    ]
    embedder = FixedEmbedder([_basis(0)])

    with pytest.raises(ValueError, match="missing requested articles"):
        await build_corpus(sources, embedder=embedder)

    assert embedder.inputs == []


def test_load_rejects_missing_or_embedding_contract_mismatch(tmp_path: Path) -> None:
    path = tmp_path / "corpus.json"
    with pytest.raises(FileNotFoundError, match="run prepare first"):
        load_corpus(path)

    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "experiment": "C",
                "chunk_count": 1,
                "embedding": {
                    "model": "other/model",
                    "dimensions": 512,
                    "embedding_version": "1",
                },
                "chunks": [{}],
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="embedding contract mismatch"):
        load_corpus(path)


@pytest.mark.asyncio
async def test_fixed_evaluation_measures_article_recall_and_out_of_scope() -> None:
    sources, expected_paths = _selected_sources()
    corpus = await build_corpus(
        sources,
        embedder=FixedEmbedder([_basis(index) for index in range(len(expected_paths))]),
    )
    cases = [
        {
            "id": "first",
            "question": "첫 조",
            "scope": "in_scope",
            "expected_title": "저작권법",
            "expected_article_path": "제1조",
        },
        {
            "id": "second",
            "question": "둘째 조",
            "scope": "in_scope",
            "expected_title": "저작권법",
            "expected_article_path": "제2조",
        },
        {
            "id": "excluded",
            "question": "범위 밖",
            "scope": "out_of_scope",
            "expected_title": "전기사업법",
            "expected_article_path": "제7조",
        },
    ]

    result = await evaluate_cases(
        cases,
        corpus,
        embedder=FixedEmbedder([_basis(0), _basis(2), _basis(0)]),
        candidate_k=10,
        generated_at="2026-07-23T10:00:00Z",
    )

    assert result["metrics"] == {
        "in_scope_cases": 2,
        "law_at_1": 1.0,
        "article_recall_at_3": 1.0,
        "article_recall_at_5": 1.0,
        "article_recall_at_10": 1.0,
        "article_mrr": 1.0,
    }
    assert result["cases"][2]["expected_present_in_corpus"] is False
    assert result["cases"][2]["article_rank"] is None


def test_fixed_evaluation_questions_and_outputs_are_machine_readable(tmp_path: Path) -> None:
    cases = _load_evaluation_cases(DEFAULT_EVALUATION_QUESTIONS)
    assert len(cases) == 6
    assert {case["scope"] for case in cases} == {"in_scope", "out_of_scope"}

    result = {
        "generated_at": "2026-07-23T10:00:00Z",
        "corpus_sha256": "sha",
        "model": "model",
        "candidate_k": 10,
        "metrics": {
            "law_at_1": 1.0,
            "article_recall_at_3": 1.0,
            "article_recall_at_5": 1.0,
            "article_recall_at_10": 1.0,
            "article_mrr": 1.0,
        },
        "cases": [
            {
                **cases[0],
                "law_at_1": True,
                "article_rank": 1,
                "raw_chunk_rank": 1,
                "search": {
                    "article_candidates": [
                        {
                            "rank": 1,
                            "title": cases[0]["expected_title"],
                            "article_path": cases[0]["expected_article_path"],
                            "score": 0.8,
                            "best_chunk": {"path": "제2조/호2.", "content": "태양에너지"},
                        }
                    ]
                },
            }
        ],
    }
    json_path = tmp_path / "evaluation.json"
    report_path = tmp_path / "evaluation.md"

    save_evaluation_result(result, json_path=json_path, report_path=report_path)

    assert json.loads(json_path.read_text(encoding="utf-8"))["metrics"]["law_at_1"] == 1.0
    report = report_path.read_text(encoding="utf-8")
    assert "Dense 조 단위 검색 평가" in report
    assert "태양에너지" in report


def test_evaluate_cli_uses_fixed_questions_and_prints_actual_result(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    async def fake_evaluate(
        path: Path,
        questions_path: Path,
        *,
        candidate_k: int,
        json_path: Path,
        report_path: Path,
    ) -> dict[str, object]:
        assert path == tmp_path / "corpus.json"
        assert questions_path == tmp_path / "questions.json"
        assert candidate_k == 10
        assert json_path == tmp_path / "evaluation.json"
        assert report_path == tmp_path / "evaluation.md"
        return {"experiment": "C", "evaluation": "dense_article_retrieval"}

    monkeypatch.setattr(search_module, "_evaluate", fake_evaluate)

    assert (
        run_cli(
            [
                "evaluate",
                "--corpus",
                str(tmp_path / "corpus.json"),
                "--questions",
                str(tmp_path / "questions.json"),
                "--json-output",
                str(tmp_path / "evaluation.json"),
                "--report",
                str(tmp_path / "evaluation.md"),
            ]
        )
        == 0
    )
    assert json.loads(capsys.readouterr().out) == {
        "experiment": "C",
        "evaluation": "dense_article_retrieval",
    }


def test_historical_source_requires_the_requested_mst() -> None:
    spec = SOURCE_SPECS[1]
    records = [
        SearchRecord("전기사업법", "source", "current", "20260101", "/current"),
        SearchRecord("전기사업법", "source", "180380", "20160728", "/history"),
    ]
    assert _exact_record(records, spec).mst == "180380"

    with pytest.raises(ValueError, match="1건이 아닙니다"):
        _exact_record(records[:1], spec)


@pytest.mark.asyncio
async def test_search_rejects_empty_question_before_embedding() -> None:
    embedder = FixedEmbedder([_basis(0)])

    with pytest.raises(ValueError, match="question must not be empty"):
        await search_corpus(" ", {"chunks": []}, embedder=embedder)

    assert embedder.inputs == []


@pytest.mark.asyncio
@pytest.mark.parametrize("candidate_k", [0, 51])
async def test_search_rejects_candidate_k_outside_observation_boundary(
    candidate_k: int,
) -> None:
    embedder = FixedEmbedder([_basis(0)])

    with pytest.raises(ValueError, match="candidate_k must be between 1 and 50"):
        await search_corpus(
            "질문",
            {"chunks": []},
            embedder=embedder,
            candidate_k=candidate_k,
        )

    assert embedder.inputs == []


def test_ask_cli_prompts_for_question(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    async def fake_ask(path: Path, question: str, *, candidate_k: int) -> dict[str, object]:
        assert path == tmp_path / "corpus.json"
        assert question == "저작물이란?"
        assert candidate_k == 10
        return {"experiment": "C", "article_candidates": []}

    monkeypatch.setattr("builtins.input", lambda _prompt: "저작물이란?")
    monkeypatch.setattr(search_module, "_ask", fake_ask)

    assert run_cli(["ask", "--corpus", str(tmp_path / "corpus.json"), "--no-record"]) == 0
    assert json.loads(capsys.readouterr().out)["experiment"] == "C"


def test_ask_cli_records_exact_stdout_and_appends_local_history(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    corpus = tmp_path / "corpus.json"
    corpus.write_text('{"corpus":"fixture"}', encoding="utf-8")
    data = tmp_path / "runs.json"
    report = tmp_path / "results.md"

    async def fake_ask(_path: Path, question: str, *, candidate_k: int) -> dict[str, object]:
        return {
            "experiment": "C",
            "question": question,
            "candidate_k": candidate_k,
            "raw_chunk_candidates": [{"title": "신재생에너지법", "path": "제2조/호2."}],
            "article_candidates": [{"title": "신재생에너지법", "article_path": "제2조"}],
        }

    monkeypatch.setattr(search_module, "_ask", fake_ask)
    argv = [
        "ask",
        "--question",
        "태양광은 재생에너지인가?",
        "--candidate-k",
        "10",
        "--corpus",
        str(corpus),
        "--results-data",
        str(data),
        "--results-report",
        str(report),
    ]

    assert run_cli(argv) == 0
    first_stdout = capsys.readouterr().out
    assert run_cli(argv) == 0
    second_stdout = capsys.readouterr().out

    history = json.loads(data.read_text(encoding="utf-8"))
    assert [run["run"] for run in history["runs"]] == [1, 2]
    assert history["runs"][0]["stdout"] == first_stdout
    assert history["runs"][1]["stdout"] == second_stdout
    assert json.loads(first_stdout)["recording"]["run"] == 1
    assert json.loads(second_stdout)["recording"]["run"] == 2
    markdown = report.read_text(encoding="utf-8")
    assert "실행 1" in markdown
    assert "실행 2" in markdown
    assert first_stdout.rstrip("\n") in markdown
    assert second_stdout.rstrip("\n") in markdown


def test_recording_failure_returns_safe_error_without_overwriting_history(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    corpus = tmp_path / "corpus.json"
    corpus.write_text("{}", encoding="utf-8")
    data = tmp_path / "runs.json"
    report = tmp_path / "results.md"
    data.write_text("previous data", encoding="utf-8")
    report.write_text("previous report", encoding="utf-8")

    async def fake_ask(_path: Path, _question: str, *, candidate_k: int) -> dict[str, object]:
        assert candidate_k == 10
        return {"experiment": "C"}

    monkeypatch.setattr(search_module, "_ask", fake_ask)

    assert (
        run_cli(
            [
                "ask",
                "--question",
                "질문",
                "--corpus",
                str(corpus),
                "--results-data",
                str(data),
                "--results-report",
                str(report),
            ]
        )
        == 2
    )
    captured = capsys.readouterr()
    assert captured.out == ""
    assert json.loads(captured.err)["code"] == "result_recording_failed"
    assert data.read_text(encoding="utf-8") == "previous data"
    assert report.read_text(encoding="utf-8") == "previous report"


def test_cli_reports_missing_corpus_without_provider_detail(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    async def missing(_path: Path, _question: str, *, candidate_k: int) -> dict[str, object]:
        assert candidate_k == 10
        raise FileNotFoundError("private provider detail")

    monkeypatch.setattr(search_module, "_ask", missing)

    assert run_cli(["ask", "--question", "질문"]) == 2
    error = json.loads(capsys.readouterr().err)
    assert error == {
        "status": "error",
        "code": "corpus_missing",
        "message": "실험 C를 실행하지 못했습니다",
    }
