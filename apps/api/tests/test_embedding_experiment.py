from math import isclose

import pytest

from scripts.experiment_embeddings import run_experiment


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
