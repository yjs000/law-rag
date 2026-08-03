from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import re
import sys
import unicodedata
from collections.abc import Sequence
from contextlib import suppress
from dataclasses import dataclass
from datetime import UTC, date, datetime
from math import fsum, isfinite, sqrt
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Protocol

from defusedxml import ElementTree as ET
from law_rag_collector.client import LawOpenApiClient, RawResponse, SearchRecord
from law_rag_collector.settings import CollectorSettings
from law_rag_core.domain.catalog import SourceKind
from law_rag_core.domain.entities import LegalDocumentRecord, ProvisionRecord

from app.adapters.nvidia_nim_embedder import NvidiaNimEmbedder
from app.settings import Settings

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_CORPUS_PATH = REPOSITORY_ROOT / ".data" / "experiments" / "search" / "corpus.json"
DEFAULT_SEARCH_RUNS_DATA = REPOSITORY_ROOT / ".data" / "experiments" / "search" / "search-runs.json"
DEFAULT_SEARCH_RUNS_REPORT = (
    REPOSITORY_ROOT / ".data" / "experiments" / "search" / "search-results.md"
)
DEFAULT_EVALUATION_QUESTIONS = (
    REPOSITORY_ROOT / "experiments" / "search" / "evaluation-questions.json"
)
DEFAULT_EVALUATION_JSON = REPOSITORY_ROOT / ".data" / "experiments" / "search" / "evaluation.json"
DEFAULT_EVALUATION_REPORT = (
    REPOSITORY_ROOT / "docs" / "generated" / "experiment-c-retrieval-evaluation.md"
)
PREPARE_COMMAND = "uv run --directory apps/api python -m scripts.experiment_search prepare"
ASK_COMMAND = "uv run --directory apps/api python -m scripts.experiment_search ask"
EVALUATE_COMMAND = "uv run --directory apps/api python -m scripts.experiment_search evaluate"
MODEL = "nvidia/nemotron-3-embed-1b"
DIMENSIONS = 512
EMBEDDING_VERSION = "1"
DEFAULT_EMBEDDING_BATCH_SIZE = 32
DEFAULT_CANDIDATE_K = 10
MAX_CANDIDATE_K = 50
ARTICLE_MATCHES_PER_CANDIDATE = 3
CHAPTER_PATTERN = re.compile(r"^\s*제\s*(\d+)\s*장(?:의\s*(\d+))?")
ARTICLE_PATH_PATTERN = re.compile(r"^(제(\d+)조(?:의(\d+))?)(?:/|$)")


@dataclass(frozen=True, slots=True)
class SourceSpec:
    title: str
    user_url: str
    selected_chapters: tuple[int, ...] = ()
    selected_article_range: tuple[int, int] | None = None
    mst: str | None = None
    effective_date: date | None = None


SOURCE_SPECS = (
    SourceSpec(
        title="저작권법",
        user_url=(
            "https://www.law.go.kr/LSW/LsiJoLinkP.do?lsNm=%EC%A0%80%EC%9E%91%EA%B6%8C%EB%B2%95#"
        ),
        selected_chapters=(1, 5),
    ),
    SourceSpec(
        title="전기사업법",
        user_url="https://www.law.go.kr/LSW/lsInfoP.do?lsiSeq=180380#0000",
        selected_chapters=(1, 6),
        mst="180380",
        effective_date=date(2016, 7, 28),
    ),
    SourceSpec(
        title="신에너지 및 재생에너지 개발ㆍ이용ㆍ보급 촉진법",
        user_url=("https://www.law.go.kr/법령/신에너지및재생에너지개발ㆍ이용ㆍ보급촉진법"),
        selected_article_range=(1, 5),
    ),
)


class Embedder(Protocol):
    async def embed(self, texts: list[str]) -> list[list[float]]: ...


@dataclass(frozen=True, slots=True)
class LoadedSource:
    spec: SourceSpec
    document: LegalDocumentRecord
    raw: RawResponse


class ResultRecordingError(RuntimeError):
    pass


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="지정한 장·조 범위의 기존 파서 청크를 사용하는 로컬 NVIDIA 벡터 검색 실험"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    prepare = subparsers.add_parser("prepare", help="3개 법령의 지정 장·조 범위를 저장하고 임베딩")
    prepare.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS_PATH)
    prepare.add_argument("--batch-size", type=int, default=DEFAULT_EMBEDDING_BATCH_SIZE)
    ask = subparsers.add_parser("ask", help="질문을 임베딩해 raw 청크와 조 단위 후보 검색")
    ask.add_argument("--question")
    ask.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS_PATH)
    ask.add_argument("--candidate-k", type=int, default=DEFAULT_CANDIDATE_K)
    ask.add_argument("--results-data", type=Path, default=DEFAULT_SEARCH_RUNS_DATA)
    ask.add_argument("--results-report", type=Path, default=DEFAULT_SEARCH_RUNS_REPORT)
    ask.add_argument("--no-record", action="store_true")
    evaluate = subparsers.add_parser("evaluate", help="고정 질문셋의 dense 검색 순위 평가")
    evaluate.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS_PATH)
    evaluate.add_argument("--questions", type=Path, default=DEFAULT_EVALUATION_QUESTIONS)
    evaluate.add_argument("--candidate-k", type=int, default=DEFAULT_CANDIDATE_K)
    evaluate.add_argument("--json-output", type=Path, default=DEFAULT_EVALUATION_JSON)
    evaluate.add_argument("--report", type=Path, default=DEFAULT_EVALUATION_REPORT)
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


def _article_root(path: str) -> tuple[str, int] | None:
    match = ARTICLE_PATH_PATTERN.match(path)
    if match is None:
        return None
    return match.group(1), int(match.group(2))


def _clean_text(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _json_nodes(value: object) -> list[dict[str, object]]:
    if isinstance(value, dict):
        return [value]
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    return []


def _raw_article_events(source: LoadedSource) -> list[tuple[str, str | None, str]]:
    events: list[tuple[str, str | None, str]] = []
    if source.raw.wire_format == "JSON":
        try:
            payload = json.loads(source.raw.body)
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid legal hierarchy JSON: {source.spec.title}") from exc

        article_nodes: list[dict[str, object]] = []

        def walk(value: object) -> None:
            nonlocal article_nodes
            if article_nodes:
                return
            if isinstance(value, dict):
                if "조문단위" in value:
                    article_nodes = _json_nodes(value["조문단위"])
                    return
                for child in value.values():
                    walk(child)
            elif isinstance(value, list):
                for child in value:
                    walk(child)

        walk(payload)
        for node in article_nodes:
            content = _clean_text(node.get("조문내용"))
            if not content:
                continue
            kind = _clean_text(node.get("조문여부")) or "조문"
            article_path = None
            if kind == "조문":
                number = _clean_text(node.get("조문번호"))
                if number:
                    article_path = f"제{number}조"
                    branch = _clean_text(node.get("조문가지번호"))
                    if branch and branch not in {"0", "00"}:
                        article_path += f"의{branch}"
            events.append((kind, article_path, content))
    else:
        try:
            root = ET.fromstring(source.raw.body)
        except ET.ParseError as exc:
            raise ValueError(f"invalid legal hierarchy XML: {source.spec.title}") from exc

        def local_name(tag: str) -> str:
            return tag.rsplit("}", 1)[-1]

        def direct_text(node: ET.Element, name: str) -> str:
            for child in list(node):
                if local_name(child.tag) == name:
                    return _clean_text(" ".join(child.itertext()))
            return ""

        for node in root.iter():
            if local_name(node.tag) != "조문단위":
                continue
            content = direct_text(node, "조문내용")
            if not content:
                continue
            kind = direct_text(node, "조문여부") or "조문"
            article_path = None
            if kind == "조문":
                number = direct_text(node, "조문번호")
                if number:
                    article_path = f"제{number}조"
                    branch = direct_text(node, "조문가지번호")
                    if branch and branch not in {"0", "00"}:
                        article_path += f"의{branch}"
            events.append((kind, article_path, content))
    if not events:
        raise ValueError(f"legal hierarchy is missing: {source.spec.title}")
    return events


def _validate_provision_hierarchy(
    title: str, provisions: list[ProvisionRecord]
) -> dict[str, object]:
    by_path: dict[str, ProvisionRecord] = {}
    roots: set[str] = set()
    for provision in provisions:
        if provision.path in by_path:
            raise ValueError(f"duplicate provision path: {title} {provision.path}")
        by_path[provision.path] = provision
        article = _article_root(provision.path)
        if article is None:
            raise ValueError(f"provision has no article root: {title} {provision.path}")
        if provision.parent_path is None:
            if provision.path != article[0]:
                raise ValueError(f"non-root provision has no parent: {title} {provision.path}")
            if CHAPTER_PATTERN.match(provision.content):
                raise ValueError(f"article body is a structure marker: {title} {provision.path}")
            roots.add(provision.path)

    for provision in provisions:
        if provision.parent_path is None:
            continue
        parent = by_path.get(provision.parent_path)
        if parent is None:
            raise ValueError(f"provision parent is missing: {title} {provision.path}")
        provision_article = _article_root(provision.path)
        parent_article = _article_root(parent.path)
        if (
            provision_article is None
            or parent_article is None
            or provision_article[0] != parent_article[0]
        ):
            raise ValueError(f"provision parent crosses articles: {title} {provision.path}")

    expected_roots = {
        article[0]
        for provision in provisions
        if (article := _article_root(provision.path)) is not None
    }
    if roots != expected_roots:
        missing = ", ".join(sorted(expected_roots - roots))
        raise ValueError(f"article root is missing: {title} {missing}")
    return {
        "status": "passed",
        "checks": [
            "unique_paths",
            "article_body_not_structure_marker",
            "article_root_present",
            "parent_path_resolved",
            "parent_within_article",
        ],
        "article_count": len(roots),
        "chunk_count": len(provisions),
    }


def _select_chapters(
    source: LoadedSource, chapters: tuple[int, ...]
) -> tuple[list[ProvisionRecord], dict[str, object]]:
    current_chapter: tuple[int, int | None] | None = None
    chapter_by_article: dict[str, tuple[int, int | None] | None] = {}
    found_chapters: set[tuple[int, int | None]] = set()
    for kind, article_path, content in _raw_article_events(source):
        marker = CHAPTER_PATTERN.match(content)
        if marker is not None:
            current_chapter = (
                int(marker.group(1)),
                int(marker.group(2)) if marker.group(2) else None,
            )
            found_chapters.add(current_chapter)
        if kind == "조문" and article_path is not None:
            chapter_by_article[article_path] = current_chapter

    requested = {(chapter, None) for chapter in chapters}
    missing = requested - found_chapters
    if missing:
        labels = ", ".join(f"제{chapter}장" for chapter, _ in sorted(missing))
        raise ValueError(
            f"parser result is missing requested chapters: {source.spec.title} {labels}"
        )

    selected_articles = {
        article for article, chapter in chapter_by_article.items() if chapter in requested
    }
    selected = [
        provision
        for provision in source.document.provisions
        if (article := _article_root(provision.path)) is not None
        and article[0] in selected_articles
    ]
    validation = _validate_provision_hierarchy(source.document.title, selected)
    return selected, {
        "title": source.document.title,
        "mst": source.document.mst,
        "effective_from": (
            source.document.effective_from.isoformat() if source.document.effective_from else None
        ),
        "type": "chapters",
        "chapters": [f"제{chapter}장" for chapter in chapters],
        "article_paths": sorted(selected_articles),
        "chunk_count": len(selected),
        "hierarchy_source": f"open_api_{source.raw.wire_format.lower()}",
        "validation": validation,
    }


def _select_article_range(
    source: LoadedSource, article_range: tuple[int, int]
) -> tuple[list[ProvisionRecord], dict[str, object]]:
    start, end = article_range
    selected: list[ProvisionRecord] = []
    selected_articles: set[str] = set()
    found_numbers: set[int] = set()
    for provision in source.document.provisions:
        article = _article_root(provision.path)
        if article is None or not start <= article[1] <= end:
            continue
        selected.append(provision)
        selected_articles.add(article[0])
        if provision.parent_path is None:
            found_numbers.add(article[1])

    missing = set(range(start, end + 1)) - found_numbers
    if missing:
        labels = ", ".join(f"제{number}조" for number in sorted(missing))
        raise ValueError(
            f"parser result is missing requested articles: {source.spec.title} {labels}"
        )
    validation = _validate_provision_hierarchy(source.document.title, selected)
    return selected, {
        "title": source.document.title,
        "mst": source.document.mst,
        "effective_from": (
            source.document.effective_from.isoformat() if source.document.effective_from else None
        ),
        "type": "article_range",
        "article_range": [f"제{start}조", f"제{end}조"],
        "article_paths": sorted(selected_articles),
        "chunk_count": len(selected),
        "hierarchy_source": "provision_paths",
        "validation": validation,
    }


def _select_provisions(
    source: LoadedSource,
) -> tuple[list[ProvisionRecord], dict[str, object]]:
    if source.spec.selected_chapters and source.spec.selected_article_range is None:
        return _select_chapters(source, source.spec.selected_chapters)
    if source.spec.selected_article_range is not None and not source.spec.selected_chapters:
        return _select_article_range(source, source.spec.selected_article_range)
    raise ValueError(f"invalid experiment C selection policy: {source.spec.title}")


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
    empty_sources = [source.spec.title for source in sources if not source.document.provisions]
    if empty_sources:
        raise ValueError(f"parser returned no chunks: {', '.join(empty_sources)}")
    selections = [_select_provisions(source) for source in sources]
    selected = [
        (source, provision)
        for source, (provisions, _) in zip(sources, selections, strict=True)
        for provision in provisions
    ]
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
        "selection": {
            "strategy": "fixed_legal_structure",
            "sources": [metadata for _, metadata in selections],
        },
        "validation": {
            "status": "passed",
            "source_count": len(sources),
            "checks": ["source_scope", "article_body", "provision_hierarchy"],
        },
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


def _stage_text(path: Path, content: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = NamedTemporaryFile(
        "w",
        encoding="utf-8",
        newline="\n",
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=path.parent,
        delete=False,
    )
    temporary = Path(handle.name)
    try:
        with handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
    except Exception:
        with suppress(OSError):
            temporary.unlink()
        raise
    return temporary


def _restore_text(path: Path, previous: bytes | None) -> None:
    if previous is None:
        with suppress(FileNotFoundError):
            path.unlink()
        return
    temporary = _stage_text(path, previous.decode("utf-8"))
    os.replace(temporary, path)


def _atomic_write_many(outputs: list[tuple[Path, str]]) -> None:
    resolved = [path.resolve() for path, _ in outputs]
    if len(set(resolved)) != len(resolved):
        raise ResultRecordingError("search result output paths must be different")
    previous = {path: path.read_bytes() if path.exists() else None for path, _ in outputs}
    staged: list[tuple[Path, Path]] = []
    replaced: list[Path] = []
    try:
        staged = [(path, _stage_text(path, content)) for path, content in outputs]
        for target, temporary in staged:
            os.replace(temporary, target)
            replaced.append(target)
    except (OSError, UnicodeError) as exc:
        for _, temporary in staged:
            with suppress(FileNotFoundError):
                temporary.unlink()
        for target in reversed(replaced):
            with suppress(OSError, UnicodeError):
                _restore_text(target, previous[target])
        raise ResultRecordingError("search result outputs could not be saved") from exc


def save_corpus(path: Path, corpus: dict[str, object]) -> None:
    serialized = json.dumps(corpus, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    _atomic_write(path, serialized)


def _display_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(REPOSITORY_ROOT).as_posix()
    except ValueError:
        return str(resolved)


def _load_search_runs(path: Path) -> list[dict[str, object]]:
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ResultRecordingError("invalid experiment C search history") from exc
    if (
        not isinstance(payload, dict)
        or payload.get("schema_version") != 1
        or payload.get("experiment") != "C"
        or not isinstance(payload.get("runs"), list)
    ):
        raise ResultRecordingError("invalid experiment C search history")
    runs = payload["runs"]
    for expected_run, run in enumerate(runs, start=1):
        if (
            not isinstance(run, dict)
            or run.get("run") != expected_run
            or not isinstance(run.get("recorded_at"), str)
            or not isinstance(run.get("corpus_sha256"), str)
            or not isinstance(run.get("stdout_sha256"), str)
            or not isinstance(run.get("stdout"), str)
            or hashlib.sha256(run["stdout"].encode("utf-8")).hexdigest() != run["stdout_sha256"]
        ):
            raise ResultRecordingError("invalid experiment C search history")
    return runs


def _markdown_cell(value: object) -> str:
    return str(value).replace("|", "\\|").replace("\r", " ").replace("\n", " ")


def _render_search_report(runs: list[dict[str, object]]) -> str:
    lines = [
        "# 실험 C — 실제 검색 실행 기록",
        "",
        f"> 생성 명령: `{ASK_COMMAND}`",
        f"> 마지막 기록: `{runs[-1]['recorded_at']}`",
        "",
        "이 문서는 사용자가 명시적으로 실행한 로컬 실험 C의 실제 stdout 이력이다.",
        "운영 로그가 아니며 `.data/` 아래에만 저장되어 Git에 포함되지 않는다.",
        "",
        "## 실행 비교",
        "",
        "| 실행 | 기록 시각 | 질문 | candidate k | raw 1위 | 조 1위 |",
        "| ---: | --- | --- | ---: | --- | --- |",
    ]
    parsed_results: list[dict[str, object]] = []
    for run in runs:
        parsed = json.loads(str(run["stdout"]))
        if not isinstance(parsed, dict):
            raise ResultRecordingError("invalid experiment C recorded stdout")
        parsed_results.append(parsed)
        raw = parsed.get("raw_chunk_candidates")
        articles = parsed.get("article_candidates")
        raw_first = raw[0] if isinstance(raw, list) and raw else {}
        article_first = articles[0] if isinstance(articles, list) and articles else {}
        lines.append(
            "| "
            f"{run['run']} | {_markdown_cell(run['recorded_at'])} | "
            f"{_markdown_cell(parsed.get('question', ''))} | "
            f"{_markdown_cell(parsed.get('candidate_k', ''))} | "
            f"{_markdown_cell(raw_first.get('title', ''))} "
            f"{_markdown_cell(raw_first.get('path', ''))} | "
            f"{_markdown_cell(article_first.get('title', ''))} "
            f"{_markdown_cell(article_first.get('article_path', ''))} |"
        )
    lines.extend(["", "## 실제 stdout", ""])
    for run in runs:
        lines.extend(
            [
                f"### 실행 {run['run']}",
                "",
                f"- 기록 시각: `{run['recorded_at']}`",
                f"- corpus SHA-256: `{run['corpus_sha256']}`",
                f"- stdout SHA-256: `{run['stdout_sha256']}`",
                "",
                "```json",
                str(run["stdout"]).rstrip("\n"),
                "```",
                "",
            ]
        )
    return "\n".join(lines)


def record_search_result(
    result: dict[str, object],
    *,
    corpus_path: Path,
    data_path: Path,
    report_path: Path,
) -> str:
    try:
        corpus_sha256 = hashlib.sha256(corpus_path.read_bytes()).hexdigest()
    except OSError as exc:
        raise ResultRecordingError("experiment C corpus could not be hashed") from exc
    runs = _load_search_runs(data_path)
    recorded_at = datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")
    recorded_result = dict(result)
    recorded_result["recording"] = {
        "run": len(runs) + 1,
        "recorded_at": recorded_at,
        "data_path": _display_path(data_path),
        "report_path": _display_path(report_path),
    }
    stdout = json.dumps(recorded_result, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    runs.append(
        {
            "run": len(runs) + 1,
            "recorded_at": recorded_at,
            "corpus_path": _display_path(corpus_path),
            "corpus_sha256": corpus_sha256,
            "stdout_sha256": hashlib.sha256(stdout.encode("utf-8")).hexdigest(),
            "stdout": stdout,
        }
    )
    history = {
        "schema_version": 1,
        "experiment": "C",
        "generated_by": ASK_COMMAND,
        "updated_at": recorded_at,
        "runs": runs,
    }
    history_json = json.dumps(history, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    report = _render_search_report(runs)
    _atomic_write_many([(data_path, history_json), (report_path, report)])
    return stdout


def _validate_selection_contract(corpus: dict[str, object]) -> None:
    selection = corpus.get("selection")
    if not isinstance(selection, dict) or selection.get("strategy") != "fixed_legal_structure":
        raise ValueError("experiment C corpus selection contract mismatch")
    sources = selection.get("sources")
    if not isinstance(sources, list) or len(sources) != len(SOURCE_SPECS):
        raise ValueError("experiment C corpus selection contract mismatch")
    for spec, metadata in zip(SOURCE_SPECS, sources, strict=True):
        if not isinstance(metadata, dict) or metadata.get("title") != spec.title:
            raise ValueError("experiment C corpus selection contract mismatch")
        if spec.selected_chapters:
            expected = [f"제{chapter}장" for chapter in spec.selected_chapters]
            if metadata.get("type") != "chapters" or metadata.get("chapters") != expected:
                raise ValueError("experiment C corpus selection contract mismatch")
        elif spec.selected_article_range is not None:
            start, end = spec.selected_article_range
            if metadata.get("type") != "article_range" or metadata.get("article_range") != [
                f"제{start}조",
                f"제{end}조",
            ]:
                raise ValueError("experiment C corpus selection contract mismatch")
        else:
            raise ValueError("experiment C corpus selection contract mismatch")
        if (
            isinstance(metadata.get("chunk_count"), bool)
            or not isinstance(metadata.get("chunk_count"), int)
            or metadata["chunk_count"] <= 0
        ):
            raise ValueError("experiment C corpus selection contract mismatch")
        validation = metadata.get("validation")
        if not isinstance(validation, dict) or validation.get("status") != "passed":
            raise ValueError("experiment C corpus validation contract mismatch")
        if not isinstance(metadata.get("hierarchy_source"), str):
            raise ValueError("experiment C corpus validation contract mismatch")
    if sum(metadata["chunk_count"] for metadata in sources) != corpus["chunk_count"]:
        raise ValueError("experiment C corpus selection contract mismatch")


def _validate_corpus_chunk_hierarchy(chunks: list[object]) -> None:
    by_document_path: dict[tuple[str, str, str], dict[str, object]] = {}
    roots_by_document: dict[tuple[str, str], set[str]] = {}
    expected_roots_by_document: dict[tuple[str, str], set[str]] = {}
    chunk_ids: set[str] = set()
    for raw_chunk in chunks:
        if not isinstance(raw_chunk, dict):
            raise ValueError("invalid experiment C chunk")
        chunk = raw_chunk
        chunk_id = chunk.get("chunk_id")
        title = chunk.get("title")
        mst = chunk.get("mst")
        path = chunk.get("path")
        content = chunk.get("content")
        required = (chunk_id, title, mst, path, content)
        if not all(isinstance(value, str) and value.strip() for value in required):
            raise ValueError("invalid experiment C chunk metadata")
        assert isinstance(chunk_id, str)
        assert isinstance(title, str)
        assert isinstance(mst, str)
        assert isinstance(path, str)
        assert isinstance(content, str)
        if chunk_id in chunk_ids:
            raise ValueError("duplicate experiment C chunk id")
        chunk_ids.add(chunk_id)
        key = (title, mst, path)
        if key in by_document_path:
            raise ValueError("duplicate experiment C provision path")
        by_document_path[key] = chunk
        article = _article_root(path)
        if article is None:
            raise ValueError("experiment C chunk path has no article root")
        document_key = (title, mst)
        expected_roots_by_document.setdefault(document_key, set()).add(article[0])
        parent = chunk.get("parent_path")
        if parent is None:
            if path != article[0] or CHAPTER_PATTERN.match(content):
                raise ValueError("invalid experiment C article root")
            roots_by_document.setdefault(document_key, set()).add(path)
        elif not isinstance(parent, str) or not parent.strip():
            raise ValueError("invalid experiment C parent path")

    for (title, mst, path), chunk in by_document_path.items():
        parent = chunk.get("parent_path")
        if parent is None:
            continue
        assert isinstance(parent, str)
        parent_chunk = by_document_path.get((title, mst, parent))
        if parent_chunk is None:
            raise ValueError("experiment C provision parent is missing")
        article = _article_root(path)
        parent_article = _article_root(parent)
        if article is None or parent_article is None or article[0] != parent_article[0]:
            raise ValueError("experiment C provision parent crosses articles")

    if roots_by_document != expected_roots_by_document:
        raise ValueError("experiment C article root is missing")


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
    validation = corpus.get("validation")
    if not isinstance(validation, dict) or validation.get("status") != "passed":
        raise ValueError("experiment C corpus validation contract mismatch")
    _validate_selection_contract(corpus)
    for chunk in corpus["chunks"]:
        if not isinstance(chunk, dict):
            raise ValueError("invalid experiment C chunk")
        _validate_vector(chunk.get("embedding"))
        for key in ("chunk_id", "title", "source_id", "mst", "path", "content"):
            if not isinstance(chunk.get(key), str) or not chunk[key].strip():
                raise ValueError("invalid experiment C chunk metadata")
    _validate_corpus_chunk_hierarchy(corpus["chunks"])
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
    candidate_k: int = DEFAULT_CANDIDATE_K,
) -> dict[str, object]:
    if not question.strip():
        raise ValueError("question must not be empty")
    if not 1 <= candidate_k <= MAX_CANDIDATE_K:
        raise ValueError(f"candidate_k must be between 1 and {MAX_CANDIDATE_K}")
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

    raw_chunk_candidates = [
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
        for rank, (score, chunk) in enumerate(scored[:candidate_k], start=1)
    ]

    grouped: dict[str, list[tuple[float, dict[str, object]]]] = {}
    for score, chunk in scored:
        article = _article_root(str(chunk["path"]))
        if article is None:
            raise ValueError("experiment C chunk path has no article root")
        article_id = f"{chunk['source_id']}:{chunk['mst']}:{article[0]}"
        grouped.setdefault(article_id, []).append((score, chunk))
    article_groups = sorted(grouped.items(), key=lambda item: (-item[1][0][0], item[0]))
    article_candidates: list[dict[str, object]] = []
    for rank, (article_id, matches) in enumerate(article_groups[:candidate_k], start=1):
        best_score, best_chunk = matches[0]
        article = _article_root(str(best_chunk["path"]))
        assert article is not None
        article_candidates.append(
            {
                "rank": rank,
                "score": best_score,
                "article_id": article_id,
                "article_path": article[0],
                "title": best_chunk["title"],
                "source_id": best_chunk["source_id"],
                "mst": best_chunk["mst"],
                "effective_from": best_chunk["effective_from"],
                "article_chunk_count": len(matches),
                "best_chunk": {
                    "score": best_score,
                    "chunk_id": best_chunk["chunk_id"],
                    "path": best_chunk["path"],
                    "heading": best_chunk["heading"],
                    "content": best_chunk["content"],
                },
                "matched_chunks": [
                    {
                        "score": match_score,
                        "chunk_id": match["chunk_id"],
                        "path": match["path"],
                        "heading": match["heading"],
                        "content": match["content"],
                    }
                    for match_score, match in matches[:ARTICLE_MATCHES_PER_CANDIDATE]
                ],
            }
        )
    return {
        "experiment": "C",
        "question": question,
        "provider": "nvidia_nim",
        "model": MODEL,
        "corpus_chunks": len(chunks),
        "candidate_k": candidate_k,
        "score": "cosine_similarity",
        "grouping": {
            "unit": "article",
            "article_score": "max_chunk_cosine",
            "matched_chunks_per_article": ARTICLE_MATCHES_PER_CANDIDATE,
        },
        "raw_chunk_candidates": raw_chunk_candidates,
        "article_candidates": article_candidates,
    }


def _load_evaluation_cases(path: Path) -> list[dict[str, object]]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValueError("experiment C evaluation questions are missing") from exc
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("invalid experiment C evaluation questions") from exc
    if (
        not isinstance(payload, dict)
        or payload.get("schema_version") != 2
        or payload.get("experiment") != "C"
        or not isinstance(payload.get("cases"), list)
        or not payload["cases"]
    ):
        raise ValueError("invalid experiment C evaluation questions")
    cases: list[dict[str, object]] = []
    seen_ids: set[str] = set()
    for case in payload["cases"]:
        if not isinstance(case, dict):
            raise ValueError("invalid experiment C evaluation questions")
        normalized: dict[str, object] = {}
        for key in (
            "id",
            "question",
            "scope",
            "expected_title",
            "expected_article_path",
        ):
            value = case.get(key)
            if not isinstance(value, str) or not value.strip():
                raise ValueError("invalid experiment C evaluation questions")
            normalized[key] = value.strip()
        required_terms = case.get("required_evidence_terms")
        if (
            not isinstance(required_terms, list)
            or not required_terms
            or any(not isinstance(term, str) or not term.strip() for term in required_terms)
        ):
            raise ValueError("invalid experiment C evaluation questions")
        normalized["required_evidence_terms"] = [term.strip() for term in required_terms]
        if normalized["scope"] not in {"in_scope", "out_of_scope"}:
            raise ValueError("invalid experiment C evaluation questions")
        if normalized["id"] in seen_ids:
            raise ValueError("duplicate experiment C evaluation case id")
        seen_ids.add(normalized["id"])
        cases.append(normalized)
    return cases


def _expected_article_rank(candidates: object, *, title: str, article_path: str) -> int | None:
    if not isinstance(candidates, list):
        return None
    for candidate in candidates:
        if (
            isinstance(candidate, dict)
            and candidate.get("title") == title
            and candidate.get("article_path") == article_path
            and isinstance(candidate.get("rank"), int)
        ):
            return int(candidate["rank"])
    return None


def _expected_raw_rank(candidates: object, *, title: str, article_path: str) -> int | None:
    if not isinstance(candidates, list):
        return None
    for candidate in candidates:
        if not isinstance(candidate, dict) or candidate.get("title") != title:
            continue
        article = _article_root(str(candidate.get("path", "")))
        if (
            article is not None
            and article[0] == article_path
            and isinstance(candidate.get("rank"), int)
        ):
            return int(candidate["rank"])
    return None


def _normalize_evidence_text(value: object) -> str:
    return re.sub(r"\s+", "", unicodedata.normalize("NFKC", str(value)))


def _article_evidence_presence(
    chunks: list[object],
    *,
    title: str,
    article_path: str,
    required_terms: list[str],
) -> tuple[bool, list[str]]:
    article_contents = [
        str(chunk["content"])
        for chunk in chunks
        if isinstance(chunk, dict)
        and chunk.get("title") == title
        and (article := _article_root(str(chunk.get("path", "")))) is not None
        and article[0] == article_path
    ]
    normalized_content = _normalize_evidence_text(" ".join(article_contents))
    missing = [
        term for term in required_terms if _normalize_evidence_text(term) not in normalized_content
    ]
    return bool(article_contents) and not missing, missing


async def evaluate_cases(
    cases: list[dict[str, object]],
    corpus: dict[str, object],
    *,
    embedder: Embedder,
    candidate_k: int = DEFAULT_CANDIDATE_K,
    generated_at: str | None = None,
    corpus_sha256: str = "test-corpus",
) -> dict[str, object]:
    if not DEFAULT_CANDIDATE_K <= candidate_k <= MAX_CANDIDATE_K:
        raise ValueError(
            f"evaluation candidate_k must be between {DEFAULT_CANDIDATE_K} and {MAX_CANDIDATE_K}"
        )
    evaluated: list[dict[str, object]] = []
    in_scope_ranks: list[int | None] = []
    in_scope_evidence_ranks: list[int | None] = []
    law_at_one_count = 0
    chunks = corpus.get("chunks")
    if not isinstance(chunks, list):
        raise ValueError("invalid experiment C corpus chunks")
    for case in cases:
        question = str(case["question"])
        expected_title = str(case["expected_title"])
        expected_article_path = str(case["expected_article_path"])
        required_terms = case["required_evidence_terms"]
        assert isinstance(required_terms, list)
        search = await search_corpus(
            question,
            corpus,
            embedder=embedder,
            candidate_k=candidate_k,
        )
        article_candidates = search["article_candidates"]
        raw_candidates = search["raw_chunk_candidates"]
        article_rank = _expected_article_rank(
            article_candidates,
            title=expected_title,
            article_path=expected_article_path,
        )
        raw_rank = _expected_raw_rank(
            raw_candidates,
            title=expected_title,
            article_path=expected_article_path,
        )
        law_at_one = bool(
            isinstance(article_candidates, list)
            and article_candidates
            and isinstance(article_candidates[0], dict)
            and article_candidates[0].get("title") == expected_title
        )
        expected_present_in_corpus = any(
            isinstance(chunk, dict)
            and chunk.get("title") == expected_title
            and (article := _article_root(str(chunk.get("path", "")))) is not None
            and article[0] == expected_article_path
            for chunk in chunks
        )
        evidence_present_in_corpus, missing_evidence_terms = _article_evidence_presence(
            chunks,
            title=expected_title,
            article_path=expected_article_path,
            required_terms=[str(term) for term in required_terms],
        )
        evidence_rank = article_rank if evidence_present_in_corpus else None
        if case["scope"] == "in_scope":
            in_scope_ranks.append(article_rank)
            in_scope_evidence_ranks.append(evidence_rank)
            law_at_one_count += int(law_at_one)
        evaluated.append(
            {
                **case,
                "law_at_1": law_at_one,
                "article_rank": article_rank,
                "raw_chunk_rank": raw_rank,
                "expected_present_in_corpus": expected_present_in_corpus,
                "evidence_present_in_corpus": evidence_present_in_corpus,
                "missing_evidence_terms": missing_evidence_terms,
                "evidence_rank": evidence_rank,
                "search": search,
            }
        )

    in_scope_count = len(in_scope_ranks)
    if in_scope_count == 0:
        raise ValueError("evaluation requires at least one in-scope case")
    metrics = {
        "in_scope_cases": in_scope_count,
        "law_at_1": law_at_one_count / in_scope_count,
        "article_recall_at_3": sum(rank is not None and rank <= 3 for rank in in_scope_ranks)
        / in_scope_count,
        "article_recall_at_5": sum(rank is not None and rank <= 5 for rank in in_scope_ranks)
        / in_scope_count,
        "article_recall_at_10": sum(rank is not None and rank <= 10 for rank in in_scope_ranks)
        / in_scope_count,
        "article_mrr": sum(0.0 if rank is None else 1.0 / rank for rank in in_scope_ranks)
        / in_scope_count,
        "evidence_recall_at_3": sum(
            rank is not None and rank <= 3 for rank in in_scope_evidence_ranks
        )
        / in_scope_count,
        "evidence_recall_at_5": sum(
            rank is not None and rank <= 5 for rank in in_scope_evidence_ranks
        )
        / in_scope_count,
        "evidence_recall_at_10": sum(
            rank is not None and rank <= 10 for rank in in_scope_evidence_ranks
        )
        / in_scope_count,
    }
    return {
        "schema_version": 1,
        "experiment": "C",
        "evaluation": "dense_article_retrieval",
        "generated_at": generated_at
        or datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "corpus_sha256": corpus_sha256,
        "provider": "nvidia_nim",
        "model": MODEL,
        "candidate_k": candidate_k,
        "metrics": metrics,
        "cases": evaluated,
    }


def _render_evaluation_report(result: dict[str, object]) -> str:
    metrics = result["metrics"]
    cases = result["cases"]
    assert isinstance(metrics, dict)
    assert isinstance(cases, list)
    lines = [
        "# 실험 C — Dense 조 단위 검색 평가",
        "",
        f"> 생성 명령: `{EVALUATE_COMMAND}`",
        f"> 기준 시점: `{result['generated_at']}`",
        f"> corpus SHA-256: `{result['corpus_sha256']}`",
        f"> 모델: `{result['model']}`",
        f"> candidate k: `{result['candidate_k']}`",
        "",
        "이 문서는 키워드 결합이나 reranker가 없는 dense-only 기준선의 실제 실행 결과다.",
        "",
        "## 지표",
        "",
        f"- Law@1: `{metrics['law_at_1']}`",
        f"- Article Recall@3: `{metrics['article_recall_at_3']}`",
        f"- Article Recall@5: `{metrics['article_recall_at_5']}`",
        f"- Article Recall@10: `{metrics['article_recall_at_10']}`",
        f"- Article MRR: `{metrics['article_mrr']}`",
        f"- Evidence Recall@3: `{metrics['evidence_recall_at_3']}`",
        f"- Evidence Recall@5: `{metrics['evidence_recall_at_5']}`",
        f"- Evidence Recall@10: `{metrics['evidence_recall_at_10']}`",
        "",
        "## 질문별 결과",
        "",
        "| ID | 범위 | 기대 법률·조 | Law@1 | 조 rank | 근거 rank | raw rank |",
        "| --- | --- | --- | --- | ---: | ---: | ---: |",
    ]
    for case in cases:
        assert isinstance(case, dict)
        lines.append(
            f"| {case['id']} | {case['scope']} | "
            f"{case['expected_title']} {case['expected_article_path']} | "
            f"{case['law_at_1']} | {case['article_rank'] or '-'} | "
            f"{case['evidence_rank'] or '-'} | "
            f"{case['raw_chunk_rank'] or '-'} |"
        )
    lines.extend(["", "## 실제 후보", ""])
    for case in cases:
        assert isinstance(case, dict)
        search = case["search"]
        assert isinstance(search, dict)
        lines.extend(
            [
                f"### {case['id']}",
                "",
                f"질문: {case['question']}",
                "",
            ]
        )
        article_candidates = search["article_candidates"]
        assert isinstance(article_candidates, list)
        for candidate in article_candidates:
            assert isinstance(candidate, dict)
            best = candidate["best_chunk"]
            assert isinstance(best, dict)
            lines.extend(
                [
                    f"#### {candidate['rank']}. {candidate['title']} "
                    f"{candidate['article_path']} — {candidate['score']}",
                    "",
                    f"최고 청크: `{best['path']}`",
                    "",
                    "```text",
                    str(best["content"]),
                    "```",
                    "",
                ]
            )
    return "\n".join(lines)


def save_evaluation_result(
    result: dict[str, object], *, json_path: Path, report_path: Path
) -> None:
    json_output = json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    report = _render_evaluation_report(result)
    _atomic_write_many([(json_path, json_output), (report_path, report)])


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
    selection = corpus["selection"]
    assert isinstance(selection, dict)
    selected_sources = selection["sources"]
    assert isinstance(selected_sources, list)
    return {
        "status": "ready",
        "experiment": "C",
        "corpus_path": str(path),
        "source_count": corpus["source_count"],
        "chunk_count": corpus["chunk_count"],
        "model": MODEL,
        "dimensions": DIMENSIONS,
        "sources": selected_sources,
    }


async def _ask(path: Path, question: str, *, candidate_k: int) -> dict[str, object]:
    _, api_settings = _settings()
    corpus = load_corpus(path)
    return await search_corpus(
        question,
        corpus,
        embedder=_query_embedder(api_settings),
        candidate_k=candidate_k,
    )


async def _evaluate(
    path: Path,
    questions_path: Path,
    *,
    candidate_k: int,
    json_path: Path,
    report_path: Path,
) -> dict[str, object]:
    _, api_settings = _settings()
    corpus = load_corpus(path)
    cases = _load_evaluation_cases(questions_path)
    try:
        corpus_bytes = await asyncio.to_thread(path.read_bytes)
        corpus_sha256 = hashlib.sha256(corpus_bytes).hexdigest()
    except OSError as exc:
        raise ValueError("experiment C corpus could not be hashed") from exc
    result = await evaluate_cases(
        cases,
        corpus,
        embedder=_query_embedder(api_settings),
        candidate_k=candidate_k,
        corpus_sha256=corpus_sha256,
    )
    result["questions_path"] = _display_path(questions_path)
    result["outputs"] = {
        "json": _display_path(json_path),
        "report": _display_path(report_path),
    }
    save_evaluation_result(result, json_path=json_path, report_path=report_path)
    return result


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
            stdout = json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
        elif args.command == "ask":
            question = args.question if args.question is not None else input("질문> ")
            result = asyncio.run(_ask(args.corpus, question, candidate_k=args.candidate_k))
            stdout = (
                json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
                if args.no_record
                else record_search_result(
                    result,
                    corpus_path=args.corpus,
                    data_path=args.results_data,
                    report_path=args.results_report,
                )
            )
        else:
            result = asyncio.run(
                _evaluate(
                    args.corpus,
                    args.questions,
                    candidate_k=args.candidate_k,
                    json_path=args.json_output,
                    report_path=args.report,
                )
            )
            stdout = json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    except ResultRecordingError:
        print(_safe_error("result_recording_failed"), file=sys.stderr)
        return 2
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
    sys.stdout.write(stdout)
    return 0


def main() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8")
    raise SystemExit(run_cli())


if __name__ == "__main__":
    main()
