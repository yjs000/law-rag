import hashlib
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

import law_rag_collector.prepared_publisher as publisher_module
from law_rag_collector.prepared_publisher import publish_prepared_bundle

_PROFILE_KEY = "nvidia-nemotron-3-embed-1b-512-v1"


def test_publish_batches_are_capped_at_one_hundred_rows() -> None:
    assert [len(batch) for batch in publisher_module._chunks(list(range(201)))] == [100, 100, 1]


def _bundle(
    tmp_path,
    *,
    changed: bool = True,
    ready: bool = True,
    profile_key: str = _PROFILE_KEY,
    dimensions: int = 512,
    vector: list[float] | None = None,
    source_text_sha256: str | None = None,
):
    raw_body = "{}"
    raw_sha256 = hashlib.sha256(raw_body.encode()).hexdigest()
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
        changed=changed,
    )
    passage = "\n".join(
        [document.title, "제7조/항①", "사업의 허가", "전기사업자는 허가를 받아야 한다."]
    )
    bundle = write_corpus_update_bundle(
        tmp_path / "bundle",
        update_id="update-1",
        documents=[document],
        deletions=[],
        raw_contents={raw.path: raw_body},
        base_snapshot_id=f"corpus-sha256:{'0' * 64}",
        parser_version=PARSER_SCHEMA_VERSION,
        embedding_profile_key=profile_key,
        required_embedding_ids=[provision_id] if changed else [],
        deletion_window=(date(2026, 8, 3), date(2026, 8, 4)),
        created_at=datetime(2026, 8, 4, tzinfo=UTC),
    )
    if changed and ready:
        bundle = finalize_corpus_update_bundle(
            bundle.root,
            [
                PreparedEmbeddingRecord(
                    provision_id=provision_id,
                    embedding_profile_key=profile_key,
                    dimensions=dimensions,
                    source_text_sha256=(
                        source_text_sha256
                        or hashlib.sha256(passage.encode("utf-8")).hexdigest()
                    ),
                    embedding=vector or ([1.0] + [0.0] * (dimensions - 1)),
                )
            ],
        )
    return bundle


class _Result:
    def __init__(self, scalar=True) -> None:
        self.scalar = scalar

    def scalar_one(self):
        return self.scalar

    def mappings(self):
        return self

    def one(self):
        return {"capability_ready": True, "ready": True, "reason": "ready"}


class _Transaction:
    def __init__(self, connection) -> None:
        self.connection = connection

    async def __aenter__(self):
        self.connection.active_transactions += 1
        return self.connection

    async def __aexit__(self, exc_type, *_):
        self.connection.active_transactions -= 1
        if exc_type is None:
            self.connection.commits += 1
        else:
            self.connection.rollbacks += 1


class _Connection:
    def __init__(self) -> None:
        self.commits = 0
        self.explicit_commits = 0
        self.rollbacks = 0
        self.active_transactions = 0
        self.statements: list[str] = []

    async def execute(self, statement, _params=None):
        self.statements.append(str(statement))
        return _Result()

    async def commit(self):
        self.explicit_commits += 1

    def begin(self):
        return _Transaction(self)


class _Storage:
    def __init__(self) -> None:
        self.paths: list[str] = []

    async def put_immutable(self, path, _raw):
        self.paths.append(path)
        return f"law-raw/{path}"


class _Repository:
    bucket = "law-raw"

    def __init__(self, connection, *, lock_error: Exception | None = None) -> None:
        self.connection = connection
        self.storage = _Storage()
        self.lock_error = lock_error
        self.session_entered = 0
        self.session_exited = 0

    @asynccontextmanager
    async def prepared_publish_session(self):
        if self.lock_error is not None:
            raise self.lock_error
        self.session_entered += 1
        try:
            yield self.connection
        finally:
            self.session_exited += 1


@pytest.mark.asyncio
async def test_unchanged_bundle_exits_before_storage_lock_or_gate(tmp_path) -> None:
    bundle = _bundle(tmp_path, changed=False, ready=False)
    repository = _Repository(_Connection())

    result = await publish_prepared_bundle(repository, bundle.root)  # type: ignore[arg-type]

    assert result["state"] == "unchanged"
    assert repository.storage.paths == []
    assert repository.session_entered == 0


@pytest.mark.asyncio
async def test_base_snapshot_mismatch_fails_before_gate(monkeypatch, tmp_path) -> None:
    bundle = _bundle(tmp_path)
    repository = _Repository(_Connection())
    gate_events = []

    async def mismatch(_connection, _parser_version):
        return f"corpus-sha256:{'f' * 64}"

    async def set_gate(*_args, **kwargs):
        gate_events.append(kwargs["ready"])

    monkeypatch.setattr(publisher_module, "_set_corpus_search_ready", set_gate)
    with pytest.raises(RuntimeError, match="base snapshot"):
        await publish_prepared_bundle(
            repository,  # type: ignore[arg-type]
            bundle.root,
            snapshot_reader=mismatch,
        )

    assert gate_events == []
    assert repository.session_exited == 1


@pytest.mark.asyncio
async def test_incomplete_prospective_coverage_fails_before_gate(monkeypatch, tmp_path) -> None:
    bundle = _bundle(tmp_path)
    connection = _Connection()
    repository = _Repository(connection)
    gate_events = []

    async def same_snapshot(_connection, _parser_version):
        return bundle.manifest.base_snapshot_id

    async def incomplete(_connection, _bundle):
        raise RuntimeError("prospective embedding gaps")

    async def set_gate(*_args, **kwargs):
        gate_events.append(kwargs["ready"])

    monkeypatch.setattr(
        publisher_module, "_require_complete_prospective_embeddings", incomplete
    )
    monkeypatch.setattr(publisher_module, "_set_corpus_search_ready", set_gate)
    with pytest.raises(RuntimeError, match="prospective embedding gaps"):
        await publish_prepared_bundle(
            repository,  # type: ignore[arg-type]
            bundle.root,
            snapshot_reader=same_snapshot,
        )

    assert gate_events == []
    assert connection.commits == 0
    assert connection.rollbacks == 0


@pytest.mark.asyncio
async def test_publish_commits_gate_then_one_atomic_apply_transaction(
    monkeypatch, tmp_path
) -> None:
    bundle = _bundle(tmp_path)
    connection = _Connection()
    repository = _Repository(connection)
    gate_events: list[bool] = []
    sleeps: list[float] = []

    async def same_snapshot(_connection, _parser_version):
        return bundle.manifest.base_snapshot_id

    async def set_gate(_connection, *, ready, **_kwargs):
        gate_events.append(ready)

    async def apply(connection_arg, _repository, _bundle_arg, _uploaded):
        assert connection_arg.active_transactions == 1
        await publisher_module._set_corpus_search_ready(
            connection_arg,
            ready=True,
            reason="corpus_publish_verified",
        )
        return {"provision_count": 1, "embedding_count": 1}

    async def sleep(seconds):
        sleeps.append(seconds)

    async def complete(_connection, _bundle):
        return None

    monkeypatch.setattr(publisher_module, "_set_corpus_search_ready", set_gate)
    monkeypatch.setattr(publisher_module, "_apply_prepared_transaction", apply)
    monkeypatch.setattr(
        publisher_module, "_require_complete_prospective_embeddings", complete
    )
    result = await publish_prepared_bundle(
        repository,  # type: ignore[arg-type]
        bundle.root,
        sleeper=sleep,
        snapshot_reader=same_snapshot,
    )

    assert result["published"] is True
    assert gate_events == [False, True]
    assert sleeps == [65.0]
    assert connection.commits == 2
    assert connection.rollbacks == 0
    assert repository.session_exited == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "failed_stage",
    ("documents", "deletions", "vectors", "verification"),
)
async def test_each_apply_stage_failure_rolls_back_tx_b_and_keeps_gate_closed(
    monkeypatch, tmp_path, failed_stage
) -> None:
    bundle = _bundle(tmp_path)
    connection = _Connection()
    repository = _Repository(connection)
    gate_events: list[bool] = []

    async def same_snapshot(_connection, _parser_version):
        return bundle.manifest.base_snapshot_id

    async def set_gate(_connection, *, ready, **_kwargs):
        gate_events.append(ready)

    async def fail_apply(*_args, **_kwargs):
        raise RuntimeError(f"forced {failed_stage} failure")

    async def no_sleep(_seconds):
        return None

    async def complete(_connection, _bundle):
        return None

    monkeypatch.setattr(publisher_module, "_set_corpus_search_ready", set_gate)
    monkeypatch.setattr(publisher_module, "_apply_prepared_transaction", fail_apply)
    monkeypatch.setattr(
        publisher_module, "_require_complete_prospective_embeddings", complete
    )
    with pytest.raises(RuntimeError, match=rf"forced {failed_stage} failure"):
        await publish_prepared_bundle(
            repository,  # type: ignore[arg-type]
            bundle.root,
            sleeper=no_sleep,
            snapshot_reader=same_snapshot,
        )

    assert gate_events == [False]
    assert connection.commits == 1
    assert connection.rollbacks == 1
    assert repository.session_exited == 1


@pytest.mark.asyncio
async def test_writer_lock_failure_does_not_close_gate(monkeypatch, tmp_path) -> None:
    bundle = _bundle(tmp_path)
    repository = _Repository(_Connection(), lock_error=RuntimeError("writer busy"))
    gate_events = []

    async def set_gate(*_args, **kwargs):
        gate_events.append(kwargs["ready"])

    monkeypatch.setattr(publisher_module, "_set_corpus_search_ready", set_gate)
    with pytest.raises(RuntimeError, match="writer busy"):
        await publish_prepared_bundle(repository, bundle.root)  # type: ignore[arg-type]

    assert gate_events == []


@pytest.mark.asyncio
async def test_wrong_profile_fails_before_storage_lock_or_gate(tmp_path) -> None:
    bundle = _bundle(tmp_path, profile_key="unexpected-profile")
    repository = _Repository(_Connection())

    with pytest.raises(ValueError, match="profile"):
        await publish_prepared_bundle(repository, bundle.root)  # type: ignore[arg-type]

    assert repository.storage.paths == []
    assert repository.session_entered == 0


@pytest.mark.parametrize(
    ("bundle_kwargs", "message"),
    [
        ({"dimensions": 2, "vector": [1.0, 0.0]}, "512 stored dimensions"),
        ({"vector": [2.0] + [0.0] * 511}, "L2-normalized"),
    ],
)
def test_invalid_vector_is_rejected_before_storage_lock_or_gate(
    tmp_path, bundle_kwargs, message
) -> None:
    repository = _Repository(_Connection())

    with pytest.raises(ValueError, match=message):
        _bundle(tmp_path, **bundle_kwargs)

    assert repository.storage.paths == []
    assert repository.session_entered == 0


@pytest.mark.asyncio
async def test_tampered_bundle_fails_before_storage_lock_or_gate(tmp_path) -> None:
    bundle = _bundle(tmp_path)
    repository = _Repository(_Connection())
    documents = bundle.root / "documents.jsonl"
    documents.write_text(documents.read_text(encoding="utf-8") + "\n", encoding="utf-8")

    with pytest.raises(ValueError, match="checksum"):
        await publish_prepared_bundle(repository, bundle.root)  # type: ignore[arg-type]

    assert repository.storage.paths == []
    assert repository.session_entered == 0


@pytest.mark.asyncio
async def test_publish_verification_rejects_temporal_or_parser_violation(tmp_path) -> None:
    bundle = _bundle(tmp_path)

    class TemporalResult:
        def mappings(self):
            return self

        def one(self):
            return {
                "invalid_period_count": 0,
                "parser_mismatch_count": 1,
                "duplicate_open_count": 0,
                "overlap_count": 0,
            }

    class Connection:
        async def execute(self, statement, _params=None):
            assert "candidate_versions" in str(statement)
            return TemporalResult()

    with pytest.raises(RuntimeError, match="temporal or parser"):
        await publisher_module._verify_publish_state(Connection(), bundle)  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_publish_verification_requires_currently_eligible_provisions(tmp_path) -> None:
    bundle = _bundle(tmp_path)

    class TemporalResult:
        def mappings(self):
            return self

        def one(self):
            return {
                "invalid_period_count": 0,
                "parser_mismatch_count": 0,
                "duplicate_open_count": 0,
                "overlap_count": 0,
                "current_eligible_provision_count": 0,
                "supported_from": None,
            }

    class Connection:
        async def execute(self, statement, _params=None):
            assert "current_population" in str(statement)
            return TemporalResult()

    with pytest.raises(RuntimeError, match="no currently eligible"):
        await publisher_module._verify_publish_state(Connection(), bundle)  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_publishable_gate_allows_recovery_from_previous_publish_failure() -> None:
    class GateResult:
        def mappings(self):
            return self

        def one(self):
            return {
                "capability_ready": True,
                "ready": False,
                "reason": "corpus_publish",
            }

    class Connection:
        async def execute(self, _statement, _params=None):
            return GateResult()

    await publisher_module._require_publishable_gate(Connection())  # type: ignore[arg-type]


@pytest.mark.asyncio
@pytest.mark.parametrize("database_already_fixed", [False, True])
async def test_prospective_coverage_accepts_exact_required_bundle_embedding(
    tmp_path, database_already_fixed
) -> None:
    bundle = _bundle(tmp_path)
    document = bundle.documents[0]
    provision = document.provisions[0]
    prepared = bundle.embeddings[0]

    class RowsResult:
        def mappings(self):
            return self

        def all(self):
            return [
                {
                    "provision_id": provision.id,
                    "source_kind": document.source_kind.value,
                    "source_id": document.source_id,
                    "mst": document.mst,
                    "effective_from": document.effective_from,
                    "document_title": document.title,
                    "path": provision.path,
                    "heading": provision.heading,
                    "content": provision.content,
                    "stored_sha256": (
                        prepared.source_text_sha256 if database_already_fixed else None
                    ),
                    "stored_dimensions": 512 if database_already_fixed else None,
                    "stored_norm": 1.0 if database_already_fixed else None,
                }
            ]

    class Connection:
        async def execute(self, _statement, _params=None):
            return RowsResult()

    await publisher_module._require_complete_prospective_embeddings(
        Connection(),  # type: ignore[arg-type]
        bundle,
    )
