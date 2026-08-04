"""Fail-closed, read-only checks before a maintenance corpus publish."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from law_rag_core.corpus_update_bundle import (
    canonical_corpus_publish_snapshot_id,
    canonical_corpus_snapshot_id,
    load_corpus_update_bundle,
)
from law_rag_core.domain.identifiers import PARSER_SCHEMA_VERSION
from law_rag_core.persistence import (
    CORPUS_PUBLISH_BASE_SELECT_SQL,
    CORPUS_SEARCH_READY_CAPABILITY_SQL,
    CORPUS_SEARCH_READY_FLAG_KEY,
    CORPUS_SEARCH_READY_SQL,
    LEGAL_PROVISION_V1_SOURCE_SHA_SQL,
    SEARCHABLE_DOCUMENT_VERSION_SQL,
)
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine, create_async_engine
from sqlalchemy.pool import NullPool

EXPECTED_MIGRATION_HEAD = "0011"
EXPECTED_PROFILE = {
    "profile_key": "nvidia-nemotron-3-embed-1b-512-v1",
    "provider": "nvidia",
    "model": "nvidia/nemotron-3-embed-1b",
    "native_dimensions": 2048,
    "stored_dimensions": 512,
    "document_input_type": "passage",
    "query_input_type": "query",
    "truncation": "first_512",
    "normalization": "l2",
    "text_template_version": "legal-provision-v1",
    "profile_version": "1",
    "active": True,
}
_KST = timezone(timedelta(hours=9), name="Asia/Seoul")


class CorpusPreflightSettings(BaseSettings):
    """The preflight intentionally needs only a direct PostgreSQL session URL."""

    model_config = SettingsConfigDict(
        env_file=(".env", ".env.local"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    direct_url: str | None = None


class CorpusPreflightError(RuntimeError):
    """Raised when the current DB cannot safely serve as a publish baseline."""


def _async_url(url: str) -> str:
    if url.startswith("postgresql+asyncpg://"):
        return url
    return url.replace("postgresql://", "postgresql+asyncpg://", 1)


def _json_value(value: object) -> object:
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return value


def _mapping(row: Mapping[str, Any]) -> dict[str, object]:
    return {str(key): _json_value(value) for key, value in row.items()}


async def _one(connection: AsyncConnection, sql: str, parameters=None) -> dict[str, object]:
    row = (await connection.execute(text(sql), parameters or {})).mappings().one()
    return _mapping(row)


async def _all(
    connection: AsyncConnection,
    sql: str,
    parameters=None,
) -> list[dict[str, object]]:
    rows = (await connection.execute(text(sql), parameters or {})).mappings().all()
    return [_mapping(row) for row in rows]


async def _read_state(connection: AsyncConnection, *, today: date) -> dict[str, object]:
    transaction = await _one(
        connection,
        """SELECT current_setting('transaction_isolation') transaction_isolation,
        current_setting('transaction_read_only') transaction_read_only,
        current_setting('statement_timeout') statement_timeout,
        current_setting('lock_timeout') lock_timeout""",
    )
    migration = await _one(
        connection,
        "SELECT version_num migration_head FROM alembic_version",
    )
    gate = await _one(
        connection,
        f"""SELECT {CORPUS_SEARCH_READY_CAPABILITY_SQL} capability_enabled,
        {CORPUS_SEARCH_READY_SQL} search_ready,
        COALESCE((SELECT value->>'reason' FROM runtime_flags
          WHERE key=:ready_key),'runtime_flag_missing') reason""",
        {"ready_key": CORPUS_SEARCH_READY_FLAG_KEY},
    )
    profiles = await _all(
        connection,
        """SELECT profile_key,provider,model,native_dimensions,stored_dimensions,
        document_input_type,query_input_type,truncation,normalization,
        text_template_version,profile_version,active
        FROM embedding_profiles WHERE active IS TRUE ORDER BY profile_key""",
    )
    coverage = await _one(
        connection,
        f"""WITH searchable AS MATERIALIZED (
          SELECT p.id,{LEGAL_PROVISION_V1_SOURCE_SHA_SQL} expected_source_sha256
          FROM provisions p
          JOIN document_versions v ON v.id=p.version_id
          JOIN legal_documents d ON d.id=v.document_id
          WHERE {SEARCHABLE_DOCUMENT_VERSION_SQL}
        )
        SELECT COUNT(*)::bigint searchable_provision_count,
          COUNT(e.provision_id)::bigint valid_profile_vector_count,
          COUNT(*) FILTER (WHERE e.provision_id IS NULL)::bigint missing_vector_count,
          COUNT(*) FILTER (WHERE e.provision_id IS NOT NULL
            AND (e.dimensions<>:dimensions OR vector_dims(e.embedding)<>:dimensions)
          )::bigint wrong_dimension_count,
          COUNT(*) FILTER (WHERE e.provision_id IS NOT NULL
            AND e.source_text_sha256<>s.expected_source_sha256
          )::bigint source_sha_mismatch_count,
          COUNT(*) FILTER (WHERE e.provision_id IS NOT NULL
            AND (vector_norm(e.embedding) IS NULL
              OR abs(vector_norm(e.embedding)-1.0)>0.0001)
          )::bigint non_unit_vector_count
        FROM searchable s
        LEFT JOIN provision_embeddings e
          ON e.provision_id=s.id AND e.profile_key=:profile_key""",
        {
            "profile_key": EXPECTED_PROFILE["profile_key"],
            "dimensions": EXPECTED_PROFILE["stored_dimensions"],
        },
    )
    publish_rows = await _all(
        connection,
        f"""SELECT {CORPUS_PUBLISH_BASE_SELECT_SQL}
        FROM provisions p
        JOIN document_versions v ON v.id=p.version_id
        JOIN legal_documents d ON d.id=v.document_id
        WHERE {SEARCHABLE_DOCUMENT_VERSION_SQL}
        ORDER BY p.id""",
    )
    temporal = await _one(
        connection,
        f"""WITH collected AS MATERIALIZED (
          SELECT p.id provision_id,p.version_id,d.id document_id,
            d.exact_title document_title,d.source_kind,
            v.effective_from,v.effective_to,p.path,p.parent_path,p.heading,
            encode(digest(p.content,'sha256'),'hex') content_sha256
          FROM provisions p
          JOIN document_versions v ON v.id=p.version_id
          JOIN legal_documents d ON d.id=v.document_id
          WHERE {SEARCHABLE_DOCUMENT_VERSION_SQL}
        ), eligible AS MATERIALIZED (
          SELECT * FROM collected
          WHERE effective_from<=:today
            AND (effective_to IS NULL OR effective_to>:today)
        )
        SELECT (SELECT MIN(effective_from) FROM collected
                 WHERE effective_from<=:today) supported_as_of_from,
          CAST(:today AS date) supported_as_of_through,
          COUNT(*)::bigint eligible_provision_count,
          encode(digest(
            COALESCE(jsonb_agg(jsonb_build_array(
              '{PARSER_SCHEMA_VERSION}',document_id::text,version_id::text,
              provision_id::text,document_title,source_kind::text,
              effective_from::text,path,parent_path,heading,content_sha256
            ) ORDER BY provision_id),'[]'::jsonb)::text,
            'sha256'
          ),'hex') fingerprint_sha256
        FROM eligible""",
        {"today": today},
    )
    return {
        "transaction": transaction,
        "migration": migration,
        "gate": gate,
        "profiles": profiles,
        "coverage": coverage,
        "publish_rows": publish_rows,
        "temporal": temporal,
    }


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise CorpusPreflightError(message)


def _validated_report(
    state: Mapping[str, object],
    *,
    today: date,
    bundle_path: Path | None,
) -> dict[str, object]:
    transaction = dict(state["transaction"])  # type: ignore[arg-type]
    _require(
        transaction.get("transaction_isolation") == "repeatable read",
        "transaction isolation is not repeatable read",
    )
    _require(transaction.get("transaction_read_only") == "on", "transaction is not read only")

    migration = dict(state["migration"])  # type: ignore[arg-type]
    _require(
        migration.get("migration_head") == EXPECTED_MIGRATION_HEAD,
        "database migration head is not 0011",
    )

    gate = dict(state["gate"])  # type: ignore[arg-type]
    _require(gate.get("capability_enabled") is True, "corpus readiness capability is missing")
    _require(gate.get("search_ready") is True, "corpus search gate is closed")

    profiles = list(state["profiles"])  # type: ignore[arg-type]
    _require(len(profiles) == 1, "exactly one embedding profile must be active")
    profile = dict(profiles[0])
    _require(
        profile == EXPECTED_PROFILE,
        "active embedding profile does not match the NVIDIA 512D contract",
    )

    coverage = dict(state["coverage"])  # type: ignore[arg-type]
    searchable_count = int(coverage["searchable_provision_count"])
    valid_vector_count = int(coverage["valid_profile_vector_count"])
    _require(searchable_count > 0, "there are no searchable provisions")
    _require(valid_vector_count == searchable_count, "active vector coverage is incomplete")
    for key in (
        "missing_vector_count",
        "wrong_dimension_count",
        "source_sha_mismatch_count",
        "non_unit_vector_count",
    ):
        _require(int(coverage[key]) == 0, f"{key} must be zero")

    publish_rows = list(state["publish_rows"])  # type: ignore[arg-type]
    _require(
        len(publish_rows) == searchable_count, "publisher snapshot population differs from coverage"
    )
    publisher_snapshot_id = canonical_corpus_publish_snapshot_id(publish_rows)

    temporal = dict(state["temporal"])  # type: ignore[arg-type]
    eligible_count = int(temporal["eligible_provision_count"])
    fingerprint = str(temporal["fingerprint_sha256"])
    _require(eligible_count > 0, "there are no provisions effective today")
    _require(temporal.get("supported_as_of_from") is not None, "supported start date is missing")
    _require(
        temporal.get("supported_as_of_through") == today.isoformat(),
        "supported end date is not today",
    )
    _require(len(fingerprint) == 64, "runtime corpus fingerprint is invalid")
    runtime_snapshot_id = canonical_corpus_snapshot_id(
        parser_contract_version=PARSER_SCHEMA_VERSION,
        retrieval_unit="provision",
        content_populations=[
            {
                "eligible_provision_count": eligible_count,
                "fingerprint_sha256": fingerprint,
            }
        ],
    )

    bundle_report: dict[str, object] = {"present": False}
    if bundle_path is not None:
        bundle = load_corpus_update_bundle(bundle_path, expected_state="ready_to_publish")
        matches = bundle.manifest.base_snapshot_id == publisher_snapshot_id
        _require(matches, "prepared bundle base snapshot does not match the database")
        bundle_report = {
            "present": True,
            "state": bundle.manifest.state,
            "update_id": bundle.manifest.update_id,
            "bundle_sha256": bundle.manifest.bundle_sha256,
            "base_snapshot_id": bundle.manifest.base_snapshot_id,
            "base_snapshot_matches": matches,
        }

    return {
        "state": "ready",
        "checked_as_of_kst": today.isoformat(),
        "transaction": transaction,
        "migration": {
            "expected_head": EXPECTED_MIGRATION_HEAD,
            "current_head": migration["migration_head"],
        },
        "corpus_gate": gate,
        "embedding_profile": profile,
        "coverage": coverage,
        "publisher_snapshot": {
            "snapshot_id": publisher_snapshot_id,
            "searchable_provision_count": searchable_count,
        },
        "runtime_corpus": {
            "corpus_snapshot_id": runtime_snapshot_id,
            "supported_as_of_from": temporal["supported_as_of_from"],
            "supported_as_of_through": temporal["supported_as_of_through"],
            "eligible_provision_count": eligible_count,
            "fingerprint_sha256": fingerprint,
        },
        "bundle": bundle_report,
    }


async def preflight_current_corpus(
    database_url: str,
    *,
    bundle_path: Path | None = None,
    today: date | None = None,
    engine: AsyncEngine | None = None,
) -> dict[str, object]:
    """Inspect production corpus state without locks, writes, or external APIs."""

    if not database_url:
        raise ValueError("DIRECT_URL is required")
    owns_engine = engine is None
    selected_engine = engine or create_async_engine(
        _async_url(database_url),
        poolclass=NullPool,
        connect_args={"statement_cache_size": 0},
    )
    effective_today = today or datetime.now(_KST).date()
    try:
        async with selected_engine.connect() as connection:
            async with connection.begin():
                await connection.execute(
                    text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY")
                )
                await connection.execute(text("SET LOCAL statement_timeout = '15s'"))
                await connection.execute(text("SET LOCAL lock_timeout = '2s'"))
                state = await _read_state(connection, today=effective_today)
        return _validated_report(
            state,
            today=effective_today,
            bundle_path=bundle_path,
        )
    finally:
        if owns_engine:
            await selected_engine.dispose()


__all__ = [
    "CorpusPreflightError",
    "CorpusPreflightSettings",
    "EXPECTED_MIGRATION_HEAD",
    "EXPECTED_PROFILE",
    "preflight_current_corpus",
]
