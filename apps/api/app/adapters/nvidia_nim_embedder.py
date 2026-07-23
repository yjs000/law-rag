from __future__ import annotations

from math import fsum, isfinite, sqrt
from typing import Literal

from openai import AsyncOpenAI

NVIDIA_HOSTED_BASE_URL = "https://integrate.api.nvidia.com/v1"
NVIDIA_EMBEDDING_MODEL = "nvidia/nemotron-3-embed-1b"
NATIVE_DIMENSIONS = 2048
OUTPUT_DIMENSIONS = 512


class NvidiaNimEmbedder:
    """NVIDIA hosted NIM embedding adapter with the existing batch contract."""

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str,
        model: str,
        dimensions: int,
        timeout_seconds: float,
        input_type: Literal["query", "passage"] = "query",
    ) -> None:
        if not api_key:
            raise ValueError("NVIDIA API key is required")
        if base_url != NVIDIA_HOSTED_BASE_URL:
            raise ValueError("unsupported NVIDIA hosted NIM base URL")
        if model != NVIDIA_EMBEDDING_MODEL:
            raise ValueError("unsupported NVIDIA embedding model")
        if dimensions != OUTPUT_DIMENSIONS:
            raise ValueError("NVIDIA embedding output dimensions must be 512")
        if input_type not in {"query", "passage"}:
            raise ValueError("unsupported NVIDIA embedding input type")
        self.client = AsyncOpenAI(
            api_key=api_key,
            base_url=base_url,
            timeout=timeout_seconds,
            max_retries=0,
        )
        self.model = model
        self.dimensions = dimensions
        self.input_type = input_type

    async def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        if any(not isinstance(text, str) or not text.strip() for text in texts):
            raise ValueError("embedding input must contain non-empty strings")

        response = await self.client.embeddings.create(
            model=self.model,
            input=texts,
            encoding_format="float",
            extra_body={
                "input_type": self.input_type,
                "modality": "text",
                "embedding_type": "float",
                "truncate": "NONE",
            },
        )
        ordered = sorted(response.data, key=lambda item: item.index)
        if len(ordered) != len(texts) or [item.index for item in ordered] != list(
            range(len(texts))
        ):
            raise ValueError("NVIDIA NIM returned invalid embedding indexes")
        return [self._slice_and_normalize(item.embedding) for item in ordered]

    def _slice_and_normalize(self, embedding: list[float]) -> list[float]:
        if len(embedding) != NATIVE_DIMENSIONS:
            raise ValueError("NVIDIA NIM returned an unexpected embedding dimension")
        if any(
            isinstance(value, bool)
            or not isinstance(value, int | float)
            or not isfinite(value)
            for value in embedding
        ):
            raise ValueError("NVIDIA NIM returned a non-finite embedding value")

        sliced = [float(value) for value in embedding[: self.dimensions]]
        norm = sqrt(fsum(value * value for value in sliced))
        if not isfinite(norm) or norm == 0:
            raise ValueError("NVIDIA NIM returned a zero-norm sliced embedding")
        return [value / norm for value in sliced]
