"""Opt-in transaction test for a dedicated empty PostgreSQL database."""

import hashlib
import os
from contextlib import asynccontextmanager
from datetime import UTC, date, datetime
from uuid import uuid4

import pytest
from law_rag_core.corpus_update_bundle import (
    PreparedDocumentRecord,
    PreparedEmbeddingRecord,
    PreparedProvisionRecord,
    PreparedRawRecord,
    finalize_corpus_update_bundle,
    write_corpus_update_bundle,
)
from law_rag_core.domain.catalog import SourceKind
from law_rag_core.domain.identifiers import PARSER_SCHEMA_VERSION
from law_rag_core.persistence import (
    CORPUS_SYNC_RUN_LOCK_KEY,
    EMBEDDING_BACKFILL_LOCK_KEY,
)
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

import law_rag_collector.prepared_publisher as publisher_module
from law_rag_collector.prepared_publisher import publish_prepared_bundle
from law_rag_collector.supabase_repository import SupabaseCurrentCorpusRepository

DATABASE_URL = os.getenv("CORPUS_PUBLISH_TEST_DATABASE_URL")

pytestmark = pytest.mark.skipif(
    not DATABASE_URL,
    reason=(
        "CORPUS_PUBLISH_TEST_DATABASE_URL이 설정된 빈 PostgreSQL 통합 gate에서만 실행"
    ),
)

_PROFILE_KEY = "nvidia-nemotron-3-embed-1b-512-v1"


def _async_url(value: str) -> str:
    return value.replace("postgresql://", "postgresql+asyncpg://", 1)


class _Storage:
    async def put_immutable(self, path, _raw):
        return f"law-raw/{path}"

    async def close(self):
        return None


def _bundle(tmp_path):
    body = "{}"
    raw_sha256 = hashlib.sha256(body.encode()).hexdigest()
    provision_id = uuid4()
    raw = PreparedRawRecord(
        path="raw/law-001.json",
        sha256=raw_sha256,
        wire_format="JSON",
        source_url="https://example.test/law",
    )
    document = PreparedDocumentRecord(
        source_id="001",
        mst="100",
        title="전기사업법",
        source_kind=SourceKind.LAW,
        effective_from=date(2026, 1, 1),
        source_url=raw.source_url,
        raw_format="JSON",
        raw_sha256=raw_sha256,
        parser_schema_version=PARSER_SCHEMA_VERSION,
        raw=raw,
        provisions=[
            PreparedProvisionRecord(
                id=provision_id,
                path="제7조/항①",
                heading="사업의 허가",
                content="전기사업자는 허가를 받아야 한다.",
                ordinal=1,
            )
        ],
        changed=True,
    )
    passage = "\n".join(
        [document.title, "제7조/항①", "사업의 허가", "전기사업자는 허가를 받아야 한다."]
    )
    prepared = write_corpus_update_bundle(
        tmp_path / "bundle",
        update_id="postgres-update",
        documents=[document],
        deletions=[],
        raw_contents={raw.path: body},
        base_snapshot_id=f"corpus-sha256:{'0' * 64}",
        parser_version=PARSER_SCHEMA_VERSION,
        embedding_profile_key=_PROFILE_KEY,
        required_embedding_ids=[provision_id],
        deletion_window=(date(2026, 8, 4), date(2026, 8, 4)),
        created_at=datetime(2026, 8, 4, tzinfo=UTC),
    )
    return finalize_corpus_update_bundle(
        prepared.root,
        [
            PreparedEmbeddingRecord(
                provision_id=provision_id,
                embedding_profile_key=_PROFILE_KEY,
                dimensions=512,
                source_text_sha256=hashlib.sha256(passage.encode()).hexdigest(),
                embedding=[1.0] + [0.0] * 511,
            )
        ],
    )


@asynccontextmanager
async def _isolated_repository():
    assert DATABASE_URL is not None
    schema = f"corpus_publish_test_{uuid4().hex}"
    admin = create_async_engine(_async_url(DATABASE_URL))
    async with admin.begin() as connection:
        await connection.execute(text(f'CREATE SCHEMA "{schema}"'))
        await connection.execute(
            text(
                f'''CREATE TABLE "{schema}".runtime_flags(
                key text PRIMARY KEY,value jsonb NOT NULL,
                updated_at timestamptz NOT NULL DEFAULT now())'''
            )
        )
        await connection.execute(
            text(f'CREATE TABLE "{schema}".publish_test_rows(stage text NOT NULL)')
        )
        await connection.execute(
            text(
                f'''INSERT INTO "{schema}".runtime_flags(key,value) VALUES
                ('schema.corpus_search_ready_v1',jsonb_build_object('enabled', true)),
                ('corpus.search_ready',jsonb_build_object(
                    'ready', true,
                    'reason', 'ready'
                ))'''
            )
        )
    engine = create_async_engine(
        _async_url(DATABASE_URL),
        connect_args={"server_settings": {"search_path": schema}},
    )
    repository = SupabaseCurrentCorpusRepository(
        database_url=DATABASE_URL,
        supabase_url="https://prepared-publish.invalid",
        supabase_secret_key="unused",
        bucket="law-raw",
        engine=engine,
        storage=_Storage(),  # type: ignore[arg-type]
    )
    try:
        yield repository, engine
    finally:
        await engine.dispose()
        async with admin.begin() as connection:
            await connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        await admin.dispose()


async def _no_sleep(_seconds):
    return None


async def _complete(_connection, _bundle):
    return None


async def _assert_writer_locks_released(engine) -> None:
    async with engine.connect() as connection:
        for lock_key in (EMBEDDING_BACKFILL_LOCK_KEY, CORPUS_SYNC_RUN_LOCK_KEY):
            acquired = (
                await connection.execute(
                    text("SELECT pg_try_advisory_lock(:lock_key)"),
                    {"lock_key": lock_key},
                )
            ).scalar_one()
            assert acquired is True
            await connection.execute(
                text("SELECT pg_advisory_unlock(:lock_key)"),
                {"lock_key": lock_key},
            )


@pytest.mark.asyncio
async def test_postgres_publish_commits_tx_b_and_reopens_gate(monkeypatch, tmp_path) -> None:
    bundle = _bundle(tmp_path)

    async def same_snapshot(_connection, _parser_version):
        return bundle.manifest.base_snapshot_id

    async def apply(connection, _repository, bundle_arg, _uploaded):
        await connection.execute(
            text("INSERT INTO publish_test_rows(stage) VALUES('verified')")
        )
        await publisher_module._set_corpus_search_ready(
            connection,
            ready=True,
            reason="corpus_publish_verified",
            update_id=bundle_arg.manifest.update_id,
        )
        return {"provision_count": 1, "embedding_count": 1}

    monkeypatch.setattr(
        publisher_module,
        "_require_complete_prospective_embeddings",
        _complete,
    )
    monkeypatch.setattr(publisher_module, "_apply_prepared_transaction", apply)
    async with _isolated_repository() as (repository, engine):
        await publish_prepared_bundle(
            repository,
            bundle.root,
            sleeper=_no_sleep,
            snapshot_reader=same_snapshot,
        )

        async with engine.connect() as connection:
            assert (
                await connection.execute(text("SELECT count(*) FROM publish_test_rows"))
            ).scalar_one() == 1
            assert (
                await connection.execute(
                    text(
                        "SELECT (value->>'ready')::boolean FROM runtime_flags "
                        "WHERE key='corpus.search_ready'"
                    )
                )
            ).scalar_one() is True
        await _assert_writer_locks_released(engine)


@pytest.mark.asyncio
@pytest.mark.parametrize("failed_stage", ("documents", "deletions", "vectors", "verification"))
async def test_postgres_each_stage_failure_rolls_back_tx_b_and_leaves_gate_closed(
    monkeypatch, tmp_path, failed_stage
) -> None:
    bundle = _bundle(tmp_path)

    async def same_snapshot(_connection, _parser_version):
        return bundle.manifest.base_snapshot_id

    async def fail_apply(connection, _repository, _bundle_arg, _uploaded):
        await connection.execute(
            text("INSERT INTO publish_test_rows(stage) VALUES(:stage)"),
            {"stage": failed_stage},
        )
        raise RuntimeError(f"forced {failed_stage} failure")

    monkeypatch.setattr(
        publisher_module,
        "_require_complete_prospective_embeddings",
        _complete,
    )
    monkeypatch.setattr(publisher_module, "_apply_prepared_transaction", fail_apply)
    async with _isolated_repository() as (repository, engine):
        with pytest.raises(RuntimeError, match=rf"forced {failed_stage} failure"):
            await publish_prepared_bundle(
                repository,
                bundle.root,
                sleeper=_no_sleep,
                snapshot_reader=same_snapshot,
            )

        async with engine.connect() as connection:
            assert (
                await connection.execute(text("SELECT count(*) FROM publish_test_rows"))
            ).scalar_one() == 0
            assert (
                await connection.execute(
                    text(
                        "SELECT (value->>'ready')::boolean FROM runtime_flags "
                        "WHERE key='corpus.search_ready'"
                    )
                )
            ).scalar_one() is False
        await _assert_writer_locks_released(engine)
