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
    DIMENSIONS,
    SOURCE_SPECS,
    LoadedSource,
    SourceSpec,
    _exact_record,
    build_corpus,
    load_corpus,
    run_cli,
    save_corpus,
    search_corpus,
)


class FixedEmbedder:
    def __init__(self, vectors: list[list[float]]) -> None:
        self.vectors = vectors
        self.inputs: list[str] | None = None

    async def embed(self, texts: list[str]) -> list[list[float]]:
        self.inputs = texts
        return self.vectors


def _basis(index: int) -> list[float]:
    vector = [0.0] * DIMENSIONS
    vector[index] = 1.0
    return vector


def _source(spec: SourceSpec, index: int) -> LoadedSource:
    mst = spec.mst or f"current-{index}"
    provisions = [
        ProvisionRecord(
            id=uuid5(NAMESPACE_URL, f"{mst}:{path}"),
            path=path,
            heading=f"표제 {path}",
            content=f"{spec.title} {path} 실제 조문",
            ordinal=ordinal,
        )
        for ordinal, path in enumerate(spec.selected_paths)
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


@pytest.mark.asyncio
async def test_builds_exactly_ten_parser_chunks_with_passage_embeddings(tmp_path: Path) -> None:
    sources = [_source(spec, index) for index, spec in enumerate(SOURCE_SPECS)]
    embedder = FixedEmbedder([_basis(index) for index in range(10)])

    corpus = await build_corpus(
        sources,
        embedder=embedder,
        generated_at="2026-07-23T07:00:00Z",
    )
    path = tmp_path / "corpus.json"
    save_corpus(path, corpus)
    loaded = load_corpus(path)

    assert loaded["source_count"] == 3
    assert loaded["chunk_count"] == 10
    assert [chunk["path"] for chunk in loaded["chunks"]] == [
        path for spec in SOURCE_SPECS for path in spec.selected_paths
    ]
    assert all(len(chunk["embedding"]) == 512 for chunk in loaded["chunks"])
    assert all("redacted" in chunk["source_url"] for chunk in loaded["chunks"])
    assert embedder.inputs is not None
    assert embedder.inputs[0].startswith("저작권법\n제2조/호1.")
    assert "실제 조문" in embedder.inputs[0]


@pytest.mark.asyncio
async def test_search_returns_cosine_top_three_in_score_order() -> None:
    sources = [_source(spec, index) for index, spec in enumerate(SOURCE_SPECS)]
    corpus = await build_corpus(
        sources,
        embedder=FixedEmbedder([_basis(index) for index in range(10)]),
    )
    query = [0.8, 0.48, 0.36, *([0.0] * 509)]

    result = await search_corpus(
        "무엇이 필요한가?",
        corpus,
        embedder=FixedEmbedder([query]),
    )

    assert result["corpus_chunks"] == 10
    assert result["top_k"] == 3
    assert [item["rank"] for item in result["results"]] == [1, 2, 3]
    assert [item["path"] for item in result["results"]] == [
        "제2조/호1.",
        "제2조/호2.",
        "제4조/항①/호1.",
    ]
    assert [item["score"] for item in result["results"]] == pytest.approx([0.8, 0.48, 0.36])


@pytest.mark.asyncio
async def test_missing_selected_path_stops_before_embedding() -> None:
    sources = [_source(spec, index) for index, spec in enumerate(SOURCE_SPECS)]
    sources[0].document.provisions.pop()
    embedder = FixedEmbedder([_basis(index) for index in range(10)])

    with pytest.raises(ValueError, match="선택 조문"):
        await build_corpus(sources, embedder=embedder)

    assert embedder.inputs is None


def test_load_rejects_missing_or_embedding_contract_mismatch(tmp_path: Path) -> None:
    path = tmp_path / "corpus.json"
    with pytest.raises(FileNotFoundError, match="run prepare first"):
        load_corpus(path)

    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "experiment": "C",
                "chunk_count": 10,
                "embedding": {
                    "model": "other/model",
                    "dimensions": 512,
                    "embedding_version": "1",
                },
                "chunks": [{} for _ in range(10)],
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="embedding contract mismatch"):
        load_corpus(path)


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

    assert embedder.inputs is None


def test_ask_cli_prompts_for_question(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    async def fake_ask(path: Path, question: str) -> dict[str, object]:
        assert path == tmp_path / "corpus.json"
        assert question == "저작물이란?"
        return {"experiment": "C", "results": []}

    monkeypatch.setattr("builtins.input", lambda _prompt: "저작물이란?")
    monkeypatch.setattr(search_module, "_ask", fake_ask)

    assert run_cli(["ask", "--corpus", str(tmp_path / "corpus.json")]) == 0
    assert json.loads(capsys.readouterr().out)["experiment"] == "C"


def test_cli_reports_missing_corpus_without_provider_detail(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    async def missing(_path: Path, _question: str) -> dict[str, object]:
        raise FileNotFoundError("private provider detail")

    monkeypatch.setattr(search_module, "_ask", missing)

    assert run_cli(["ask", "--question", "질문"]) == 2
    error = json.loads(capsys.readouterr().err)
    assert error == {
        "status": "error",
        "code": "corpus_missing",
        "message": "실험 C를 실행하지 못했습니다",
    }
