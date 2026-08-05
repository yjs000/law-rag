"""Run the non-gold Experiment D-10 retrieval and context diagnostic."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import re
import shutil
import struct
import subprocess
import sys
from collections.abc import Callable, Mapping, Sequence
from contextlib import suppress
from dataclasses import dataclass
from datetime import UTC, date, datetime
from math import fsum, isfinite, sqrt
from pathlib import Path
from typing import Protocol
from uuid import uuid4

from law_rag_core.corpus_update_bundle import canonical_corpus_snapshot_id
from law_rag_core.domain.identifiers import PARSER_SCHEMA_VERSION

from app.adapters.nvidia_nim_embedder import NvidiaNimEmbedder
from app.domain.corpus_temporal_contract import korea_today
from app.domain.embedding_profiles import NVIDIA_NEMOTRON_512_PROFILE
from app.settings import Settings, get_settings
from scripts.evaluate_experiment_d_gold import (
    CorpusSnapshot,
    DenseCandidate,
    ExperimentDBackend,
    GoldRunError,
    PostgresExperimentDBackend,
    _validate_retrieval_state,
)
from scripts.experiment_d_corpus import SourceProvision
from scripts.experiment_d_manual_review_contract import (
    DEFAULT_APPROVAL_MANIFEST,
    DEFAULT_QUESTION_INPUT,
    DEFAULT_SOURCE_BANK,
    ManualPilotArtifacts,
    ManualPilotQuestion,
    load_manual_pilot_artifacts,
)
from scripts.preflight_experiment_d_gold import eligible_population_fingerprint_sha256

REPOSITORY_ROOT = Path(__file__).parents[3]
DEFAULT_DATA_ROOT = REPOSITORY_ROOT / ".data" / "experiments" / "d-manual"
DEFAULT_OUTPUT_DIR = DEFAULT_DATA_ROOT / "runs"
DEFAULT_QUERY_CACHE = DEFAULT_DATA_ROOT / "query-vector-cache.json"
SEARCH_LIMIT_WITH_TIE_SENTINEL = 11
ARTICLE_PATH_PATTERN = re.compile(r"^(제(?:\d+)조(?:의(?:\d+))?)(?:/|$)")
CRITICAL_CODE_PATHS = (
    Path("experiments/d_manual/experiment-d-10-questions.json"),
    Path("apps/api/scripts/experiment_d_manual_review.py"),
    Path("apps/api/scripts/experiment_d_manual_review_contract.py"),
    Path("apps/api/scripts/evaluate_experiment_d_gold.py"),
    Path("apps/api/scripts/experiment_d_corpus.py"),
    Path("apps/api/scripts/preflight_experiment_d_gold.py"),
    Path("apps/api/app/adapters/postgres_repository.py"),
    Path("apps/api/app/adapters/nvidia_nim_embedder.py"),
    Path("apps/api/app/domain/embedding_profiles.py"),
    Path("packages/law-rag-core/src/law_rag_core/persistence.py"),
    Path("packages/law-rag-core/src/law_rag_core/corpus_update_bundle.py"),
    Path("apps/api/pyproject.toml"),
    Path("pyproject.toml"),
    Path("uv.lock"),
)


class ManualRunError(RuntimeError):
    def __init__(
        self,
        code: str,
        *,
        details: Mapping[str, object] | None = None,
    ) -> None:
        super().__init__(code)
        self.code = code
        self.details = dict(details or {})


class QueryEmbedder(Protocol):
    async def embed(self, texts: list[str]) -> list[list[float]]: ...


@dataclass(frozen=True, slots=True)
class CurrentPopulation:
    as_of_date: date
    provisions: tuple[SourceProvision, ...]
    fingerprint_sha256: str
    snapshot_id: str

    @property
    def count(self) -> int:
        return len(self.provisions)


@dataclass(frozen=True, slots=True)
class PublishedManualRun:
    directory: Path
    json_path: Path
    markdown_path: Path
    json_sha256: str
    markdown_sha256: str
    stdout: str
    payload: dict[str, object]


def _sha256(encoded: bytes) -> str:
    return hashlib.sha256(encoded).hexdigest()


def _canonical_json_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _iso_utc(value: datetime) -> str:
    if value.tzinfo is None:
        raise ManualRunError("run_timestamp_must_include_timezone")
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _is_effective_at(provision: SourceProvision, as_of_date: date) -> bool:
    return provision.effective_from <= as_of_date and (
        provision.effective_to is None or as_of_date < provision.effective_to
    )


def _validate_snapshot(stage: str, snapshot: CorpusSnapshot, as_of_date: date) -> CurrentPopulation:
    if not snapshot.status.ready:
        raise ManualRunError(
            f"{stage}_corpus_unready",
            details={"reason": snapshot.status.reason},
        )
    try:
        _validate_retrieval_state(stage, snapshot)
    except GoldRunError as error:
        raise ManualRunError(error.code, details=error.details) from error
    eligible = tuple(
        provision
        for provision in snapshot.provisions
        if _is_effective_at(provision, as_of_date)
    )
    if not eligible:
        raise ManualRunError(f"{stage}_current_population_empty")
    fingerprint = eligible_population_fingerprint_sha256(eligible)
    snapshot_id = canonical_corpus_snapshot_id(
        parser_contract_version=PARSER_SCHEMA_VERSION,
        retrieval_unit="provision",
        content_populations=[
            {
                "eligible_provision_count": len(eligible),
                "fingerprint_sha256": fingerprint,
            }
        ],
    )
    return CurrentPopulation(
        as_of_date=as_of_date,
        provisions=eligible,
        fingerprint_sha256=fingerprint,
        snapshot_id=snapshot_id,
    )


def _retrieval_identity(snapshot: CorpusSnapshot) -> dict[str, object]:
    state = snapshot.retrieval_state
    return {
        "profile": state.profile,
        "vector_count": state.vector_count,
        "non_unit_vector_count": state.non_unit_vector_count,
        "vector_fingerprint_sha256": state.vector_fingerprint_sha256,
        "pgvector_version": state.pgvector_version,
    }


def _validate_same_locked_state(
    initial_snapshot: CorpusSnapshot,
    initial_population: CurrentPopulation,
    locked_snapshot: CorpusSnapshot,
    locked_population: CurrentPopulation,
) -> None:
    if (
        initial_population.snapshot_id != locked_population.snapshot_id
        or initial_population.fingerprint_sha256 != locked_population.fingerprint_sha256
        or initial_population.count != locked_population.count
    ):
        raise ManualRunError("corpus_changed_after_query_embedding")
    if _retrieval_identity(initial_snapshot) != _retrieval_identity(locked_snapshot):
        raise ManualRunError("retrieval_profile_changed_after_query_embedding")


def _validate_query_vector(vector: Sequence[float]) -> list[float]:
    dimensions = NVIDIA_NEMOTRON_512_PROFILE.stored_dimensions
    if len(vector) != dimensions:
        raise ManualRunError(
            "query_embedding_dimension_mismatch",
            details={"expected": dimensions, "actual": len(vector)},
        )
    normalized: list[float] = []
    for component in vector:
        if (
            isinstance(component, bool)
            or not isinstance(component, int | float)
            or not isfinite(component)
        ):
            raise ManualRunError("query_embedding_nonfinite")
        normalized.append(float(component))
    norm = sqrt(fsum(component * component for component in normalized))
    if abs(norm - 1.0) > 0.0001:
        raise ManualRunError("query_embedding_not_l2_normalized", details={"norm": norm})
    return normalized


def _embedding_sha256(vector: Sequence[float]) -> str:
    return _sha256(struct.pack(f"<{len(vector)}d", *vector))


def _cache_key(
    *,
    question_sha256: str,
    profile_key: str,
    corpus_snapshot_id: str,
) -> str:
    return _sha256(
        _canonical_json_bytes(
            {
                "question_sha256": question_sha256,
                "profile_key": profile_key,
                "corpus_snapshot_id": corpus_snapshot_id,
            }
        )
    )


def _load_query_cache(path: Path) -> dict[str, dict[str, object]]:
    if not path.exists():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ManualRunError("query_cache_unreadable") from error
    if not isinstance(value, dict) or value.get("schema_version") != 1:
        raise ManualRunError("query_cache_contract_invalid")
    raw_records = value.get("records")
    if not isinstance(raw_records, list):
        raise ManualRunError("query_cache_contract_invalid")
    records: dict[str, dict[str, object]] = {}
    for raw in raw_records:
        if not isinstance(raw, dict) or set(raw) != {
            "cache_key",
            "question_id",
            "question_sha256",
            "profile_key",
            "corpus_snapshot_id",
            "vector_sha256",
            "vector",
        }:
            raise ManualRunError("query_cache_record_invalid")
        key = raw.get("cache_key")
        if not isinstance(key, str) or key in records:
            raise ManualRunError("query_cache_duplicate_or_invalid_key")
        expected_key = _cache_key(
            question_sha256=str(raw.get("question_sha256")),
            profile_key=str(raw.get("profile_key")),
            corpus_snapshot_id=str(raw.get("corpus_snapshot_id")),
        )
        if key != expected_key:
            raise ManualRunError("query_cache_key_mismatch")
        vector_value = raw.get("vector")
        if not isinstance(vector_value, list):
            raise ManualRunError("query_cache_vector_invalid")
        vector = _validate_query_vector(vector_value)
        if raw.get("vector_sha256") != _embedding_sha256(vector):
            raise ManualRunError("query_cache_vector_sha256_mismatch")
        records[key] = {**raw, "vector": vector}
    return records


def _atomic_write_query_cache(path: Path, records: Mapping[str, Mapping[str, object]]) -> None:
    payload = {
        "schema_version": 1,
        "records": [records[key] for key in sorted(records)],
    }
    encoded = (
        json.dumps(payload, ensure_ascii=False, allow_nan=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.parent / f".{path.name}.{uuid4().hex}.tmp"
    try:
        with temporary.open("xb") as stream:
            stream.write(encoded)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        with suppress(OSError):
            temporary.unlink(missing_ok=True)


def _cache_file_sha256(path: Path) -> str:
    return _sha256(path.read_bytes()) if path.exists() else _sha256(b"")


async def _query_vectors(
    questions: Sequence[ManualPilotQuestion],
    *,
    profile_key: str,
    corpus_snapshot_id: str,
    cache_path: Path,
    embedder_factory: Callable[[], QueryEmbedder],
) -> tuple[list[list[float]], int, int, str]:
    records = _load_query_cache(cache_path)
    vectors_by_id: dict[str, list[float]] = {}
    missing: list[ManualPilotQuestion] = []
    for question in questions:
        key = _cache_key(
            question_sha256=question.question_sha256,
            profile_key=profile_key,
            corpus_snapshot_id=corpus_snapshot_id,
        )
        cached = records.get(key)
        if cached is None:
            missing.append(question)
        else:
            vectors_by_id[question.id] = list(cached["vector"])

    if len(missing) > 10:
        raise ManualRunError("query_embedding_cost_bound_exceeded")
    if missing:
        embedded = await embedder_factory().embed([question.question for question in missing])
        if len(embedded) != len(missing):
            raise ManualRunError(
                "query_embedding_batch_count_mismatch",
                details={"expected": len(missing), "actual": len(embedded)},
            )
        for question, raw_vector in zip(missing, embedded, strict=True):
            vector = _validate_query_vector(raw_vector)
            key = _cache_key(
                question_sha256=question.question_sha256,
                profile_key=profile_key,
                corpus_snapshot_id=corpus_snapshot_id,
            )
            record: dict[str, object] = {
                "cache_key": key,
                "question_id": question.id,
                "question_sha256": question.question_sha256,
                "profile_key": profile_key,
                "corpus_snapshot_id": corpus_snapshot_id,
                "vector_sha256": _embedding_sha256(vector),
                "vector": vector,
            }
            records[key] = record
            vectors_by_id[question.id] = vector
        _atomic_write_query_cache(cache_path, records)

    ordered = [vectors_by_id[question.id] for question in questions]
    cache_file_sha256 = await asyncio.to_thread(_cache_file_sha256, cache_path)
    return ordered, len(questions) - len(missing), len(missing), cache_file_sha256


def _validate_dense_candidates(candidates: Sequence[DenseCandidate]) -> tuple[DenseCandidate, ...]:
    if len(candidates) != SEARCH_LIMIT_WITH_TIE_SENTINEL:
        raise ManualRunError(
            "dense_search_candidate_count_mismatch",
            details={
                "expected": SEARCH_LIMIT_WITH_TIE_SENTINEL,
                "actual": len(candidates),
            },
        )
    seen: set[str] = set()
    previous: DenseCandidate | None = None
    for candidate in candidates:
        if not candidate.provision_id or candidate.provision_id in seen:
            raise ManualRunError("dense_search_duplicate_provision_id")
        if not isfinite(candidate.score):
            raise ManualRunError("dense_search_nonfinite_score")
        if previous is not None and (
            candidate.score > previous.score
            or (
                candidate.score == previous.score
                and candidate.provision_id < previous.provision_id
            )
        ):
            raise ManualRunError("dense_search_order_contract_violated")
        seen.add(candidate.provision_id)
        previous = candidate
    if len(candidates) == SEARCH_LIMIT_WITH_TIE_SENTINEL and (
        candidates[9].score == candidates[10].score
    ):
        raise ManualRunError(
            "unresolved_cutoff_tie",
            details={
                "rank_10_provision_id": candidates[9].provision_id,
                "rank_11_provision_id": candidates[10].provision_id,
                "score": candidates[9].score,
            },
        )
    return tuple(candidates[:10])


def _article_root(path: str) -> str:
    match = ARTICLE_PATH_PATTERN.match(path)
    if match is None:
        raise ManualRunError("candidate_path_has_no_article_root", details={"path": path})
    return match.group(1)


def _raw_candidate_record(
    rank: int,
    candidate: DenseCandidate,
    source: SourceProvision,
) -> dict[str, object]:
    return {
        "rank": rank,
        "provision_id": candidate.provision_id,
        "document_id": candidate.document_id,
        "version_id": source.version_id,
        "document_title": candidate.document_title,
        "source_kind": candidate.source_kind,
        "mst": source.mst,
        "version_label": candidate.version_label,
        "effective_from": (
            candidate.effective_from.isoformat() if candidate.effective_from else None
        ),
        "effective_to": candidate.effective_to.isoformat() if candidate.effective_to else None,
        "path": candidate.path,
        "parent_path": source.parent_path,
        "heading": candidate.heading,
        "content": candidate.content,
        "content_sha256": source.content_sha256,
        "source_url": candidate.source_url,
        "raw_cosine_similarity": candidate.score,
    }


def _article_contexts(
    raw_candidates: Sequence[DenseCandidate],
    population: CurrentPopulation,
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    by_id = {provision.provision_id: provision for provision in population.provisions}
    raw_records: list[dict[str, object]] = []
    grouped: dict[tuple[str, str, str], dict[str, object]] = {}
    for rank, candidate in enumerate(raw_candidates, 1):
        source = by_id.get(candidate.provision_id)
        if source is None:
            raise ManualRunError(
                "dense_candidate_missing_from_locked_population",
                details={"provision_id": candidate.provision_id},
            )
        raw_records.append(_raw_candidate_record(rank, candidate, source))
        root = _article_root(source.path)
        key = (source.document_id, source.version_id, root)
        group = grouped.setdefault(
            key,
            {
                "article_id": f"{source.document_id}:{source.version_id}:{root}",
                "document_id": source.document_id,
                "version_id": source.version_id,
                "document_title": source.document_title,
                "source_kind": source.source_kind,
                "mst": source.mst,
                "effective_from": source.effective_from.isoformat(),
                "effective_to": source.effective_to.isoformat() if source.effective_to else None,
                "source_url": source.source_url,
                "article_path": root,
                "best_raw_rank": rank,
                "best_raw_score": candidate.score,
                "matched_raw_ranks": [],
                "matched_raw_provision_ids": [],
            },
        )
        group["matched_raw_ranks"].append(rank)
        group["matched_raw_provision_ids"].append(source.provision_id)

    contexts: list[dict[str, object]] = []
    for key, group in sorted(grouped.items(), key=lambda item: int(item[1]["best_raw_rank"])):
        document_id, version_id, root = key
        nodes = [
            provision
            for provision in population.provisions
            if provision.document_id == document_id
            and provision.version_id == version_id
            and _article_root(provision.path) == root
        ]
        nodes.sort(key=lambda item: (item.ordinal, item.path, item.provision_id))
        paths = {node.path for node in nodes}
        if root not in paths:
            raise ManualRunError("article_context_root_missing", details={"article_path": root})
        for node in nodes:
            if node.parent_path is not None and node.parent_path not in paths:
                raise ManualRunError(
                    "article_context_parent_missing",
                    details={"path": node.path, "parent_path": node.parent_path},
                )
        contexts.append(
            {
                **group,
                "context_provision_count": len(nodes),
                "provisions": [
                    {
                        "provision_id": node.provision_id,
                        "path": node.path,
                        "parent_path": node.parent_path,
                        "heading": node.heading,
                        "content": node.content,
                        "content_sha256": node.content_sha256,
                        "ordinal": node.ordinal,
                    }
                    for node in nodes
                ],
            }
        )
    return raw_records, contexts


def _code_provenance() -> dict[str, object]:
    try:
        commit = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=REPOSITORY_ROOT,
            check=True,
            capture_output=True,
            text=True,
            timeout=5,
        ).stdout.strip()
        status = subprocess.run(
            [
                "git",
                "status",
                "--porcelain=v1",
                "--",
                *(path.as_posix() for path in CRITICAL_CODE_PATHS),
            ],
            cwd=REPOSITORY_ROOT,
            check=True,
            capture_output=True,
            text=True,
            timeout=5,
        ).stdout.splitlines()
    except OSError, subprocess.SubprocessError:
        raise ManualRunError("code_provenance_unavailable") from None
    if not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise ManualRunError("code_revision_invalid")
    dirty = [line for line in status if line.strip()]
    if dirty:
        raise ManualRunError("critical_code_worktree_dirty", details={"status": dirty})
    hashes: dict[str, str] = {}
    for relative in CRITICAL_CODE_PATHS:
        try:
            hashes[relative.as_posix()] = _sha256((REPOSITORY_ROOT / relative).read_bytes())
        except OSError as error:
            raise ManualRunError(
                "critical_code_file_unreadable",
                details={"path": relative.as_posix()},
            ) from error
    return {
        "git_commit": commit,
        "critical_code_dirty": False,
        "critical_file_sha256": hashes,
    }


def _validate_code_provenance(value: Mapping[str, object]) -> dict[str, object]:
    if set(value) != {"git_commit", "critical_code_dirty", "critical_file_sha256"}:
        raise ManualRunError("code_provenance_contract_invalid")
    commit = value.get("git_commit")
    if not isinstance(commit, str) or not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise ManualRunError("code_revision_invalid")
    if value.get("critical_code_dirty") is not False:
        raise ManualRunError("critical_code_worktree_dirty")
    hashes = value.get("critical_file_sha256")
    if not isinstance(hashes, Mapping):
        raise ManualRunError("critical_code_hash_contract_invalid")
    if any(
        not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest)
        for digest in hashes.values()
    ):
        raise ManualRunError("critical_code_hash_invalid")
    return {
        "git_commit": commit,
        "critical_code_dirty": False,
        "critical_file_sha256": dict(hashes),
    }


def _stdout_payload(
    *,
    run_id: str,
    final_directory: Path,
    population: CurrentPopulation,
    cache_hit_count: int,
    cache_miss_count: int,
) -> dict[str, object]:
    return {
        "status": "retrieval_completed_awaiting_manual_review",
        "experiment": "D-10",
        "run_id": run_id,
        "result_directory": str(final_directory.resolve()),
        "result_json": str((final_directory / "result.json").resolve()),
        "review_markdown": str((final_directory / "review.md").resolve()),
        "case_count": 10,
        "as_of_date": population.as_of_date.isoformat(),
        "corpus_snapshot_id": population.snapshot_id,
        "embedding_profile_key": NVIDIA_NEMOTRON_512_PROFILE.key,
        "query_cache_hit_count": cache_hit_count,
        "query_cache_miss_count": cache_miss_count,
        "manual_review_status": "pending",
    }


def _markdown_escape(value: object) -> str:
    return str(value).replace("|", "\\|").replace("\r", " ").replace("\n", " ")


def _render_markdown(payload: Mapping[str, object]) -> str:
    inputs = payload["inputs"]
    assert isinstance(inputs, Mapping)
    lines = [
        "# 실험 D-10 수동 검토",
        "",
        f"- run: `{payload['run_id']}`",
        f"- 상태: `{payload['status']}`",
        f"- 기준일: `{inputs['as_of_date']}`",
        f"- corpus snapshot: `{inputs['corpus_snapshot_id']}`",
        f"- 검색 provision: `{inputs['eligible_provision_count']}`",
        f"- embedding profile: `{inputs['embedding_profile_key']}`",
        f"- stdout SHA-256: `{payload['stdout_sha256']}`",
        "",
        "> 이 문서는 정답 없는 수동 진단 초안이다. 사용자 확인 전에는 Recall 또는 "
        "확정 결과가 아니다.",
        "",
    ]
    cases = payload["cases"]
    assert isinstance(cases, list)
    for index, case in enumerate(cases, 1):
        assert isinstance(case, Mapping)
        lines.extend(
            [
                f"## {index}. {case['case_id']}",
                "",
                str(case["question"]),
                "",
                "### Raw top 10",
                "",
                "| 순위 | 점수 | 법령 | 경로 | provision ID |",
                "|---:|---:|---|---|---|",
            ]
        )
        raw_candidates = case["raw_candidates"]
        assert isinstance(raw_candidates, list)
        for candidate in raw_candidates:
            assert isinstance(candidate, Mapping)
            lines.append(
                "| {rank} | {score:.12f} | {title} | {path} | `{provision_id}` |".format(
                    rank=candidate["rank"],
                    score=float(candidate["raw_cosine_similarity"]),
                    title=_markdown_escape(candidate["document_title"]),
                    path=_markdown_escape(candidate["path"]),
                    provision_id=candidate["provision_id"],
                )
            )
        lines.extend(["", "### Raw 원문", ""])
        for candidate in raw_candidates:
            assert isinstance(candidate, Mapping)
            lines.extend(
                [
                    f"#### {candidate['rank']}위 — {candidate['document_title']} "
                    f"{candidate['path']}",
                    "",
                    str(candidate["content"]),
                    "",
                ]
            )
        lines.extend(["### 조문 단위 복원 문맥", ""])
        article_contexts = case["article_contexts"]
        assert isinstance(article_contexts, list)
        for context in article_contexts:
            assert isinstance(context, Mapping)
            lines.extend(
                [
                    f"#### raw {context['best_raw_rank']}위 — {context['document_title']} "
                    f"{context['article_path']}",
                    "",
                ]
            )
            provisions = context["provisions"]
            assert isinstance(provisions, list)
            for provision in provisions:
                assert isinstance(provision, Mapping)
                heading = f" ({provision['heading']})" if provision.get("heading") else ""
                lines.extend(
                    [
                        f"- `{provision['path']}`{heading} — `{provision['provision_id']}`",
                        "",
                        str(provision["content"]),
                        "",
                    ]
                )
        lines.extend(
            [
                "### Codex 1차 검토 / 사용자 최종 확인",
                "",
                "- 직접 근거 provision과 순위: `미작성`",
                "- 판정: `미작성`",
                "- 이유와 누락 답변 요소: `미작성`",
                "- 문맥 판정: `미작성`",
                "- top 5 무관 후보: `미작성`",
                "- 사용자 확인: `보류`",
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def _atomic_publish_run(
    output_dir: Path,
    run_id: str,
    payload: dict[str, object],
) -> tuple[Path, Path, Path, str, str]:
    final_directory = output_dir / run_id
    temporary_directory = output_dir / f".{run_id}.{uuid4().hex}.tmp"
    if final_directory.exists():
        raise ManualRunError("result_run_id_already_exists")
    output_dir.mkdir(parents=True, exist_ok=True)
    temporary_directory.mkdir()
    try:
        json_encoded = (
            json.dumps(payload, ensure_ascii=False, allow_nan=False, indent=2, sort_keys=True)
            + "\n"
        ).encode("utf-8")
        markdown_encoded = _render_markdown(payload).encode("utf-8")
        for name, encoded in (("result.json", json_encoded), ("review.md", markdown_encoded)):
            with (temporary_directory / name).open("xb") as stream:
                stream.write(encoded)
                stream.flush()
                os.fsync(stream.fileno())
        try:
            os.rename(temporary_directory, final_directory)
        except FileExistsError as error:
            raise ManualRunError("result_run_id_already_exists") from error
        with suppress(OSError):
            directory_descriptor = os.open(output_dir, os.O_RDONLY)
            try:
                os.fsync(directory_descriptor)
            finally:
                os.close(directory_descriptor)
    finally:
        if temporary_directory.exists():
            shutil.rmtree(temporary_directory)
    return (
        final_directory,
        final_directory / "result.json",
        final_directory / "review.md",
        _sha256(json_encoded),
        _sha256(markdown_encoded),
    )


async def run_manual_retrieval(
    artifacts: ManualPilotArtifacts,
    backend: ExperimentDBackend,
    embedder_factory: Callable[[], QueryEmbedder],
    *,
    output_dir: Path,
    cache_path: Path,
    code_provenance: Mapping[str, object],
    as_of_date: date,
    run_id: str,
    started_at: datetime,
    completed_at_factory: Callable[[], datetime],
) -> PublishedManualRun:
    if len(artifacts.questions) != 10:
        raise ManualRunError("manual_pilot_question_count_mismatch")
    if not re.fullmatch(r"[a-z0-9_-]+", run_id):
        raise ManualRunError("invalid_run_id")
    validated_code_provenance = _validate_code_provenance(code_provenance)
    initial_snapshot = await backend.snapshot()
    initial_population = _validate_snapshot("initial", initial_snapshot, as_of_date)
    vectors, cache_hits, cache_misses, cache_file_sha256 = await _query_vectors(
        artifacts.questions,
        profile_key=NVIDIA_NEMOTRON_512_PROFILE.key,
        corpus_snapshot_id=initial_population.snapshot_id,
        cache_path=cache_path,
        embedder_factory=embedder_factory,
    )

    case_records: list[dict[str, object]] = []
    async with backend.locked_reader() as reader:
        locked_snapshot = await reader.snapshot()
        locked_population = _validate_snapshot("locked", locked_snapshot, as_of_date)
        _validate_same_locked_state(
            initial_snapshot,
            initial_population,
            locked_snapshot,
            locked_population,
        )
        for question, vector in zip(artifacts.questions, vectors, strict=True):
            raw_candidates = _validate_dense_candidates(
                await reader.search(
                    as_of_date=as_of_date,
                    query_embedding=vector,
                    limit=SEARCH_LIMIT_WITH_TIE_SENTINEL,
                )
            )
            raw_records, article_contexts = _article_contexts(
                raw_candidates,
                locked_population,
            )
            case_records.append(
                {
                    "case_id": question.id,
                    "question": question.question,
                    "question_sha256": question.question_sha256,
                    "question_scope_sha256": question.question_scope_sha256,
                    "query_embedding_sha256": _embedding_sha256(vector),
                    "raw_candidates": raw_records,
                    "article_contexts": article_contexts,
                    "manual_review": {
                        "status": "pending",
                        "assistant_review": None,
                        "user_confirmation": "on_hold",
                    },
                }
            )

    final_directory = output_dir / run_id
    stdout_payload = _stdout_payload(
        run_id=run_id,
        final_directory=final_directory,
        population=locked_population,
        cache_hit_count=cache_hits,
        cache_miss_count=cache_misses,
    )
    stdout = json.dumps(stdout_payload, ensure_ascii=False, allow_nan=False, indent=2) + "\n"
    completed_at = completed_at_factory()
    payload: dict[str, object] = {
        "schema_version": 1,
        "experiment": "D-10",
        "artifact_class": "not_gold",
        "status": "retrieval_completed_awaiting_manual_review",
        "run_id": run_id,
        "started_at": _iso_utc(started_at),
        "completed_at": _iso_utc(completed_at),
        "inputs": {
            "question_input_sha256": artifacts.question_input_sha256,
            "source_bank_file_sha256": artifacts.source_bank_file_sha256,
            "approval_manifest_file_sha256": artifacts.approval_manifest_file_sha256,
            "approval_manifest_payload_sha256": artifacts.approval_manifest_payload_sha256,
            "as_of_date": as_of_date.isoformat(),
            "corpus_snapshot_id": locked_population.snapshot_id,
            "corpus_population_fingerprint_sha256": locked_population.fingerprint_sha256,
            "eligible_provision_count": locked_population.count,
            "embedding_profile_key": NVIDIA_NEMOTRON_512_PROFILE.key,
            "retrieval_execution_mode": "exhaustive_exact_cosine",
            "raw_candidate_limit": 10,
            "tie_sentinel_limit": SEARCH_LIMIT_WITH_TIE_SENTINEL,
            "query_cache_path": str(cache_path),
            "query_cache_file_sha256": cache_file_sha256,
            "query_cache_hit_count": cache_hits,
            "query_cache_miss_count": cache_misses,
            "query_embedding_request_count": 1 if cache_misses else 0,
            "query_embedding_input_count": cache_misses,
            "retrieval_state": locked_snapshot.retrieval_state.to_dict(),
            "code_provenance": validated_code_provenance,
        },
        "stdout_sha256": _sha256(stdout.encode("utf-8")),
        "case_count": len(case_records),
        "cases": case_records,
        "diagnostics": {
            "status": "not_computed_pending_user_confirmation",
            "is_gold_metric": False,
        },
    }
    payload["payload_without_self_hash_sha256"] = _sha256(_canonical_json_bytes(payload))
    directory, json_path, markdown_path, json_sha, markdown_sha = _atomic_publish_run(
        output_dir,
        run_id,
        payload,
    )
    return PublishedManualRun(
        directory=directory,
        json_path=json_path,
        markdown_path=markdown_path,
        json_sha256=json_sha,
        markdown_sha256=markdown_sha,
        stdout=stdout,
        payload=payload,
    )


def _embedder_factory(settings: Settings) -> QueryEmbedder:
    if not settings.nvidia_api_key:
        raise ManualRunError("nvidia_api_key_required")
    return NvidiaNimEmbedder(
        api_key=settings.nvidia_api_key,
        base_url=settings.nvidia_base_url,
        model=settings.nvidia_embedding_model,
        dimensions=settings.embedding_dimensions,
        timeout_seconds=settings.embedding_timeout_seconds,
        input_type=NVIDIA_NEMOTRON_512_PROFILE.query_input_type,
    )


def _arguments(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Experiment D-10 manual retrieval diagnostic")
    subparsers = parser.add_subparsers(dest="command", required=True)
    validate = subparsers.add_parser("validate-input")
    run = subparsers.add_parser("run")
    for command in (validate, run):
        command.add_argument("--questions", type=Path, default=DEFAULT_QUESTION_INPUT)
        command.add_argument("--source-bank", type=Path, default=DEFAULT_SOURCE_BANK)
        command.add_argument("--approval-manifest", type=Path, default=DEFAULT_APPROVAL_MANIFEST)
    run.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    run.add_argument("--query-cache", type=Path, default=DEFAULT_QUERY_CACHE)
    return parser.parse_args(argv)


async def _run_command(arguments: argparse.Namespace) -> PublishedManualRun:
    settings = get_settings()
    if not settings.direct_url:
        raise ManualRunError("direct_url_required")
    artifacts = load_manual_pilot_artifacts(
        arguments.questions,
        arguments.source_bank,
        arguments.approval_manifest,
    )
    started_at = datetime.now(UTC)
    run_id = f"d10-{started_at.strftime('%Y%m%dT%H%M%S%fZ')}-{uuid4().hex[:12]}"
    backend = PostgresExperimentDBackend(settings.direct_url)
    try:
        return await run_manual_retrieval(
            artifacts,
            backend,
            lambda: _embedder_factory(settings),
            output_dir=arguments.output_dir,
            cache_path=arguments.query_cache,
            code_provenance=_code_provenance(),
            as_of_date=korea_today(),
            run_id=run_id,
            started_at=started_at,
            completed_at_factory=lambda: datetime.now(UTC),
        )
    finally:
        await backend.close()


def _error_payload(error: BaseException) -> dict[str, object]:
    if isinstance(error, ManualRunError):
        return {
            "status": "failed",
            "error_code": error.code,
            "details": error.details,
            "result_written": False,
        }
    return {
        "status": "failed",
        "error_code": "experiment_d10_run_failed",
        "error_type": type(error).__name__,
        "result_written": False,
    }


def main(argv: Sequence[str] | None = None) -> int:
    arguments = _arguments(argv)
    if arguments.command == "validate-input":
        artifacts = load_manual_pilot_artifacts(
            arguments.questions,
            arguments.source_bank,
            arguments.approval_manifest,
        )
        print(
            json.dumps(
                {
                    "status": "valid",
                    "experiment": "D-10",
                    "artifact_class": "not_gold",
                    "question_count": len(artifacts.questions),
                    "question_ids": [question.id for question in artifacts.questions],
                    "question_input_sha256": artifacts.question_input_sha256,
                    "approval_manifest_payload_sha256": (
                        artifacts.approval_manifest_payload_sha256
                    ),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0
    try:
        published = asyncio.run(_run_command(arguments))
    except KeyboardInterrupt, SystemExit:
        raise
    except BaseException as error:
        print(json.dumps(_error_payload(error), ensure_ascii=False, indent=2), file=sys.stderr)
        return 2
    sys.stdout.write(published.stdout)
    return 0


if __name__ == "__main__":
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    raise SystemExit(main())


__all__ = [
    "CurrentPopulation",
    "ManualRunError",
    "PublishedManualRun",
    "run_manual_retrieval",
]
