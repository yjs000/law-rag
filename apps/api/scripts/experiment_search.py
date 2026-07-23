from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime
from math import fsum, isfinite, sqrt
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Protocol

from law_rag_collector.client import LawOpenApiClient, RawResponse, SearchRecord
from law_rag_collector.settings import CollectorSettings
from law_rag_core.domain.catalog import SourceKind
from law_rag_core.domain.entities import LegalDocumentRecord, ProvisionRecord

from app.adapters.nvidia_nim_embedder import NvidiaNimEmbedder
from app.settings import Settings

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_CORPUS_PATH = REPOSITORY_ROOT / ".data" / "experiments" / "search" / "corpus.json"
PREPARE_COMMAND = "uv run --directory apps/api python -m scripts.experiment_search prepare"
MODEL = "nvidia/nemotron-3-embed-1b"
DIMENSIONS = 512
EMBEDDING_VERSION = "1"
DEFAULT_EMBEDDING_BATCH_SIZE = 32


@dataclass(frozen=True, slots=True)
class SourceSpec:
    title: str
    user_url: str
    mst: str | None = None
    effective_date: date | None = None


SOURCE_SPECS = (
    SourceSpec(
        title="저작권법",
        user_url=(
            "https://www.law.go.kr/LSW/LsiJoLinkP.do?lsNm=%EC%A0%80%EC%9E%91%EA%B6%8C%EB%B2%95#"
        ),
    ),
    SourceSpec(
        title="전기사업법",
        user_url="https://www.law.go.kr/LSW/lsInfoP.do?lsiSeq=180380#0000",
        mst="180380",
        effective_date=date(2016, 7, 28),
    ),
    SourceSpec(
        title="신에너지 및 재생에너지 개발ㆍ이용ㆍ보급 촉진법",
        user_url=("https://www.law.go.kr/법령/신에너지및재생에너지개발ㆍ이용ㆍ보급촉진법"),
    ),
)


class Embedder(Protocol):
    async def embed(self, texts: list[str]) -> list[list[float]]: ...


@dataclass(frozen=True, slots=True)
class LoadedSource:
    spec: SourceSpec
    document: LegalDocumentRecord
    raw: RawResponse


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Open API 법령의 기존 파서 청크 전체를 사용하는 로컬 NVIDIA 벡터 검색 실험"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    prepare = subparsers.add_parser(
        "prepare", help="3개 법령의 기존 파서 청크 전체를 저장하고 임베딩"
    )
    prepare.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS_PATH)
    prepare.add_argument("--batch-size", type=int, default=DEFAULT_EMBEDDING_BATCH_SIZE)
    ask = subparsers.add_parser("ask", help="질문을 임베딩해 로컬 청크 상위 3개 검색")
    ask.add_argument("--question")
    ask.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS_PATH)
    return parser


def _settings() -> tuple[CollectorSettings, Settings]:
    env_files = (
        REPOSITORY_ROOT / ".env",
        REPOSITORY_ROOT / ".env.local",
        REPOSITORY_ROOT / "apps" / "api" / ".env.local",
        REPOSITORY_ROOT / "apps" / "collector" / ".env.local",
    )
    collector = CollectorSettings(_env_file=env_files)
    api = Settings(_env_file=env_files)
    return collector, api


def _exact_record(records: list[SearchRecord], spec: SourceSpec) -> SearchRecord:
    exact = [
        record
        for record in records
        if record.title == spec.title and (spec.mst is None or record.mst == spec.mst)
    ]
    if len(exact) != 1:
        version = f", MST={spec.mst}" if spec.mst else ""
        raise ValueError(f"정확 법령 검색 결과가 1건이 아닙니다: {spec.title}{version}")
    record = exact[0]
    if not record.source_id or not record.mst:
        raise ValueError("검색 결과에 source_id 또는 MST가 없습니다")
    return record


async def _load_source(client: LawOpenApiClient, spec: SourceSpec) -> LoadedSource:
    historical = spec.mst is not None
    search = await client.search(spec.title, SourceKind.LAW, historical=historical)
    record = _exact_record(search.value, spec)
    parsed = await client.document(
        expected_title=spec.title,
        source_kind=SourceKind.LAW,
        source_id=record.source_id,
        mst=record.mst,
        historical=historical,
        effective_date=spec.effective_date,
    )
    return LoadedSource(spec, parsed.value, parsed.raw)


def _embedding_text(source: LoadedSource, provision: ProvisionRecord) -> str:
    heading = f" ({provision.heading})" if provision.heading else ""
    return f"{source.document.title}\n{provision.path}{heading}\n{provision.content}"


def _validate_vector(vector: object) -> list[float]:
    if (
        not isinstance(vector, list)
        or len(vector) != DIMENSIONS
        or any(
            isinstance(value, bool) or not isinstance(value, int | float) or not isfinite(value)
            for value in vector
        )
    ):
        raise ValueError("embedding must contain 512 finite floats")
    normalized = [float(value) for value in vector]
    norm = sqrt(fsum(value * value for value in normalized))
    if not isfinite(norm) or norm == 0:
        raise ValueError("embedding norm must be finite and non-zero")
    return normalized


async def build_corpus(
    sources: list[LoadedSource],
    *,
    embedder: Embedder,
    generated_at: str | None = None,
    embedding_batch_size: int = DEFAULT_EMBEDDING_BATCH_SIZE,
) -> dict[str, object]:
    if len(sources) != len(SOURCE_SPECS):
        raise ValueError("experiment C requires exactly three legal sources")
    if embedding_batch_size <= 0:
        raise ValueError("embedding batch size must be positive")
    selected = [
        (source, provision) for source in sources for provision in source.document.provisions
    ]
    empty_sources = [source.spec.title for source in sources if not source.document.provisions]
    if empty_sources:
        raise ValueError(f"parser returned no chunks: {', '.join(empty_sources)}")
    embedding_texts = [_embedding_text(source, provision) for source, provision in selected]
    vectors: list[list[float]] = []
    for start in range(0, len(embedding_texts), embedding_batch_size):
        batch = embedding_texts[start : start + embedding_batch_size]
        batch_vectors = await embedder.embed(batch)
        if len(batch_vectors) != len(batch):
            raise ValueError("embedder returned an unexpected batch size")
        vectors.extend(batch_vectors)
    if len(vectors) != len(selected):
        raise ValueError("embedder returned an unexpected batch size")

    chunks: list[dict[str, object]] = []
    for ordinal, ((source, provision), embedding_text, vector) in enumerate(
        zip(selected, embedding_texts, vectors, strict=True), start=1
    ):
        validated_vector = _validate_vector(vector)
        chunks.append(
            {
                "chunk_id": (f"{source.document.source_id}:{source.document.mst}:{provision.path}"),
                "ordinal": ordinal,
                "title": source.document.title,
                "source_kind": source.document.source_kind.value,
                "source_id": source.document.source_id,
                "mst": source.document.mst,
                "effective_from": (
                    source.document.effective_from.isoformat()
                    if source.document.effective_from
                    else None
                ),
                "source_url": source.document.source_url,
                "user_url": source.spec.user_url,
                "raw_format": source.raw.wire_format,
                "raw_sha256": source.document.raw_sha256,
                "fallback_reason": source.raw.fallback_reason,
                "parser_schema_version": source.document.parser_schema_version,
                "path": provision.path,
                "heading": provision.heading,
                "parent_path": provision.parent_path,
                "content": provision.content,
                "embedding_text": embedding_text,
                "embedding": validated_vector,
            }
        )

    return {
        "schema_version": 1,
        "experiment": "C",
        "generated_by": PREPARE_COMMAND,
        "generated_at": generated_at
        or datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "storage": "local_json",
        "source_count": len(sources),
        "chunk_count": len(chunks),
        "embedding": {
            "provider": "nvidia_nim",
            "model": MODEL,
            "dimensions": DIMENSIONS,
            "embedding_version": EMBEDDING_VERSION,
            "batch_size": embedding_batch_size,
            "document_input_type": "passage",
            "query_input_type": "query",
            "similarity": "cosine",
        },
        "chunks": chunks,
    }


def _atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        with NamedTemporaryFile(
            "w", encoding="utf-8", newline="\n", dir=path.parent, delete=False
        ) as temporary:
            temporary.write(content)
            temporary.flush()
            os.fsync(temporary.fileno())
            temporary_path = Path(temporary.name)
        os.replace(temporary_path, path)
        temporary_path = None
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


def save_corpus(path: Path, corpus: dict[str, object]) -> None:
    serialized = json.dumps(corpus, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    _atomic_write(path, serialized)


def load_corpus(path: Path) -> dict[str, object]:
    if not path.exists():
        raise FileNotFoundError("experiment C corpus is missing; run prepare first")
    corpus = json.loads(path.read_text(encoding="utf-8"))
    if (
        not isinstance(corpus, dict)
        or corpus.get("schema_version") != 1
        or corpus.get("experiment") != "C"
        or not isinstance(corpus.get("chunks"), list)
        or isinstance(corpus.get("chunk_count"), bool)
        or not isinstance(corpus.get("chunk_count"), int)
        or corpus["chunk_count"] <= 0
        or len(corpus["chunks"]) != corpus["chunk_count"]
    ):
        raise ValueError("invalid experiment C corpus metadata")
    embedding = corpus.get("embedding")
    if not isinstance(embedding, dict) or (
        embedding.get("model"),
        embedding.get("dimensions"),
        embedding.get("embedding_version"),
    ) != (MODEL, DIMENSIONS, EMBEDDING_VERSION):
        raise ValueError("experiment C corpus embedding contract mismatch")
    for chunk in corpus["chunks"]:
        if not isinstance(chunk, dict):
            raise ValueError("invalid experiment C chunk")
        _validate_vector(chunk.get("embedding"))
        for key in ("chunk_id", "title", "source_id", "mst", "path", "content"):
            if not isinstance(chunk.get(key), str) or not chunk[key].strip():
                raise ValueError("invalid experiment C chunk metadata")
    return corpus


def _cosine(left: list[float], right: list[float]) -> float:
    norm_left = sqrt(fsum(value * value for value in left))
    norm_right = sqrt(fsum(value * value for value in right))
    if norm_left == 0 or norm_right == 0:
        raise ValueError("cosine similarity requires non-zero vectors")
    score = fsum(a * b for a, b in zip(left, right, strict=True)) / (norm_left * norm_right)
    if not isfinite(score):
        raise ValueError("cosine similarity must be finite")
    return min(1.0, max(-1.0, score))


async def search_corpus(
    question: str,
    corpus: dict[str, object],
    *,
    embedder: Embedder,
    top_k: int = 3,
) -> dict[str, object]:
    if not question.strip():
        raise ValueError("question must not be empty")
    if top_k != 3:
        raise ValueError("experiment C top_k must be 3")
    query_vectors = await embedder.embed([question])
    if len(query_vectors) != 1:
        raise ValueError("query embedder returned an unexpected batch size")
    query_vector = _validate_vector(query_vectors[0])
    chunks = corpus["chunks"]
    assert isinstance(chunks, list)
    scored: list[tuple[float, dict[str, object]]] = []
    for chunk in chunks:
        assert isinstance(chunk, dict)
        chunk_vector = _validate_vector(chunk["embedding"])
        scored.append((_cosine(query_vector, chunk_vector), chunk))
    scored.sort(key=lambda item: (-item[0], str(item[1]["chunk_id"])))
    results = [
        {
            "rank": rank,
            "score": score,
            "chunk_id": chunk["chunk_id"],
            "title": chunk["title"],
            "source_id": chunk["source_id"],
            "mst": chunk["mst"],
            "effective_from": chunk["effective_from"],
            "path": chunk["path"],
            "heading": chunk["heading"],
            "content": chunk["content"],
        }
        for rank, (score, chunk) in enumerate(scored[:top_k], start=1)
    ]
    return {
        "experiment": "C",
        "question": question,
        "provider": "nvidia_nim",
        "model": MODEL,
        "corpus_chunks": len(chunks),
        "top_k": top_k,
        "score": "cosine_similarity",
        "results": results,
    }


def _passage_embedder(settings: Settings) -> NvidiaNimEmbedder:
    if not settings.nvidia_api_key:
        raise RuntimeError("nvidia_api_key_missing")
    return NvidiaNimEmbedder(
        api_key=settings.nvidia_api_key,
        base_url=settings.nvidia_base_url,
        model=settings.nvidia_embedding_model,
        dimensions=settings.embedding_dimensions,
        timeout_seconds=settings.embedding_timeout_seconds,
        input_type="passage",
    )


def _query_embedder(settings: Settings) -> NvidiaNimEmbedder:
    if not settings.nvidia_api_key:
        raise RuntimeError("nvidia_api_key_missing")
    return NvidiaNimEmbedder(
        api_key=settings.nvidia_api_key,
        base_url=settings.nvidia_base_url,
        model=settings.nvidia_embedding_model,
        dimensions=settings.embedding_dimensions,
        timeout_seconds=settings.embedding_timeout_seconds,
        input_type="query",
    )


async def _prepare(path: Path, *, embedding_batch_size: int) -> dict[str, object]:
    collector_settings, api_settings = _settings()
    if not collector_settings.law_open_api_oc:
        raise RuntimeError("law_open_api_oc_missing")
    async with LawOpenApiClient(
        oc=collector_settings.law_open_api_oc,
        base_url=collector_settings.law_open_api_base_url,
        timeout=collector_settings.collector_request_timeout_seconds,
    ) as client:
        sources = [await _load_source(client, spec) for spec in SOURCE_SPECS]
    corpus = await build_corpus(
        sources,
        embedder=_passage_embedder(api_settings),
        embedding_batch_size=embedding_batch_size,
    )
    save_corpus(path, corpus)
    return {
        "status": "ready",
        "experiment": "C",
        "corpus_path": str(path),
        "source_count": corpus["source_count"],
        "chunk_count": corpus["chunk_count"],
        "model": MODEL,
        "dimensions": DIMENSIONS,
        "sources": [
            {
                "title": source.document.title,
                "mst": source.document.mst,
                "effective_from": (
                    source.document.effective_from.isoformat()
                    if source.document.effective_from
                    else None
                ),
                "chunk_count": len(source.document.provisions),
            }
            for source in sources
        ],
    }


async def _ask(path: Path, question: str) -> dict[str, object]:
    _, api_settings = _settings()
    corpus = load_corpus(path)
    return await search_corpus(question, corpus, embedder=_query_embedder(api_settings))


def _safe_error(code: str) -> str:
    return json.dumps(
        {"status": "error", "code": code, "message": "실험 C를 실행하지 못했습니다"},
        ensure_ascii=False,
        separators=(",", ":"),
    )


def run_cli(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "prepare":
            result = asyncio.run(_prepare(args.corpus, embedding_batch_size=args.batch_size))
        else:
            question = args.question if args.question is not None else input("질문> ")
            result = asyncio.run(_ask(args.corpus, question))
    except RuntimeError as exc:
        known = {"nvidia_api_key_missing", "law_open_api_oc_missing"}
        code = str(exc) if str(exc) in known else "experiment_c_failed"
        print(_safe_error(code), file=sys.stderr)
        return 2
    except FileNotFoundError:
        print(_safe_error("corpus_missing"), file=sys.stderr)
        return 2
    except EOFError, KeyboardInterrupt:
        print(_safe_error("question_cancelled"), file=sys.stderr)
        return 130
    except Exception:
        print(_safe_error("experiment_c_failed"), file=sys.stderr)
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
