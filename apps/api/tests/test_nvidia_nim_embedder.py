from math import isclose
from types import SimpleNamespace

import pytest

from app.adapters.nvidia_nim_embedder import NvidiaNimEmbedder


def _embedder(**overrides) -> NvidiaNimEmbedder:
    values = {
        "api_key": "nvapi-test",
        "base_url": "https://integrate.api.nvidia.com/v1",
        "model": "nvidia/nemotron-3-embed-1b",
        "dimensions": 512,
        "timeout_seconds": 30,
    }
    values.update(overrides)
    return NvidiaNimEmbedder(**values)


@pytest.mark.asyncio
async def test_embedder_preserves_indexes_slices_and_l2_normalizes() -> None:
    embedder = _embedder()
    captured: dict[str, object] = {}
    first = [3.0, 4.0, *([0.0] * 2046)]
    second = [4.0, 3.0, *([0.0] * 2046)]

    async def create(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(
            data=[
                SimpleNamespace(index=1, embedding=second),
                SimpleNamespace(index=0, embedding=first),
            ]
        )

    embedder.client = SimpleNamespace(embeddings=SimpleNamespace(create=create))
    vectors = await embedder.embed(["문장 A", "문장 B"])

    assert captured["model"] == "nvidia/nemotron-3-embed-1b"
    assert captured["input"] == ["문장 A", "문장 B"]
    assert captured["extra_body"] == {
        "input_type": "query",
        "modality": "text",
        "embedding_type": "float",
        "truncate": "NONE",
    }
    assert len(vectors) == 2
    assert all(len(vector) == 512 for vector in vectors)
    assert vectors[0][:2] == [0.6, 0.8]
    assert vectors[1][:2] == [0.8, 0.6]
    assert all(isclose(sum(value * value for value in vector), 1.0) for vector in vectors)


@pytest.mark.asyncio
async def test_embedder_empty_batch_does_not_call_provider() -> None:
    embedder = _embedder()
    embedder.client = None

    assert await embedder.embed([]) == []


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"api_key": ""}, "API key"),
        ({"base_url": "https://attacker.example/v1"}, "base URL"),
        ({"model": "other/model"}, "embedding model"),
        ({"dimensions": 1024}, "dimensions must be 512"),
        ({"input_type": "other"}, "input type"),
    ],
)
def test_embedder_rejects_unsupported_configuration(overrides, message) -> None:
    with pytest.raises(ValueError, match=message):
        _embedder(**overrides)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "data",
    [
        [SimpleNamespace(index=0, embedding=[0.0] * 2048)],
        [SimpleNamespace(index=0, embedding=[1.0] * 2047)],
        [SimpleNamespace(index=0, embedding=[float("nan"), *([0.0] * 2047)])],
    ],
)
async def test_embedder_rejects_invalid_provider_vectors(data) -> None:
    embedder = _embedder()

    async def create(**kwargs):
        return SimpleNamespace(data=data)

    embedder.client = SimpleNamespace(embeddings=SimpleNamespace(create=create))
    with pytest.raises(ValueError):
        await embedder.embed(["문장"])


@pytest.mark.asyncio
async def test_embedder_rejects_missing_or_duplicate_indexes() -> None:
    embedder = _embedder()

    async def create(**kwargs):
        vector = [1.0, *([0.0] * 2047)]
        return SimpleNamespace(
            data=[
                SimpleNamespace(index=0, embedding=vector),
                SimpleNamespace(index=0, embedding=vector),
            ]
        )

    embedder.client = SimpleNamespace(embeddings=SimpleNamespace(create=create))
    with pytest.raises(ValueError, match="indexes"):
        await embedder.embed(["문장 A", "문장 B"])
