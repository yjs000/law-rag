from __future__ import annotations

import asyncio
import time
from collections.abc import Callable
from math import fsum, isfinite, sqrt
from typing import Any, Literal

from openai import AsyncOpenAI

from app.domain.provider_attempts import ProviderAttemptsExhausted
from app.provider_observability import (
    classify_provider_failure,
    emit_provider_attempt,
    provider_attempt_scope,
)

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
        client_factory: Callable[[], Any] | None = None,
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
        self.client = (client_factory or (
            lambda: AsyncOpenAI(
                api_key=api_key,
                base_url=base_url,
                timeout=timeout_seconds,
                max_retries=0,
            )
        ))()
        self.model = model
        self.dimensions = dimensions
        self.input_type = input_type
        self.timeout_seconds = timeout_seconds

    async def embed(self, texts: list[str]) -> list[list[float]]:
        with provider_attempt_scope():
            if not texts:
                return []
            if any(not isinstance(text, str) or not text.strip() for text in texts):
                raise ValueError("embedding input must contain non-empty strings")

            deadline = time.monotonic() + self.timeout_seconds
            attempt_started = time.monotonic()
            try:
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
                result = [self._slice_and_normalize(item.embedding) for item in ordered]
            except asyncio.CancelledError:
                finished_at = time.monotonic()
                emit_provider_attempt(
                    operation="query_embedding",
                    attempt=1,
                    max_attempts=1,
                    outcome="failed",
                    failure_kind="cancelled",
                    upstream_status=None,
                    elapsed_ms=max(int((finished_at - attempt_started) * 1000), 0),
                    remaining_ms=max(int((deadline - finished_at) * 1000), 0),
                    retry_scheduled=False,
                )
                raise
            except Exception as exc:  # noqa: BLE001 - classified without provider data
                finished_at = time.monotonic()
                failure_kind, upstream_status = classify_provider_failure(exc)
                emit_provider_attempt(
                    operation="query_embedding",
                    attempt=1,
                    max_attempts=1,
                    outcome="failed",
                    failure_kind=failure_kind,
                    upstream_status=upstream_status,
                    elapsed_ms=max(int((finished_at - attempt_started) * 1000), 0),
                    remaining_ms=max(int((deadline - finished_at) * 1000), 0),
                    retry_scheduled=False,
                )
                if failure_kind in {"provider_http", "timeout", "connection"}:
                    raise ProviderAttemptsExhausted(
                        failure_kind=failure_kind,
                        upstream_status=upstream_status,
                    ) from None
                raise
            else:
                finished_at = time.monotonic()
                emit_provider_attempt(
                    operation="query_embedding",
                    attempt=1,
                    max_attempts=1,
                    outcome="succeeded",
                    failure_kind=None,
                    upstream_status=None,
                    elapsed_ms=max(int((finished_at - attempt_started) * 1000), 0),
                    remaining_ms=max(int((deadline - finished_at) * 1000), 0),
                    retry_scheduled=False,
                )
                return result

    async def aclose(self) -> None:
        """Release the process-owned NVIDIA HTTP client."""

        await self.client.close()

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
