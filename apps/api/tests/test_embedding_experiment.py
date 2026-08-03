import json
from math import isclose
from pathlib import Path

import pytest

import scripts.experiment_embeddings as experiment_module
from scripts.experiment_embeddings import record_experiment_result, run_experiment


class FakeEmbedder:
    async def embed(self, texts: list[str]) -> list[list[float]]:
        assert texts == ["문장 A", "문장 B"]
        return [
            [1.0, *([0.0] * 511)],
            [0.8, 0.6, *([0.0] * 510)],
        ]


@pytest.mark.asyncio
async def test_experiment_reports_vectors_norms_and_cosine_without_writing() -> None:
    result = await run_experiment(
        "문장 A",
        "문장 B",
        embedder=FakeEmbedder(),
        model="nvidia/nemotron-3-embed-1b",
    )

    assert result["provider"] == "nvidia_nim"
    assert result["native_dimensions"] == 2048
    assert result["output_dimensions"] == 512
    assert len(result["embedding_a"]) == 512
    assert len(result["embedding_b"]) == 512
    assert isclose(result["norm_a"], 1.0)
    assert isclose(result["norm_b"], 1.0)
    assert isclose(result["cosine_similarity"], 0.8)


@pytest.mark.asyncio
async def test_experiment_rejects_empty_sentence() -> None:
    with pytest.raises(ValueError, match="must not be empty"):
        await run_experiment(
            "",
            "문장 B",
            embedder=FakeEmbedder(),
            model="nvidia/nemotron-3-embed-1b",
        )


@pytest.mark.asyncio
async def test_result_document_preserves_exact_stdout_and_compares_repeated_runs(
    tmp_path: Path,
) -> None:
    result = await run_experiment(
        "문장 A",
        "문장 B",
        embedder=FakeEmbedder(),
        model="nvidia/nemotron-3-embed-1b",
    )
    stdout = json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    data_path = tmp_path / "runs.json"
    document_path = tmp_path / "results.md"

    record_experiment_result(
        result,
        stdout=stdout,
        data_path=data_path,
        document_path=document_path,
        recorded_at="2026-07-23T01:00:00Z",
    )
    record_experiment_result(
        result,
        stdout=stdout,
        data_path=data_path,
        document_path=document_path,
        recorded_at="2026-07-23T01:01:00Z",
    )

    history = json.loads(data_path.read_text(encoding="utf-8"))
    document = document_path.read_text(encoding="utf-8")
    assert [run["stdout"] for run in history["runs"]] == [stdout, stdout]
    assert document.count(stdout.rstrip("\n")) == 2
    assert (
        "| 2 | 2026-07-23T01:01:00Z | 0.80000000000000004 | "
        "0 | 같음 | 같음 | 0 | 0 |"
    ) in document
    assert "예상값을 실제값처럼 쓰지 않는다" in document


@pytest.mark.asyncio
async def test_result_document_reports_vector_and_cosine_differences(tmp_path: Path) -> None:
    baseline = await run_experiment(
        "문장 A",
        "문장 B",
        embedder=FakeEmbedder(),
        model="nvidia/nemotron-3-embed-1b",
    )
    changed = dict(baseline)
    changed["embedding_a"] = [0.5, *([0.0] * 511)]
    changed["cosine_similarity"] = 0.7
    data_path = tmp_path / "runs.json"
    document_path = tmp_path / "results.md"

    for result, timestamp in (
        (baseline, "2026-07-23T01:00:00Z"),
        (changed, "2026-07-23T01:01:00Z"),
    ):
        stdout = json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
        record_experiment_result(
            result,
            stdout=stdout,
            data_path=data_path,
            document_path=document_path,
            recorded_at=timestamp,
        )

    document = document_path.read_text(encoding="utf-8")
    assert "| 2 | 2026-07-23T01:01:00Z | 0.69999999999999996" in document
    assert "| 다름 | 같음 | 0.5 | 0 |" in document


def test_invalid_stdout_is_not_recorded(tmp_path: Path) -> None:
    data_path = tmp_path / "runs.json"
    document_path = tmp_path / "results.md"

    with pytest.raises(ValueError, match="invalid embedding"):
        record_experiment_result(
            {"embedding_a": [], "embedding_b": [], "cosine_similarity": 0.0},
            stdout='{"embedding_a":[],"embedding_b":[],"cosine_similarity":0.0}\n',
            data_path=data_path,
            document_path=document_path,
        )

    assert not data_path.exists()
    assert not document_path.exists()


@pytest.mark.asyncio
async def test_document_write_failure_rolls_back_result_history(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    result = await run_experiment(
        "문장 A",
        "문장 B",
        embedder=FakeEmbedder(),
        model="nvidia/nemotron-3-embed-1b",
    )
    stdout = json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    data_path = tmp_path / "runs.json"
    document_path = tmp_path / "results.md"
    original_write = experiment_module._atomic_write
    calls = 0

    def fail_second_write(path: Path, content: str) -> None:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("document unavailable")
        original_write(path, content)

    monkeypatch.setattr(experiment_module, "_atomic_write", fail_second_write)

    with pytest.raises(OSError, match="document unavailable"):
        record_experiment_result(
            result,
            stdout=stdout,
            data_path=data_path,
            document_path=document_path,
        )

    assert not data_path.exists()
    assert not document_path.exists()
