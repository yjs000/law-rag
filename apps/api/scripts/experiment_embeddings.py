from __future__ import annotations

import argparse
import asyncio
import json
import sys
from collections.abc import Sequence
from math import fsum, isfinite, sqrt
from typing import Protocol

from app.adapters.nvidia_nim_embedder import NvidiaNimEmbedder
from app.settings import get_settings

DEFAULT_SENTENCE_A = "전기사업을 하려는 자는 산업통상자원부장관의 허가를 받아야 한다."
DEFAULT_SENTENCE_B = "산업통상자원부장관의 허가를 받지 않으면 전기사업을 시작할 수 없다."


class Embedder(Protocol):
    async def embed(self, texts: list[str]) -> list[list[float]]: ...


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="NVIDIA NIM으로 두 문장을 임베딩하고 코사인 유사도를 출력한다"
    )
    parser.add_argument("--sentence-a", default=DEFAULT_SENTENCE_A)
    parser.add_argument("--sentence-b", default=DEFAULT_SENTENCE_B)
    return parser


def _norm(vector: list[float]) -> float:
    return sqrt(fsum(value * value for value in vector))


async def run_experiment(
    sentence_a: str,
    sentence_b: str,
    *,
    embedder: Embedder,
    model: str,
) -> dict[str, object]:
    if not sentence_a.strip() or not sentence_b.strip():
        raise ValueError("sentences must not be empty")
    vectors = await embedder.embed([sentence_a, sentence_b])
    if len(vectors) != 2 or any(len(vector) != 512 for vector in vectors):
        raise ValueError("embedder returned an invalid result shape")
    vector_a, vector_b = vectors
    norm_a = _norm(vector_a)
    norm_b = _norm(vector_b)
    if not isfinite(norm_a) or not isfinite(norm_b) or norm_a == 0 or norm_b == 0:
        raise ValueError("embedder returned an invalid vector norm")
    similarity = fsum(a * b for a, b in zip(vector_a, vector_b, strict=True)) / (
        norm_a * norm_b
    )
    if not isfinite(similarity):
        raise ValueError("cosine similarity is not finite")
    similarity = min(1.0, max(-1.0, similarity))
    return {
        "provider": "nvidia_nim",
        "model": model,
        "native_dimensions": 2048,
        "output_dimensions": 512,
        "sentence_a": sentence_a,
        "embedding_a": vector_a,
        "sentence_b": sentence_b,
        "embedding_b": vector_b,
        "norm_a": norm_a,
        "norm_b": norm_b,
        "cosine_similarity": similarity,
    }


async def _run_cli(args: argparse.Namespace) -> dict[str, object]:
    settings = get_settings()
    if not settings.nvidia_api_key:
        raise RuntimeError("nvidia_api_key_missing")
    embedder = NvidiaNimEmbedder(
        api_key=settings.nvidia_api_key,
        base_url=settings.nvidia_base_url,
        model=settings.nvidia_embedding_model,
        dimensions=settings.embedding_dimensions,
        timeout_seconds=settings.embedding_timeout_seconds,
    )
    return await run_experiment(
        args.sentence_a,
        args.sentence_b,
        embedder=embedder,
        model=settings.nvidia_embedding_model,
    )


def run_cli(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        result = asyncio.run(_run_cli(args))
    except RuntimeError as exc:
        code = (
            "nvidia_api_key_missing"
            if str(exc) == "nvidia_api_key_missing"
            else "embedding_failed"
        )
        print(
            json.dumps(
                {"status": "error", "code": code, "message": "NVIDIA 임베딩을 실행하지 못했습니다"},
                ensure_ascii=False,
                separators=(",", ":"),
            ),
            file=sys.stderr,
        )
        return 2
    except Exception:
        print(
            json.dumps(
                {
                    "status": "error",
                    "code": "embedding_failed",
                    "message": "NVIDIA 임베딩을 실행하지 못했습니다",
                },
                ensure_ascii=False,
                separators=(",", ":"),
            ),
            file=sys.stderr,
        )
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))
    return 0


def main() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8")
    raise SystemExit(run_cli())


if __name__ == "__main__":
    main()
