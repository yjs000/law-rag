"""Run the approved Experiment D gold suite against raw dense provision search.

The command is intentionally fail-closed.  It validates and audits the frozen
gold twice, never embeds before the first audit, holds a shared corpus mutation
lock across the second audit and every search, and publishes only a complete
result without overwriting an earlier run.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import struct
import subprocess
import sys
from collections.abc import AsyncIterator, Callable, Mapping, Sequence
from contextlib import asynccontextmanager, suppress
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime
from math import fsum, isfinite, sqrt
from pathlib import Path
from typing import Any, Protocol
from uuid import uuid4

from law_rag_core.persistence import (
    CORPUS_MUTATION_LOCK_KEY,
    LEGAL_PROVISION_V1_SOURCE_SHA_SQL,
    SEARCHABLE_DOCUMENT_VERSION_SQL,
)
from pydantic import ValidationError
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from app.adapters.nvidia_nim_embedder import NvidiaNimEmbedder
from app.adapters.postgres_repository import PostgresLegalRepository
from app.domain.embedding_profiles import NVIDIA_NEMOTRON_512_PROFILE
from app.domain.schemas import CorpusSearchStatus, SearchHit
from app.settings import Settings, get_settings
from scripts.experiment_d_corpus import (
    SourceProvision,
    load_provisions_from_connection,
)
from scripts.experiment_d_gold_contract import (
    ExperimentDGoldAdjudicationManifest,
    ExperimentDGoldDataset,
    ExperimentDQuestionApprovalManifest,
)
from scripts.experiment_d_metrics import evaluate_dense_retrieval, metric_cases_from_gold
from scripts.preflight_experiment_d_gold import (
    GoldPreflightReport,
    NonCurrentParserIdError,
    audit_gold_dataset,
    gold_adjudication_manifest_errors,
)

REPOSITORY_ROOT = Path(__file__).parents[3]
DEFAULT_OUTPUT_DIR = REPOSITORY_ROOT / ".data" / "experiments" / "experiment-d" / "runs"
SEARCH_LIMIT_WITH_TIE_SENTINEL = 11
RETRIEVAL_EXECUTION_MODE = "exact_cosine"
CRITICAL_CODE_PATHS = (
    Path("apps/api/scripts/evaluate_experiment_d_gold.py"),
    Path("apps/api/scripts/experiment_d_metrics.py"),
    Path("apps/api/scripts/experiment_d_gold_contract.py"),
    Path("apps/api/scripts/preflight_experiment_d_gold.py"),
    Path("apps/api/scripts/experiment_d_corpus.py"),
    Path("apps/api/scripts/experiment_d_question_identity.py"),
    Path("apps/api/app/adapters/postgres_repository.py"),
    Path("apps/api/app/adapters/nvidia_nim_embedder.py"),
    Path("apps/api/app/domain/catalog.py"),
    Path("apps/api/app/domain/corpus_temporal_contract.py"),
    Path("apps/api/app/domain/embedding_profiles.py"),
    Path("apps/api/app/domain/errors.py"),
    Path("apps/api/app/domain/schemas.py"),
    Path("apps/api/app/settings.py"),
    Path("packages/law-rag-core/src/law_rag_core/domain/catalog.py"),
    Path("packages/law-rag-core/src/law_rag_core/persistence.py"),
    Path("packages/law-rag-core/src/law_rag_core/domain/identifiers.py"),
    Path("packages/law-rag-core/src/law_rag_core/domain/schemas.py"),
    Path("apps/api/pyproject.toml"),
    Path("pyproject.toml"),
    Path("uv.lock"),
)


class GoldRunError(RuntimeError):
    def __init__(
        self,
        code: str,
        *,
        details: Mapping[str, object] | None = None,
    ) -> None:
        super().__init__(code)
        self.code = code
        self.details = dict(details or {})


@dataclass(frozen=True, slots=True)
class GoldRunArtifacts:
    dataset: ExperimentDGoldDataset
    dataset_raw: dict[str, object]
    source_bank_raw: dict[str, object]
    approval_manifest_raw: dict[str, object]
    adjudication_manifest_raw: dict[str, object]
    dataset_sha256: str
    source_bank_sha256: str
    approval_manifest_sha256: str
    adjudication_manifest_sha256: str


@dataclass(frozen=True, slots=True)
class CorpusSnapshot:
    status: CorpusSearchStatus
    provisions: tuple[SourceProvision, ...]
    retrieval_state: RetrievalState


@dataclass(frozen=True, slots=True)
class RetrievalState:
    profile: dict[str, object] | None
    vector_count: int
    non_unit_vector_count: int
    vector_fingerprint_sha256: str
    pgvector_version: str | None
    retrieval_settings: dict[str, str | None]
    state_fingerprint_sha256: str

    def to_dict(self) -> dict[str, object]:
        return {
            "profile": self.profile,
            "vector_count": self.vector_count,
            "non_unit_vector_count": self.non_unit_vector_count,
            "vector_fingerprint_sha256": self.vector_fingerprint_sha256,
            "pgvector_version": self.pgvector_version,
            "retrieval_settings": self.retrieval_settings,
            "state_fingerprint_sha256": self.state_fingerprint_sha256,
        }


@dataclass(frozen=True, slots=True)
class DenseCandidate:
    provision_id: str
    document_id: str
    document_title: str
    source_kind: str
    version_label: str
    effective_from: date | None
    effective_to: date | None
    path: str
    heading: str | None
    content: str
    source_url: str
    score: float

    @classmethod
    def from_search_hit(cls, hit: SearchHit) -> DenseCandidate:
        return cls(
            provision_id=str(hit.provision_id),
            document_id=str(hit.document_id),
            document_title=hit.document_title,
            source_kind=hit.source_kind.value,
            version_label=hit.version_label,
            effective_from=hit.effective_from,
            effective_to=hit.effective_to,
            path=hit.path,
            heading=hit.heading,
            content=hit.content,
            source_url=hit.source_url,
            score=hit.score,
        )


class QueryEmbedder(Protocol):
    async def embed(self, texts: list[str]) -> list[list[float]]: ...


class LockedDenseReader(Protocol):
    async def snapshot(self) -> CorpusSnapshot: ...

    async def search(
        self,
        *,
        as_of_date: date,
        query_embedding: list[float],
        limit: int,
    ) -> list[DenseCandidate]: ...

    async def explain(
        self,
        *,
        as_of_date: date,
        query_embedding: list[float],
        limit: int,
    ) -> object: ...


class ExperimentDBackend(Protocol):
    async def snapshot(self) -> CorpusSnapshot: ...

    def locked_reader(self) -> Any: ...


@dataclass(frozen=True, slots=True)
class PublishedGoldRun:
    path: Path
    file_sha256: str
    payload: dict[str, object]


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="승인된 실험 D gold만 raw provision dense-only로 평가"
    )
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--source-bank", type=Path, required=True)
    parser.add_argument("--approval-manifest", type=Path, required=True)
    parser.add_argument("--adjudication-manifest", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--embedding-batch-size", type=int, default=32)
    return parser.parse_args()


def _canonical_json_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _read_json_object(path: Path) -> tuple[dict[str, object], str]:
    try:
        raw_bytes = path.read_bytes()
        value = json.loads(raw_bytes.decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise GoldRunError(
            "gold_artifact_unreadable",
            details={"artifact": path.name, "error_type": type(error).__name__},
        ) from error
    if not isinstance(value, dict):
        raise GoldRunError(
            "gold_artifact_root_not_object",
            details={"artifact": path.name},
        )
    return value, _sha256(raw_bytes)


def validate_gold_artifacts(
    dataset_raw: dict[str, object],
    source_bank_raw: dict[str, object],
    approval_manifest_raw: dict[str, object],
    adjudication_manifest_raw: dict[str, object],
    *,
    dataset_sha256: str | None = None,
    source_bank_sha256: str | None = None,
    approval_manifest_sha256: str | None = None,
    adjudication_manifest_sha256: str | None = None,
) -> GoldRunArtifacts:
    try:
        dataset = ExperimentDGoldDataset.model_validate(dataset_raw)
        question_approval = ExperimentDQuestionApprovalManifest.model_validate(
            approval_manifest_raw
        )
        adjudication = ExperimentDGoldAdjudicationManifest.model_validate(adjudication_manifest_raw)
    except ValidationError as error:
        raise GoldRunError(
            "gold_artifact_contract_invalid",
            details={"validation_error_count": error.error_count()},
        ) from error
    adjudication_errors = gold_adjudication_manifest_errors(
        dataset,
        question_approval,
        adjudication,
    )
    if adjudication_errors:
        raise GoldRunError(
            "gold_adjudication_binding_invalid",
            details={
                "error_count": len(adjudication_errors),
                "error_sample": list(adjudication_errors[:20]),
            },
        )
    return GoldRunArtifacts(
        dataset=dataset,
        dataset_raw=dataset_raw,
        source_bank_raw=source_bank_raw,
        approval_manifest_raw=approval_manifest_raw,
        adjudication_manifest_raw=adjudication_manifest_raw,
        dataset_sha256=dataset_sha256 or _sha256(_canonical_json_bytes(dataset_raw)),
        source_bank_sha256=(source_bank_sha256 or _sha256(_canonical_json_bytes(source_bank_raw))),
        approval_manifest_sha256=(
            approval_manifest_sha256 or _sha256(_canonical_json_bytes(approval_manifest_raw))
        ),
        adjudication_manifest_sha256=(
            adjudication_manifest_sha256
            or _sha256(_canonical_json_bytes(adjudication_manifest_raw))
        ),
    )


def load_gold_artifacts(
    dataset_path: Path,
    source_bank_path: Path,
    approval_manifest_path: Path,
    adjudication_manifest_path: Path,
) -> GoldRunArtifacts:
    resolved = [
        dataset_path.resolve(),
        source_bank_path.resolve(),
        approval_manifest_path.resolve(),
        adjudication_manifest_path.resolve(),
    ]
    if len(set(resolved)) != len(resolved):
        raise GoldRunError("gold_artifact_paths_must_be_distinct")
    dataset_raw, dataset_sha = _read_json_object(dataset_path)
    source_bank_raw, source_bank_sha = _read_json_object(source_bank_path)
    approval_raw, approval_sha = _read_json_object(approval_manifest_path)
    adjudication_raw, adjudication_sha = _read_json_object(adjudication_manifest_path)
    artifacts = validate_gold_artifacts(
        dataset_raw,
        source_bank_raw,
        approval_raw,
        adjudication_raw,
        dataset_sha256=dataset_sha,
        source_bank_sha256=source_bank_sha,
        approval_manifest_sha256=approval_sha,
        adjudication_manifest_sha256=adjudication_sha,
    )
    if Path(artifacts.dataset.source_bank.artifact).name != source_bank_path.name:
        raise GoldRunError("source_bank_artifact_name_mismatch")
    if (
        Path(artifacts.dataset.source_bank.approval_manifest_artifact).name
        != approval_manifest_path.name
    ):
        raise GoldRunError("approval_manifest_artifact_name_mismatch")
    return artifacts


async def _load_retrieval_state(connection: AsyncConnection) -> RetrievalState:
    profile_row = (
        (
            await connection.execute(
                text(
                    """SELECT profile_key,provider,model,native_dimensions,
                    stored_dimensions,document_input_type,query_input_type,
                    truncation,normalization,text_template_version,profile_version,active
                    FROM embedding_profiles WHERE profile_key=:profile_key"""
                ),
                {"profile_key": NVIDIA_NEMOTRON_512_PROFILE.key},
            )
        )
        .mappings()
        .one_or_none()
    )
    profile = dict(profile_row) if profile_row is not None else None
    pgvector_version = (
        await connection.execute(text("SELECT extversion FROM pg_extension WHERE extname='vector'"))
    ).scalar_one_or_none()
    settings_row = (
        (
            await connection.execute(
                text(
                    """SELECT
                    current_setting('transaction_isolation',true) transaction_isolation,
                    current_setting('transaction_read_only',true) transaction_read_only,
                    current_setting('server_version',true) postgresql_version,
                    current_setting('server_version_num',true) postgresql_version_num,
                    current_setting('search_path',true) search_path,
                    current_setting('enable_seqscan',true) enable_seqscan,
                    current_setting('enable_indexscan',true) enable_indexscan,
                    current_setting('enable_bitmapscan',true) enable_bitmapscan,
                    current_setting('random_page_cost',true) random_page_cost,
                    current_setting('effective_cache_size',true) effective_cache_size,
                    current_setting('work_mem',true) work_mem"""
                )
            )
        )
        .mappings()
        .one()
    )
    retrieval_settings = {
        str(key): (str(value) if value is not None else None) for key, value in settings_row.items()
    }
    vector_rows = (
        (
            await connection.execute(
                text(
                    f"""SELECT p.id provision_id,e.source_text_sha256,
                    e.embedding::text embedding_text,vector_norm(e.embedding) embedding_norm
                    FROM provisions p
                    JOIN document_versions v ON v.id=p.version_id
                    JOIN legal_documents d ON d.id=v.document_id
                    JOIN provision_embeddings e ON e.provision_id=p.id
                    JOIN embedding_profiles ep
                      ON ep.profile_key=e.profile_key
                     AND ep.stored_dimensions=e.dimensions
                    WHERE {SEARCHABLE_DOCUMENT_VERSION_SQL}
                      AND e.profile_key=:profile_key
                      AND e.dimensions=:dimensions
                      AND ep.active IS TRUE
                      AND ep.text_template_version='legal-provision-v1'
                      AND e.source_text_sha256={LEGAL_PROVISION_V1_SOURCE_SHA_SQL}
                    ORDER BY p.id"""
                ),
                {
                    "profile_key": NVIDIA_NEMOTRON_512_PROFILE.key,
                    "dimensions": NVIDIA_NEMOTRON_512_PROFILE.stored_dimensions,
                },
            )
        )
        .mappings()
        .all()
    )
    vector_hasher = hashlib.sha256()
    non_unit_vector_count = 0
    for row in vector_rows:
        try:
            embedding_norm = float(row["embedding_norm"])
        except TypeError, ValueError:
            non_unit_vector_count += 1
        else:
            if not isfinite(embedding_norm) or abs(embedding_norm - 1.0) > 0.0001:
                non_unit_vector_count += 1
        vector_hasher.update(
            _canonical_json_bytes(
                {
                    "provision_id": str(row["provision_id"]),
                    "source_text_sha256": row["source_text_sha256"],
                    "embedding_text": row["embedding_text"],
                }
            )
        )
        vector_hasher.update(b"\n")
    pgvector_version_text = str(pgvector_version) if pgvector_version is not None else None
    vector_fingerprint = vector_hasher.hexdigest()
    state_without_hash: dict[str, object] = {
        "profile": profile,
        "vector_count": len(vector_rows),
        "non_unit_vector_count": non_unit_vector_count,
        "vector_fingerprint_sha256": vector_fingerprint,
        "pgvector_version": pgvector_version_text,
        "retrieval_settings": retrieval_settings,
    }
    return RetrievalState(
        profile=profile,
        vector_count=len(vector_rows),
        non_unit_vector_count=non_unit_vector_count,
        vector_fingerprint_sha256=vector_fingerprint,
        pgvector_version=pgvector_version_text,
        retrieval_settings=retrieval_settings,
        state_fingerprint_sha256=_sha256(_canonical_json_bytes(state_without_hash)),
    )


async def _snapshot_on_connection(
    repository: PostgresLegalRepository,
    connection: AsyncConnection,
) -> CorpusSnapshot:
    status = await repository.corpus_search_status_on_connection(connection)
    provisions = await load_provisions_from_connection(connection)
    retrieval_state = await _load_retrieval_state(connection)
    return CorpusSnapshot(
        status=status,
        provisions=tuple(provisions),
        retrieval_state=retrieval_state,
    )


async def _configure_search_path(connection: AsyncConnection) -> None:
    # Keep public corpus relations ahead of extension and temporary schemas,
    # while resolving built-in functions from pg_catalog first.
    await connection.execute(text("SET LOCAL search_path=pg_catalog,public,extensions,pg_temp"))


async def _set_repeatable_read_only(connection: AsyncConnection) -> None:
    await connection.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY"))


async def _set_read_committed_read_only(connection: AsyncConnection) -> None:
    # The shared advisory lock is the first snapshot-taking statement.  The
    # following corpus read must see a writer that committed just before the
    # nonblocking lock succeeds, so this locked transaction uses READ COMMITTED.
    await connection.execute(text("SET TRANSACTION ISOLATION LEVEL READ COMMITTED, READ ONLY"))


class _PostgresLockedDenseReader:
    def __init__(
        self,
        repository: PostgresLegalRepository,
        connection: AsyncConnection,
    ) -> None:
        self._repository = repository
        self._connection = connection

    async def snapshot(self) -> CorpusSnapshot:
        return await _snapshot_on_connection(self._repository, self._connection)

    async def search(
        self,
        *,
        as_of_date: date,
        query_embedding: list[float],
        limit: int,
    ) -> list[DenseCandidate]:
        hits = await self._repository.search_dense_provisions_on_connection(
            self._connection,
            as_of_date,
            limit,
            query_embedding,
            NVIDIA_NEMOTRON_512_PROFILE.key,
        )
        return [DenseCandidate.from_search_hit(hit) for hit in hits]

    async def explain(
        self,
        *,
        as_of_date: date,
        query_embedding: list[float],
        limit: int,
    ) -> object:
        return await self._repository.explain_dense_provisions_on_connection(
            self._connection,
            as_of_date,
            limit,
            query_embedding,
            NVIDIA_NEMOTRON_512_PROFILE.key,
        )


class PostgresExperimentDBackend:
    """Backend holding one transaction-scoped shared lock for the evaluation."""

    def __init__(self, database_url: str) -> None:
        if not database_url:
            raise GoldRunError("database_url_required")
        self.repository = PostgresLegalRepository(database_url)

    async def snapshot(self) -> CorpusSnapshot:
        async with self.repository.engine.connect() as connection:
            async with connection.begin():
                await _set_repeatable_read_only(connection)
                await _configure_search_path(connection)
                return await _snapshot_on_connection(self.repository, connection)

    @asynccontextmanager
    async def locked_reader(self) -> AsyncIterator[LockedDenseReader]:
        async with self.repository.engine.connect() as connection:
            async with connection.begin():
                await _set_read_committed_read_only(connection)
                await _configure_search_path(connection)
                acquired = (
                    await connection.execute(
                        text("SELECT pg_catalog.pg_try_advisory_xact_lock_shared(:lock_key)"),
                        {"lock_key": CORPUS_MUTATION_LOCK_KEY},
                    )
                ).scalar_one()
                if acquired is not True:
                    raise GoldRunError("corpus_mutation_in_progress")
                yield _PostgresLockedDenseReader(self.repository, connection)

    async def close(self) -> None:
        await self.repository.engine.dispose()


def _audit_or_raise(
    stage: str,
    artifacts: GoldRunArtifacts,
    snapshot: CorpusSnapshot,
) -> GoldPreflightReport:
    try:
        report = audit_gold_dataset(
            artifacts.dataset_raw,
            snapshot.provisions,
            artifacts.source_bank_raw,
            artifacts.approval_manifest_raw,
            artifacts.adjudication_manifest_raw,
            corpus_search_ready=snapshot.status.ready,
            corpus_search_ready_reason=snapshot.status.reason,
        )
    except NonCurrentParserIdError as error:
        raise GoldRunError(
            f"{stage}_non_current_parser_ids",
            details=error.to_dict(),
        ) from error
    if not report.ready:
        raise GoldRunError(
            f"{stage}_preflight_rejected",
            details={"preflight": report.to_dict()},
        )
    return report


def _validate_retrieval_state(stage: str, snapshot: CorpusSnapshot) -> None:
    state = snapshot.retrieval_state
    expected_profile: dict[str, object] = {
        "profile_key": NVIDIA_NEMOTRON_512_PROFILE.key,
        "provider": NVIDIA_NEMOTRON_512_PROFILE.provider,
        "model": NVIDIA_NEMOTRON_512_PROFILE.model,
        "native_dimensions": NVIDIA_NEMOTRON_512_PROFILE.native_dimensions,
        "stored_dimensions": NVIDIA_NEMOTRON_512_PROFILE.stored_dimensions,
        "document_input_type": NVIDIA_NEMOTRON_512_PROFILE.document_input_type,
        "query_input_type": NVIDIA_NEMOTRON_512_PROFILE.query_input_type,
        "truncation": NVIDIA_NEMOTRON_512_PROFILE.truncation,
        "normalization": NVIDIA_NEMOTRON_512_PROFILE.normalization,
        "text_template_version": NVIDIA_NEMOTRON_512_PROFILE.text_template_version,
        "profile_version": NVIDIA_NEMOTRON_512_PROFILE.profile_version,
        "active": True,
    }
    errors: list[str] = []
    if state.profile != expected_profile:
        errors.append("embedding_profile_contract_mismatch")
    if state.vector_count != len(snapshot.provisions):
        errors.append("active_vector_coverage_mismatch")
    if state.non_unit_vector_count != 0:
        errors.append("passage_embedding_not_l2_normalized")
    if not state.pgvector_version:
        errors.append("pgvector_version_missing")
    expected_transaction_isolation = "read committed" if stage == "locked" else "repeatable read"
    expected_retrieval_settings = {
        "transaction_isolation": expected_transaction_isolation,
        "transaction_read_only": "on",
    }
    if any(
        state.retrieval_settings.get(key) != value
        for key, value in expected_retrieval_settings.items()
    ):
        errors.append("retrieval_runtime_settings_mismatch")
    planner_setting_keys = {
        "enable_seqscan",
        "enable_indexscan",
        "enable_bitmapscan",
        "random_page_cost",
        "effective_cache_size",
        "work_mem",
        "postgresql_version",
        "postgresql_version_num",
        "search_path",
    }
    if any(not state.retrieval_settings.get(key) for key in planner_setting_keys):
        errors.append("planner_settings_missing")
    if state.retrieval_settings.get("search_path") != ("pg_catalog, public, extensions, pg_temp"):
        errors.append("search_path_mismatch")
    if errors:
        raise GoldRunError(
            f"{stage}_retrieval_state_rejected",
            details={
                "reasons": errors,
                "retrieval_state": state.to_dict(),
                "searchable_provision_count": len(snapshot.provisions),
            },
        )


def _validate_query_vector(vector: Sequence[float]) -> list[float]:
    dimensions = NVIDIA_NEMOTRON_512_PROFILE.stored_dimensions
    if len(vector) != dimensions:
        raise GoldRunError(
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
            raise GoldRunError("query_embedding_nonfinite")
        normalized.append(float(component))
    norm = sqrt(fsum(component * component for component in normalized))
    if abs(norm - 1.0) > 0.0001:
        raise GoldRunError(
            "query_embedding_not_l2_normalized",
            details={"norm": norm},
        )
    return normalized


async def _embed_all_questions(
    dataset: ExperimentDGoldDataset,
    embedder: QueryEmbedder,
    *,
    batch_size: int,
) -> list[list[float]]:
    if not 1 <= batch_size <= 128:
        raise GoldRunError("embedding_batch_size_out_of_range")
    vectors: list[list[float]] = []
    for start in range(0, len(dataset.cases), batch_size):
        cases = dataset.cases[start : start + batch_size]
        embedded = await embedder.embed([case.question for case in cases])
        if len(embedded) != len(cases):
            raise GoldRunError(
                "query_embedding_batch_count_mismatch",
                details={"expected": len(cases), "actual": len(embedded)},
            )
        vectors.extend(_validate_query_vector(vector) for vector in embedded)
    if len(vectors) != len(dataset.cases):
        raise GoldRunError("query_embedding_total_count_mismatch")
    return vectors


def _embedding_sha256(vector: Sequence[float]) -> str:
    return _sha256(struct.pack(f"<{len(vector)}d", *vector))


def _validate_dense_candidates(
    candidates: Sequence[DenseCandidate],
) -> tuple[DenseCandidate, ...]:
    if len(candidates) > SEARCH_LIMIT_WITH_TIE_SENTINEL:
        raise GoldRunError("dense_search_returned_too_many_candidates")
    seen: set[str] = set()
    previous: DenseCandidate | None = None
    for candidate in candidates:
        if not candidate.provision_id or candidate.provision_id in seen:
            raise GoldRunError("dense_search_duplicate_provision_id")
        if not isfinite(candidate.score):
            raise GoldRunError("dense_search_nonfinite_score")
        seen.add(candidate.provision_id)
        if previous is not None and (
            candidate.score > previous.score
            or (
                candidate.score == previous.score and candidate.provision_id < previous.provision_id
            )
        ):
            raise GoldRunError("dense_search_order_contract_violated")
        previous = candidate
    if (
        len(candidates) == SEARCH_LIMIT_WITH_TIE_SENTINEL
        and candidates[9].score == candidates[10].score
    ):
        raise GoldRunError(
            "unresolved_cutoff_tie",
            details={
                "rank_10_provision_id": candidates[9].provision_id,
                "rank_11_provision_id": candidates[10].provision_id,
                "score": candidates[9].score,
            },
        )
    return tuple(candidates[:10])


def _candidate_record(rank: int, candidate: DenseCandidate) -> dict[str, object]:
    return {
        "rank": rank,
        "provision_id": candidate.provision_id,
        "document_id": candidate.document_id,
        "document_title": candidate.document_title,
        "source_kind": candidate.source_kind,
        "version_label": candidate.version_label,
        "effective_from": (
            candidate.effective_from.isoformat() if candidate.effective_from else None
        ),
        "effective_to": (candidate.effective_to.isoformat() if candidate.effective_to else None),
        "path": candidate.path,
        "heading": candidate.heading,
        "source_url": candidate.source_url,
        "content_sha256": _sha256(candidate.content.encode("utf-8")),
        "raw_cosine_similarity": candidate.score,
    }


def _iso_utc(value: datetime) -> str:
    if value.tzinfo is None:
        raise ValueError("run timestamp must be timezone-aware")
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _is_lower_hex(value: object, *, length: int) -> bool:
    return (
        isinstance(value, str)
        and len(value) == length
        and all(character in "0123456789abcdef" for character in value)
    )


def _validate_code_provenance(value: Mapping[str, object]) -> dict[str, object]:
    expected_top_level = {
        "git_commit",
        "critical_code_dirty",
        "critical_file_sha256",
    }
    if set(value) != expected_top_level:
        raise GoldRunError("code_provenance_contract_invalid")
    if not _is_lower_hex(value.get("git_commit"), length=40):
        raise GoldRunError("code_revision_invalid")
    if value.get("critical_code_dirty") is not False:
        raise GoldRunError("critical_code_worktree_dirty")
    hashes = value.get("critical_file_sha256")
    expected_paths = {path.as_posix() for path in CRITICAL_CODE_PATHS}
    if not isinstance(hashes, Mapping) or set(hashes) != expected_paths:
        raise GoldRunError("critical_code_hash_contract_invalid")
    if any(not _is_lower_hex(digest, length=64) for digest in hashes.values()):
        raise GoldRunError("critical_code_hash_invalid")
    return {
        "git_commit": value["git_commit"],
        "critical_code_dirty": False,
        "critical_file_sha256": dict(hashes),
    }


def _current_code_provenance() -> dict[str, object]:
    try:
        commit_result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=REPOSITORY_ROOT,
            check=True,
            capture_output=True,
            text=True,
            timeout=5,
        )
        status_result = subprocess.run(
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
        )
    except OSError, subprocess.SubprocessError:
        raise GoldRunError("code_provenance_unavailable") from None
    commit = commit_result.stdout.strip()
    if not _is_lower_hex(commit, length=40):
        raise GoldRunError("code_revision_invalid")
    dirty_lines = [line for line in status_result.stdout.splitlines() if line.strip()]
    if dirty_lines:
        raise GoldRunError(
            "critical_code_worktree_dirty",
            details={"critical_status": dirty_lines},
        )
    file_hashes: dict[str, str] = {}
    for relative_path in CRITICAL_CODE_PATHS:
        absolute_path = REPOSITORY_ROOT / relative_path
        try:
            file_hashes[relative_path.as_posix()] = _sha256(absolute_path.read_bytes())
        except OSError as error:
            raise GoldRunError(
                "critical_code_file_unreadable",
                details={
                    "path": relative_path.as_posix(),
                    "error_type": type(error).__name__,
                },
            ) from error
    return _validate_code_provenance(
        {
            "git_commit": commit,
            "critical_code_dirty": False,
            "critical_file_sha256": file_hashes,
        }
    )


def _retrieval_observation_sha256(
    case_records: Sequence[Mapping[str, object]],
) -> str:
    observations = [
        {
            "case_id": record["case_id"],
            "query_embedding_sha256": record["query_embedding_sha256"],
            "hits": [
                {
                    "rank": hit["rank"],
                    "provision_id": hit["provision_id"],
                    "raw_cosine_similarity": hit["raw_cosine_similarity"],
                }
                for hit in record["hits"]
            ],
        }
        for record in case_records
    ]
    return _sha256(_canonical_json_bytes(observations))


def _normalize_explain_plan(value: object) -> list[dict[str, object]]:
    try:
        decoded = json.loads(value) if isinstance(value, str) else value
        normalized = json.loads(_canonical_json_bytes(decoded))
    except (TypeError, ValueError, json.JSONDecodeError) as error:
        raise GoldRunError("query_plan_not_serializable") from error
    if (
        not isinstance(normalized, list)
        or len(normalized) != 1
        or not isinstance(normalized[0], dict)
        or not isinstance(normalized[0].get("Plan"), dict)
    ):
        raise GoldRunError("query_plan_contract_invalid")
    return normalized


async def _capture_query_plans(
    dataset: ExperimentDGoldDataset,
    query_vectors: Sequence[list[float]],
    reader: LockedDenseReader,
) -> tuple[list[dict[str, object]], str]:
    representative_by_date: dict[date, tuple[str, list[float]]] = {}
    for case, vector in zip(dataset.cases, query_vectors, strict=True):
        representative_by_date.setdefault(case.as_of_date, (case.id, vector))
    records: list[dict[str, object]] = []
    for as_of_date in sorted(representative_by_date):
        case_id, vector = representative_by_date[as_of_date]
        plan = _normalize_explain_plan(
            await reader.explain(
                as_of_date=as_of_date,
                query_embedding=vector,
                limit=SEARCH_LIMIT_WITH_TIE_SENTINEL,
            )
        )
        records.append(
            {
                "as_of_date": as_of_date.isoformat(),
                "representative_case_id": case_id,
                "query_embedding_sha256": _embedding_sha256(vector),
                "retrieval_execution_mode": RETRIEVAL_EXECUTION_MODE,
                "plan": plan,
            }
        )
    records_sha256 = _sha256(_canonical_json_bytes(records))
    return records, records_sha256


async def evaluate_approved_gold(
    artifacts: GoldRunArtifacts,
    backend: ExperimentDBackend,
    embedder_factory: Callable[[], QueryEmbedder],
    *,
    batch_size: int,
    run_id: str,
    started_at: datetime,
    completed_at_factory: Callable[[], datetime],
    code_provenance: Mapping[str, object],
) -> dict[str, object]:
    validated_code_provenance = _validate_code_provenance(code_provenance)
    initial_snapshot = await backend.snapshot()
    initial_preflight = _audit_or_raise("initial", artifacts, initial_snapshot)
    _validate_retrieval_state("initial", initial_snapshot)

    embedder = embedder_factory()
    query_vectors = await _embed_all_questions(
        artifacts.dataset,
        embedder,
        batch_size=batch_size,
    )

    case_records: list[dict[str, object]] = []
    rankings_by_case: dict[str, list[str]] = {}
    async with backend.locked_reader() as reader:
        locked_snapshot = await reader.snapshot()
        locked_preflight = _audit_or_raise("locked", artifacts, locked_snapshot)
        _validate_retrieval_state("locked", locked_snapshot)
        query_plans, query_plans_sha256 = await _capture_query_plans(
            artifacts.dataset,
            query_vectors,
            reader,
        )
        for case, vector in zip(artifacts.dataset.cases, query_vectors, strict=True):
            candidates = _validate_dense_candidates(
                await reader.search(
                    as_of_date=case.as_of_date,
                    query_embedding=vector,
                    limit=SEARCH_LIMIT_WITH_TIE_SENTINEL,
                )
            )
            rankings_by_case[case.id] = [item.provision_id for item in candidates]
            case_records.append(
                {
                    "case_id": case.id,
                    "question": case.question,
                    "question_sha256": case.question_sha256,
                    "split": case.split,
                    "answerability": case.answerability,
                    "as_of_date": case.as_of_date.isoformat(),
                    "query_embedding_sha256": _embedding_sha256(vector),
                    "query_embedding": vector,
                    "hits": [
                        _candidate_record(rank, candidate)
                        for rank, candidate in enumerate(candidates, 1)
                    ],
                }
            )

    metrics = evaluate_dense_retrieval(
        metric_cases_from_gold(artifacts.dataset),
        rankings_by_case,
        ks=tuple(artifacts.dataset.metric_protocol.cutoffs),
    )
    retrieval_observation_sha256 = _retrieval_observation_sha256(case_records)
    corpus_snapshot_id = locked_preflight.current_corpus_snapshot_id
    if corpus_snapshot_id is None:
        raise GoldRunError("locked_corpus_snapshot_identity_missing")
    as_of_population_fingerprints = [
        asdict(population) for population in locked_preflight.current_as_of_populations
    ]
    metric_payload = {
        "dataset_sha256": artifacts.dataset_sha256,
        "adjudication_manifest_sha256": artifacts.adjudication_manifest_sha256,
        "question_set_sha256": artifacts.dataset.source_bank.question_set_sha256,
        "question_scope_set_sha256": (artifacts.dataset.source_bank.question_scope_set_sha256),
        "corpus_snapshot_id": corpus_snapshot_id,
        "as_of_population_fingerprints": as_of_population_fingerprints,
        "embedding_profile_key": NVIDIA_NEMOTRON_512_PROFILE.key,
        "embedding_batch_size": batch_size,
        "retrieval_execution_mode": RETRIEVAL_EXECUTION_MODE,
        "retrieval_state_fingerprint_sha256": (
            locked_snapshot.retrieval_state.state_fingerprint_sha256
        ),
        "query_plans_sha256": query_plans_sha256,
        "rankings_by_case": rankings_by_case,
        "metrics": metrics,
    }
    completed_at = completed_at_factory()
    payload: dict[str, object] = {
        "schema_version": 4,
        "experiment": "D",
        "status": "completed",
        "run_id": run_id,
        "started_at": _iso_utc(started_at),
        "completed_at": _iso_utc(completed_at),
        "retrieval_execution_mode": RETRIEVAL_EXECUTION_MODE,
        "retrieval_contract": artifacts.dataset.metric_protocol.model_dump(mode="json"),
        "inputs": {
            "dataset_sha256": artifacts.dataset_sha256,
            "source_bank_sha256": artifacts.source_bank_sha256,
            "approval_manifest_sha256": artifacts.approval_manifest_sha256,
            "adjudication_manifest_sha256": artifacts.adjudication_manifest_sha256,
            "question_set_sha256": artifacts.dataset.source_bank.question_set_sha256,
            "question_scope_set_sha256": (artifacts.dataset.source_bank.question_scope_set_sha256),
            "corpus_snapshot_id": corpus_snapshot_id,
            "as_of_population_fingerprints": as_of_population_fingerprints,
            "embedding_profile_key": NVIDIA_NEMOTRON_512_PROFILE.key,
            "embedding_batch_size": batch_size,
            "retrieval_execution_mode": RETRIEVAL_EXECUTION_MODE,
            "retrieval_state_fingerprint_sha256": (
                locked_snapshot.retrieval_state.state_fingerprint_sha256
            ),
            "query_plans_sha256": query_plans_sha256,
            "code_provenance": validated_code_provenance,
        },
        "initial_preflight": initial_preflight.to_dict(),
        "locked_preflight": locked_preflight.to_dict(),
        "case_count": len(case_records),
        "search_count": len(case_records),
        "retrieval_state": locked_snapshot.retrieval_state.to_dict(),
        "query_plans": query_plans,
        "retrieval_observation_sha256": retrieval_observation_sha256,
        "metrics": metrics,
        "metric_payload_sha256": _sha256(_canonical_json_bytes(metric_payload)),
        "cases": case_records,
    }
    payload["payload_without_self_hash_sha256"] = _sha256(_canonical_json_bytes(payload))
    _canonical_json_bytes(payload)
    return payload


def _atomic_publish(
    output_dir: Path,
    run_id: str,
    payload: dict[str, object],
) -> tuple[Path, str]:
    serialized = (
        json.dumps(
            payload,
            ensure_ascii=False,
            allow_nan=False,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )
    encoded = serialized.encode("utf-8")
    final_path = output_dir / f"{run_id}.json"
    temporary_path = output_dir / f".{run_id}.{uuid4().hex}.tmp"
    output_dir.mkdir(parents=True, exist_ok=True)
    try:
        with temporary_path.open("xb") as stream:
            stream.write(encoded)
            stream.flush()
            os.fsync(stream.fileno())
        try:
            os.link(temporary_path, final_path)
        except FileExistsError as error:
            raise GoldRunError("result_run_id_already_exists") from error
        with suppress(OSError):
            directory_descriptor = os.open(output_dir, os.O_RDONLY)
            try:
                os.fsync(directory_descriptor)
            finally:
                os.close(directory_descriptor)
    finally:
        with suppress(OSError):
            temporary_path.unlink(missing_ok=True)
    return final_path, _sha256(encoded)


async def run_and_publish_approved_gold(
    artifacts: GoldRunArtifacts,
    backend: ExperimentDBackend,
    embedder_factory: Callable[[], QueryEmbedder],
    output_dir: Path,
    *,
    code_provenance: Mapping[str, object],
    batch_size: int = 32,
    clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    run_id_factory: Callable[[], str] | None = None,
    publisher: Callable[[Path, str, dict[str, object]], tuple[Path, str]] = _atomic_publish,
) -> PublishedGoldRun:
    started_at = clock()
    run_id = (
        run_id_factory()
        if run_id_factory is not None
        else f"experiment-d-{started_at.strftime('%Y%m%dT%H%M%S%fZ')}-{uuid4().hex[:12]}"
    )
    if not run_id or any(
        character not in "abcdefghijklmnopqrstuvwxyz0123456789-_" for character in run_id
    ):
        raise GoldRunError("invalid_run_id")
    payload = await evaluate_approved_gold(
        artifacts,
        backend,
        embedder_factory,
        batch_size=batch_size,
        run_id=run_id,
        started_at=started_at,
        completed_at_factory=clock,
        code_provenance=code_provenance,
    )
    path, file_sha = publisher(output_dir, run_id, payload)
    return PublishedGoldRun(path=path, file_sha256=file_sha, payload=payload)


def _embedder_factory(settings: Settings) -> QueryEmbedder:
    if not settings.nvidia_api_key:
        raise GoldRunError("nvidia_api_key_required")
    return NvidiaNimEmbedder(
        api_key=settings.nvidia_api_key,
        base_url=settings.nvidia_base_url,
        model=settings.nvidia_embedding_model,
        dimensions=settings.embedding_dimensions,
        timeout_seconds=settings.embedding_timeout_seconds,
        input_type=NVIDIA_NEMOTRON_512_PROFILE.query_input_type,
    )


async def _run(arguments: argparse.Namespace) -> PublishedGoldRun:
    settings = get_settings()
    database_url = settings.database_url or settings.direct_url
    if not database_url:
        raise GoldRunError("database_url_required")
    artifacts = load_gold_artifacts(
        arguments.dataset,
        arguments.source_bank,
        arguments.approval_manifest,
        arguments.adjudication_manifest,
    )
    code_provenance = _current_code_provenance()
    backend = PostgresExperimentDBackend(database_url)
    try:
        return await run_and_publish_approved_gold(
            artifacts,
            backend,
            lambda: _embedder_factory(settings),
            arguments.output_dir,
            batch_size=arguments.embedding_batch_size,
            code_provenance=code_provenance,
        )
    finally:
        await backend.close()


def _error_payload(error: BaseException) -> dict[str, object]:
    if isinstance(error, GoldRunError):
        return {
            "status": "failed",
            "error_code": error.code,
            "details": error.details,
            "result_written": False,
        }
    return {
        "status": "failed",
        "error_code": "experiment_d_run_failed",
        "error_type": type(error).__name__,
        "result_written": False,
    }


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")
    try:
        published = asyncio.run(_run(_arguments()))
    except KeyboardInterrupt, SystemExit:
        raise
    except BaseException as error:
        print(json.dumps(_error_payload(error), ensure_ascii=False, indent=2), file=sys.stderr)
        raise SystemExit(2) from error
    print(
        json.dumps(
            {
                "status": "completed",
                "run_id": published.payload["run_id"],
                "result_path": str(published.path.resolve()),
                "result_file_sha256": published.file_sha256,
                "metric_payload_sha256": published.payload["metric_payload_sha256"],
                "retrieval_observation_sha256": published.payload["retrieval_observation_sha256"],
                "retrieval_state_fingerprint_sha256": published.payload["inputs"][
                    "retrieval_state_fingerprint_sha256"
                ],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


__all__ = [
    "CorpusSnapshot",
    "DenseCandidate",
    "GoldRunArtifacts",
    "GoldRunError",
    "PostgresExperimentDBackend",
    "PublishedGoldRun",
    "evaluate_approved_gold",
    "load_gold_artifacts",
    "run_and_publish_approved_gold",
    "validate_gold_artifacts",
]
