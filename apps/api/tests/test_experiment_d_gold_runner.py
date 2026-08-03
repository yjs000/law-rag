from __future__ import annotations

import copy
import hashlib
import json
from collections.abc import Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass, replace
from datetime import UTC, date, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest
from law_rag_core.persistence import CORPUS_MUTATION_LOCK_KEY

import scripts.evaluate_experiment_d_gold as runner
from app.domain.schemas import CorpusSearchStatus
from scripts.evaluate_experiment_d_gold import (
    CorpusSnapshot,
    DenseCandidate,
    GoldRunArtifacts,
    GoldRunError,
    PostgresExperimentDBackend,
    RetrievalState,
    run_and_publish_approved_gold,
    validate_gold_artifacts,
)
from scripts.preflight_experiment_d_gold import corpus_fingerprint_sha256
from tests import test_experiment_d_gold_contract as gold_fixture
from tests import test_experiment_d_gold_preflight as preflight_fixture

UNIT_VECTOR = [1.0, *([0.0] * 511)]
TEST_CODE_PROVENANCE = {
    "git_commit": "b" * 40,
    "critical_code_dirty": False,
    "critical_file_sha256": {path.as_posix(): "a" * 64 for path in runner.CRITICAL_CODE_PATHS},
}


def _retrieval_state(
    vector_count: int,
    *,
    transaction_isolation: str = "repeatable read",
) -> RetrievalState:
    return RetrievalState(
        profile={
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
        },
        vector_count=vector_count,
        non_unit_vector_count=0,
        vector_fingerprint_sha256="c" * 64,
        hnsw_index={
            "index_oid": "12345",
            "index_relfilenode": "67890",
            "index_size_bytes": 16384,
            "index_name": "provision_embeddings_nemotron_512_hnsw",
            "indexed_relation": "provision_embeddings",
            "key_attribute_count": 1,
            "access_method": "hnsw",
            "operator_class": "vector_cosine_ops",
            "indexed_type": "vector(512)",
            "index_expression": "(embedding)::vector(512)",
            "index_predicate": ("profile_key = 'nvidia-nemotron-3-embed-1b-512-v1'::text"),
            "index_valid": True,
            "index_ready": True,
            "contract_ready": True,
            "index_definition": (
                "CREATE INDEX provision_embeddings_nemotron_512_hnsw "
                "USING hnsw ((embedding::vector(512)) vector_cosine_ops) "
                "WHERE profile_key='nvidia-nemotron-3-embed-1b-512-v1'"
            ),
        },
        pgvector_version="0.8.1",
        retrieval_settings={
            "transaction_isolation": transaction_isolation,
            "transaction_read_only": "on",
            "postgresql_version": "17.5",
            "postgresql_version_num": "170005",
            "search_path": "pg_catalog, public, extensions, pg_temp",
            "enable_seqscan": "on",
            "enable_indexscan": "on",
            "enable_bitmapscan": "on",
            "random_page_cost": "4",
            "effective_cache_size": "4GB",
            "work_mem": "4MB",
        },
        state_fingerprint_sha256="d" * 64,
    )


@dataclass(frozen=True, slots=True)
class GoldFixtureBundle:
    artifacts: GoldRunArtifacts
    snapshot: CorpusSnapshot


@pytest.fixture(scope="module")
def gold_bundle() -> GoldFixtureBundle:
    dataset = gold_fixture._dataset()
    sources = preflight_fixture._full_contract_sources()
    source_bank = preflight_fixture._full_source_bank(dataset)
    approval_manifest = preflight_fixture._full_approval_manifest(source_bank)
    dataset["source_bank"]["approval_manifest_sha256"] = (
        preflight_fixture._approval_manifest_sha256(approval_manifest)
    )
    dataset["corpus_snapshot"]["searchable_provision_count"] = len(sources)
    dataset["corpus_snapshot"]["fingerprint_sha256"] = corpus_fingerprint_sha256(sources)
    adjudication_manifest = preflight_fixture._full_adjudication_manifest(dataset)
    artifacts = validate_gold_artifacts(
        dataset,
        source_bank,
        approval_manifest,
        adjudication_manifest,
    )
    return GoldFixtureBundle(
        artifacts=artifacts,
        snapshot=CorpusSnapshot(
            status=CorpusSearchStatus(ready=True),
            provisions=tuple(sources),
            retrieval_state=_retrieval_state(len(sources)),
        ),
    )


def _candidate(provision_id: str, score: float = 0.9) -> DenseCandidate:
    return DenseCandidate(
        provision_id=provision_id,
        document_id="document-1",
        document_title="전기사업법",
        source_kind="law",
        version_label="MST 1",
        effective_from=date(2026, 1, 1),
        effective_to=None,
        path="제1조",
        heading="목적",
        content=gold_fixture.CONTENT,
        source_url="https://open.law.go.kr/mock",
        score=score,
    )


class FakeEmbedder:
    def __init__(
        self,
        events: list[str],
        *,
        vector_factory: Callable[[], list[float]] = lambda: UNIT_VECTOR,
    ) -> None:
        self.events = events
        self.calls = 0
        self.vector_factory = vector_factory

    async def embed(self, texts: list[str]) -> list[list[float]]:
        self.calls += 1
        self.events.append(f"embed:{len(texts)}")
        return [self.vector_factory() for _ in texts]


class FakeLockedReader:
    def __init__(self, backend: FakeBackend) -> None:
        self.backend = backend

    async def snapshot(self) -> CorpusSnapshot:
        self.backend.events.append("locked_snapshot")
        return self.backend.locked_snapshot

    async def explain(
        self,
        *,
        as_of_date: date,
        query_embedding: list[float],
        limit: int,
    ) -> object:
        assert query_embedding == UNIT_VECTOR
        assert limit == 11
        self.backend.plan_count += 1
        self.backend.events.append(f"explain:{as_of_date.isoformat()}")
        return self.backend.query_plan

    async def search(
        self,
        *,
        as_of_date: date,
        query_embedding: list[float],
        limit: int,
    ) -> list[DenseCandidate]:
        del as_of_date
        assert query_embedding == UNIT_VECTOR
        assert limit == 11
        self.backend.search_count += 1
        index = self.backend.search_count
        self.backend.events.append(f"search:{index}")
        if self.backend.fail_search_at == index:
            raise RuntimeError("synthetic search failure")
        if self.backend.candidate_factory is not None:
            return self.backend.candidate_factory(index)
        return [_candidate(f"provision-{index}")]


class FakeBackend:
    def __init__(
        self,
        snapshot: CorpusSnapshot,
        *,
        locked_snapshot: CorpusSnapshot | None = None,
        lock_busy: bool = False,
        fail_search_at: int | None = None,
        candidate_factory: Callable[[int], list[DenseCandidate]] | None = None,
        query_plan: object | None = None,
        events: list[str] | None = None,
    ) -> None:
        self.initial_snapshot = snapshot
        self.locked_snapshot = locked_snapshot or replace(
            snapshot,
            retrieval_state=replace(
                snapshot.retrieval_state,
                retrieval_settings={
                    **snapshot.retrieval_state.retrieval_settings,
                    "transaction_isolation": "read committed",
                },
                state_fingerprint_sha256="e" * 64,
            ),
        )
        self.lock_busy = lock_busy
        self.fail_search_at = fail_search_at
        self.candidate_factory = candidate_factory
        self.query_plan = (
            query_plan
            if query_plan is not None
            else [
                {
                    "Plan": {
                        "Node Type": "Sort",
                        "Plans": [
                            {
                                "Node Type": "CTE Scan",
                                "CTE Name": "exact_eligible_distances",
                            }
                        ],
                    },
                }
            ]
        )
        self.events = events if events is not None else []
        self.lock_count = 0
        self.plan_count = 0
        self.search_count = 0

    async def snapshot(self) -> CorpusSnapshot:
        self.events.append("initial_snapshot")
        return self.initial_snapshot

    @asynccontextmanager
    async def locked_reader(self):
        self.events.append("lock_attempt")
        self.lock_count += 1
        if self.lock_busy:
            raise GoldRunError("corpus_mutation_in_progress")
        try:
            yield FakeLockedReader(self)
        finally:
            self.events.append("lock_release")


class PublisherSpy:
    def __init__(self, events: list[str]) -> None:
        self.events = events
        self.calls = 0
        self.payload: dict[str, object] | None = None

    def __call__(
        self,
        output_dir: Path,
        run_id: str,
        payload: dict[str, object],
    ) -> tuple[Path, str]:
        self.events.append("publish")
        self.calls += 1
        self.payload = payload
        return output_dir / f"{run_id}.json", "a" * 64


def _fixed_clock() -> Callable[[], datetime]:
    values = iter(
        (
            datetime(2026, 8, 3, 3, 0, tzinfo=UTC),
            datetime(2026, 8, 3, 3, 1, tzinfo=UTC),
        )
    )
    return lambda: next(values)


@pytest.mark.asyncio
async def test_cli_run_passes_all_four_gold_artifact_paths_to_loader(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    paths = {
        "dataset": tmp_path / "dataset.json",
        "source_bank": tmp_path / "source-bank.json",
        "approval_manifest": tmp_path / "question-approval.json",
        "adjudication_manifest": tmp_path / "gold-adjudication.json",
    }
    captured: list[Path] = []

    class ExpectedStop(RuntimeError):
        pass

    def stop_after_load(*artifact_paths: Path):
        captured.extend(artifact_paths)
        raise ExpectedStop

    monkeypatch.setattr(
        runner,
        "get_settings",
        lambda: SimpleNamespace(database_url="postgresql://example", direct_url=None),
    )
    monkeypatch.setattr(runner, "load_gold_artifacts", stop_after_load)
    arguments = SimpleNamespace(
        **paths,
        output_dir=tmp_path / "runs",
        embedding_batch_size=32,
    )

    with pytest.raises(ExpectedStop):
        await runner._run(arguments)

    assert captured == list(paths.values())


@pytest.mark.asyncio
async def test_invalid_code_provenance_stops_before_backend_or_embedder(
    gold_bundle: GoldFixtureBundle,
    tmp_path: Path,
) -> None:
    events: list[str] = []
    backend = FakeBackend(gold_bundle.snapshot, events=events)
    factory_calls = 0

    def factory() -> FakeEmbedder:
        nonlocal factory_calls
        factory_calls += 1
        return FakeEmbedder(events)

    with pytest.raises(GoldRunError) as raised:
        await run_and_publish_approved_gold(
            gold_bundle.artifacts,
            backend,
            factory,
            tmp_path,
            code_provenance={
                "git_commit": "b" * 40,
                "critical_code_dirty": False,
                "critical_file_sha256": {},
            },
            run_id_factory=lambda: "experiment-d-test-provenance-reject",
            clock=_fixed_clock(),
        )

    assert raised.value.code == "critical_code_hash_contract_invalid"
    assert events == []
    assert factory_calls == 0


@pytest.mark.asyncio
async def test_initial_preflight_rejection_creates_no_embedder_lock_search_or_output(
    gold_bundle: GoldFixtureBundle,
    tmp_path: Path,
) -> None:
    events: list[str] = []
    unready = CorpusSnapshot(
        status=CorpusSearchStatus(ready=False, reason="collector_corpus_change"),
        provisions=gold_bundle.snapshot.provisions,
        retrieval_state=gold_bundle.snapshot.retrieval_state,
    )
    backend = FakeBackend(unready, events=events)
    publisher = PublisherSpy(events)
    factory_calls = 0

    def factory() -> FakeEmbedder:
        nonlocal factory_calls
        factory_calls += 1
        return FakeEmbedder(events)

    with pytest.raises(GoldRunError) as raised:
        await run_and_publish_approved_gold(
            gold_bundle.artifacts,
            backend,
            factory,
            tmp_path,
            run_id_factory=lambda: "experiment-d-test-initial-reject",
            clock=_fixed_clock(),
            publisher=publisher,
            code_provenance=TEST_CODE_PROVENANCE,
        )

    assert raised.value.code == "initial_preflight_rejected"
    assert factory_calls == 0
    assert backend.lock_count == 0
    assert backend.search_count == 0
    assert publisher.calls == 0
    assert events == ["initial_snapshot"]


@pytest.mark.asyncio
async def test_invalid_embedding_stops_before_lock_search_and_output(
    gold_bundle: GoldFixtureBundle,
    tmp_path: Path,
) -> None:
    events: list[str] = []
    backend = FakeBackend(gold_bundle.snapshot, events=events)
    publisher = PublisherSpy(events)
    embedder = FakeEmbedder(events, vector_factory=lambda: [float("nan"), *([0.0] * 511)])

    with pytest.raises(GoldRunError) as raised:
        await run_and_publish_approved_gold(
            gold_bundle.artifacts,
            backend,
            lambda: embedder,
            tmp_path,
            run_id_factory=lambda: "experiment-d-test-invalid-vector",
            clock=_fixed_clock(),
            publisher=publisher,
            code_provenance=TEST_CODE_PROVENANCE,
        )

    assert raised.value.code == "query_embedding_nonfinite"
    assert embedder.calls == 1
    assert backend.lock_count == 0
    assert backend.search_count == 0
    assert publisher.calls == 0


@pytest.mark.asyncio
async def test_initial_retrieval_state_mismatch_stops_before_embedder(
    gold_bundle: GoldFixtureBundle,
    tmp_path: Path,
) -> None:
    events: list[str] = []
    invalid_snapshot = replace(
        gold_bundle.snapshot,
        retrieval_state=replace(
            gold_bundle.snapshot.retrieval_state,
            vector_count=len(gold_bundle.snapshot.provisions) - 1,
        ),
    )
    backend = FakeBackend(invalid_snapshot, events=events)
    publisher = PublisherSpy(events)
    factory_calls = 0

    def factory() -> FakeEmbedder:
        nonlocal factory_calls
        factory_calls += 1
        return FakeEmbedder(events)

    with pytest.raises(GoldRunError) as raised:
        await run_and_publish_approved_gold(
            gold_bundle.artifacts,
            backend,
            factory,
            tmp_path,
            run_id_factory=lambda: "experiment-d-test-retrieval-state-reject",
            clock=_fixed_clock(),
            publisher=publisher,
            code_provenance=TEST_CODE_PROVENANCE,
        )

    assert raised.value.code == "initial_retrieval_state_rejected"
    assert factory_calls == 0
    assert backend.lock_count == 0
    assert backend.search_count == 0
    assert publisher.calls == 0


@pytest.mark.asyncio
async def test_non_unit_passage_vector_stops_before_embedder(
    gold_bundle: GoldFixtureBundle,
    tmp_path: Path,
) -> None:
    events: list[str] = []
    invalid_snapshot = replace(
        gold_bundle.snapshot,
        retrieval_state=replace(
            gold_bundle.snapshot.retrieval_state,
            non_unit_vector_count=1,
        ),
    )
    backend = FakeBackend(invalid_snapshot, events=events)

    with pytest.raises(GoldRunError) as raised:
        await run_and_publish_approved_gold(
            gold_bundle.artifacts,
            backend,
            lambda: FakeEmbedder(events),
            tmp_path,
            code_provenance=TEST_CODE_PROVENANCE,
            run_id_factory=lambda: "experiment-d-test-passage-norm-reject",
            clock=_fixed_clock(),
        )

    assert raised.value.code == "initial_retrieval_state_rejected"
    assert "passage_embedding_not_l2_normalized" in raised.value.details["reasons"]
    assert backend.lock_count == 0
    assert backend.search_count == 0


@pytest.mark.asyncio
async def test_busy_corpus_lock_discards_embeddings_without_search_or_output(
    gold_bundle: GoldFixtureBundle,
    tmp_path: Path,
) -> None:
    events: list[str] = []
    backend = FakeBackend(gold_bundle.snapshot, lock_busy=True, events=events)
    publisher = PublisherSpy(events)
    embedder = FakeEmbedder(events)

    with pytest.raises(GoldRunError) as raised:
        await run_and_publish_approved_gold(
            gold_bundle.artifacts,
            backend,
            lambda: embedder,
            tmp_path,
            run_id_factory=lambda: "experiment-d-test-lock-busy",
            clock=_fixed_clock(),
            publisher=publisher,
            code_provenance=TEST_CODE_PROVENANCE,
        )

    assert raised.value.code == "corpus_mutation_in_progress"
    assert embedder.calls == 32
    assert backend.lock_count == 1
    assert backend.search_count == 0
    assert publisher.calls == 0
    assert "locked_snapshot" not in events
    assert "lock_release" not in events


@pytest.mark.asyncio
async def test_locked_preflight_rechecks_fresh_corpus_before_first_search(
    gold_bundle: GoldFixtureBundle,
    tmp_path: Path,
) -> None:
    changed = list(gold_bundle.snapshot.provisions)
    changed[0] = replace(changed[0], content="잠금 전에 바뀐 본문")
    locked_snapshot = CorpusSnapshot(
        status=CorpusSearchStatus(ready=True),
        provisions=tuple(changed),
        retrieval_state=gold_bundle.snapshot.retrieval_state,
    )
    events: list[str] = []
    backend = FakeBackend(
        gold_bundle.snapshot,
        locked_snapshot=locked_snapshot,
        events=events,
    )
    publisher = PublisherSpy(events)

    with pytest.raises(GoldRunError) as raised:
        await run_and_publish_approved_gold(
            gold_bundle.artifacts,
            backend,
            lambda: FakeEmbedder(events),
            tmp_path,
            run_id_factory=lambda: "experiment-d-test-locked-reject",
            clock=_fixed_clock(),
            publisher=publisher,
            code_provenance=TEST_CODE_PROVENANCE,
        )

    assert raised.value.code == "locked_preflight_rejected"
    assert backend.search_count == 0
    assert publisher.calls == 0
    assert events[-2:] == ["locked_snapshot", "lock_release"]


@pytest.mark.asyncio
async def test_search_failure_releases_lock_and_publishes_nothing(
    gold_bundle: GoldFixtureBundle,
    tmp_path: Path,
) -> None:
    events: list[str] = []
    backend = FakeBackend(gold_bundle.snapshot, fail_search_at=2, events=events)
    publisher = PublisherSpy(events)

    with pytest.raises(RuntimeError, match="synthetic search failure"):
        await run_and_publish_approved_gold(
            gold_bundle.artifacts,
            backend,
            lambda: FakeEmbedder(events),
            tmp_path,
            run_id_factory=lambda: "experiment-d-test-search-failure",
            clock=_fixed_clock(),
            publisher=publisher,
            code_provenance=TEST_CODE_PROVENANCE,
        )

    assert backend.search_count == 2
    assert events[-1] == "lock_release"
    assert publisher.calls == 0


@pytest.mark.asyncio
async def test_hnsw_access_path_stops_exact_search_before_output(
    gold_bundle: GoldFixtureBundle,
    tmp_path: Path,
) -> None:
    events: list[str] = []
    backend = FakeBackend(
        gold_bundle.snapshot,
        query_plan=[
            {
                "Plan": {
                    "Node Type": "Index Scan",
                    "Index Name": "provision_embeddings_nemotron_512_hnsw",
                }
            }
        ],
        events=events,
    )
    publisher = PublisherSpy(events)

    with pytest.raises(GoldRunError) as raised:
        await run_and_publish_approved_gold(
            gold_bundle.artifacts,
            backend,
            lambda: FakeEmbedder(events),
            tmp_path,
            code_provenance=TEST_CODE_PROVENANCE,
            run_id_factory=lambda: "experiment-d-test-exact-plan-reject",
            clock=_fixed_clock(),
            publisher=publisher,
        )

    assert raised.value.code == "hnsw_index_planned_for_exact_cosine"
    assert backend.plan_count >= 1
    assert backend.search_count == 0
    assert publisher.calls == 0
    assert events[-1] == "lock_release"


@pytest.mark.asyncio
async def test_equal_raw_scores_at_rank_10_and_11_fail_closed(
    gold_bundle: GoldFixtureBundle,
    tmp_path: Path,
) -> None:
    def tied_candidates(_index: int) -> list[DenseCandidate]:
        return [_candidate(f"tie-{rank:02d}", 1.0 - rank / 100) for rank in range(1, 10)] + [
            _candidate("tie-10", 0.5),
            _candidate("tie-11", 0.5),
        ]

    events: list[str] = []
    backend = FakeBackend(
        gold_bundle.snapshot,
        candidate_factory=tied_candidates,
        events=events,
    )
    publisher = PublisherSpy(events)

    with pytest.raises(GoldRunError) as raised:
        await run_and_publish_approved_gold(
            gold_bundle.artifacts,
            backend,
            lambda: FakeEmbedder(events),
            tmp_path,
            run_id_factory=lambda: "experiment-d-test-cutoff-tie",
            clock=_fixed_clock(),
            publisher=publisher,
            code_provenance=TEST_CODE_PROVENANCE,
        )

    assert raised.value.code == "unresolved_cutoff_tie"
    assert backend.search_count == 1
    assert events[-1] == "lock_release"
    assert publisher.calls == 0


@pytest.mark.asyncio
async def test_complete_fixture_searches_all_cases_then_publishes_metrics(
    gold_bundle: GoldFixtureBundle,
    tmp_path: Path,
) -> None:
    events: list[str] = []
    backend = FakeBackend(gold_bundle.snapshot, events=events)
    publisher = PublisherSpy(events)

    published = await run_and_publish_approved_gold(
        gold_bundle.artifacts,
        backend,
        lambda: FakeEmbedder(events),
        tmp_path,
        run_id_factory=lambda: "experiment-d-test-complete",
        clock=_fixed_clock(),
        publisher=publisher,
        code_provenance=TEST_CODE_PROVENANCE,
    )

    assert backend.search_count == 1000
    assert backend.plan_count >= 1
    assert publisher.calls == 1
    assert events.index("lock_release") < events.index("publish")
    assert published.payload["schema_version"] == 2
    assert published.payload["case_count"] == 1000
    assert published.payload["search_count"] == 1000
    assert published.payload["metrics"]["overall"]["recall_at_10"] == 1.0
    assert published.payload["metrics"]["overall"]["hit_rate_at_10"] == 1.0
    assert len(published.payload["cases"]) == 1000
    assert published.payload["payload_without_self_hash_sha256"]
    assert published.payload["metric_payload_sha256"]
    assert published.payload["retrieval_observation_sha256"]
    assert published.payload["retrieval_execution_mode"] == "exact_cosine"
    assert published.payload["retrieval_state"]["vector_count"] == 2000
    assert published.payload["query_plans"]
    assert published.payload["all_query_plans_exclude_hnsw"] is True
    assert all(
        plan["retrieval_execution_mode"] == "exact_cosine"
        and plan["forbidden_hnsw_index_used"] is False
        for plan in published.payload["query_plans"]
    )
    assert published.payload["inputs"]["retrieval_execution_mode"] == "exact_cosine"
    assert published.payload["inputs"]["query_plans_sha256"]


class _ScalarResult:
    def __init__(self, value: bool) -> None:
        self.value = value

    def scalar_one(self) -> bool:
        return self.value


class _LockConnection:
    def __init__(self, acquired: bool) -> None:
        self.acquired = acquired
        self.calls: list[tuple[str, dict[str, object]]] = []
        self.transaction_entries = 0
        self.transaction_exits = 0

    async def execute(self, statement, parameters=None):
        parameters = parameters or {}
        self.calls.append((str(statement), parameters))
        return _ScalarResult(self.acquired)

    def begin(self) -> _TransactionContext:
        return _TransactionContext(self)


class _TransactionContext:
    def __init__(self, connection: _LockConnection) -> None:
        self.connection = connection

    async def __aenter__(self) -> None:
        self.connection.transaction_entries += 1

    async def __aexit__(self, *_args) -> None:
        self.connection.transaction_exits += 1


class _ConnectionContext:
    def __init__(self, connection: _LockConnection) -> None:
        self.connection = connection

    async def __aenter__(self) -> _LockConnection:
        return self.connection

    async def __aexit__(self, *_args) -> None:
        return None


class _LockEngine:
    def __init__(self, connection: _LockConnection) -> None:
        self.connection = connection

    def connect(self) -> _ConnectionContext:
        return _ConnectionContext(self.connection)


@pytest.mark.asyncio
async def test_postgres_backend_uses_one_transaction_and_shared_mutation_key_for_lock() -> None:
    connection = _LockConnection(True)
    backend = PostgresExperimentDBackend.__new__(PostgresExperimentDBackend)
    backend.repository = type("Repository", (), {"engine": _LockEngine(connection)})()

    async with backend.locked_reader():
        pass

    assert connection.transaction_entries == 1
    assert connection.transaction_exits == 1
    assert len(connection.calls) == 3
    assert "SET TRANSACTION ISOLATION LEVEL READ COMMITTED, READ ONLY" in (connection.calls[0][0])
    assert "SET LOCAL search_path=pg_catalog,public,extensions,pg_temp" in (connection.calls[1][0])
    assert "pg_try_advisory_xact_lock_shared" in connection.calls[2][0]
    assert connection.calls[2][1] == {"lock_key": CORPUS_MUTATION_LOCK_KEY}


@pytest.mark.asyncio
async def test_postgres_backend_busy_xact_lock_does_not_enter_reader() -> None:
    connection = _LockConnection(False)
    backend = PostgresExperimentDBackend.__new__(PostgresExperimentDBackend)
    backend.repository = type("Repository", (), {"engine": _LockEngine(connection)})()

    with pytest.raises(GoldRunError) as raised:
        async with backend.locked_reader():
            raise AssertionError("reader must not be entered")

    assert raised.value.code == "corpus_mutation_in_progress"
    assert connection.transaction_entries == 1
    assert connection.transaction_exits == 1
    assert len(connection.calls) == 3
    assert "SET TRANSACTION ISOLATION LEVEL READ COMMITTED, READ ONLY" in (connection.calls[0][0])
    assert "SET LOCAL search_path=pg_catalog,public,extensions,pg_temp" in (connection.calls[1][0])
    assert "pg_try_advisory_xact_lock_shared" in connection.calls[2][0]


def test_atomic_publisher_rejects_nan_without_creating_output_directory(
    tmp_path: Path,
) -> None:
    output_dir = tmp_path / "runs"

    with pytest.raises(ValueError, match="Out of range float"):
        runner._atomic_publish(
            output_dir,
            "experiment-d-nan",
            {"score": float("nan")},
        )

    assert not output_dir.exists()


def test_atomic_publisher_cleans_temporary_file_when_atomic_link_fails(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    output_dir = tmp_path / "runs"
    output_dir.mkdir()
    previous = output_dir / "previous.json"
    previous.write_bytes(b"previous-result\n")

    def fail_link(_source: Path, _destination: Path) -> None:
        raise OSError("synthetic link failure")

    monkeypatch.setattr(runner.os, "link", fail_link)

    with pytest.raises(OSError, match="synthetic link failure"):
        runner._atomic_publish(
            output_dir,
            "experiment-d-replace-failure",
            {"status": "complete"},
        )

    assert previous.read_bytes() == b"previous-result\n"
    assert list(output_dir.iterdir()) == [previous]


def test_atomic_publisher_reports_success_if_temp_cleanup_fails_after_link(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    output_dir = tmp_path / "runs"
    original_unlink = Path.unlink

    def fail_temporary_unlink(path: Path, *args, **kwargs) -> None:
        if path.name.startswith(".experiment-d-cleanup-failure."):
            raise OSError("synthetic cleanup failure")
        original_unlink(path, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", fail_temporary_unlink)

    final_path, file_sha = runner._atomic_publish(
        output_dir,
        "experiment-d-cleanup-failure",
        {"status": "complete"},
    )

    assert final_path.exists()
    assert len(file_sha) == 64
    assert json.loads(final_path.read_text(encoding="utf-8")) == {"status": "complete"}


def test_atomic_publisher_never_overwrites_existing_run(tmp_path: Path) -> None:
    output_dir = tmp_path / "runs"
    output_dir.mkdir()
    existing = output_dir / "experiment-d-existing.json"
    existing.write_bytes(b"existing-result\n")

    with pytest.raises(GoldRunError) as raised:
        runner._atomic_publish(
            output_dir,
            "experiment-d-existing",
            {"status": "new-result"},
        )

    assert raised.value.code == "result_run_id_already_exists"
    assert existing.read_bytes() == b"existing-result\n"
    assert list(output_dir.iterdir()) == [existing]


def test_validate_artifacts_rejects_unlabelled_question_bank_before_any_backend() -> None:
    raw_bank = {
        "bank_version": "draft",
        "questions": [{"id": "q1", "question": "태양광 사업은 어떻게 시작하나요?"}],
    }

    with pytest.raises(GoldRunError) as raised:
        validate_gold_artifacts(
            copy.deepcopy(raw_bank),
            copy.deepcopy(raw_bank),
            {"status": "not_approved"},
            {"status": "not_approved"},
        )

    assert raised.value.code == "gold_artifact_contract_invalid"


def test_metric_payload_hash_is_canonical_for_same_value() -> None:
    left = {"b": 2, "a": [1, 3]}
    right = {"a": [1, 3], "b": 2}

    left_hash = hashlib.sha256(runner._canonical_json_bytes(left)).hexdigest()
    right_hash = hashlib.sha256(runner._canonical_json_bytes(right)).hexdigest()

    assert left_hash == right_hash
    assert json.loads(runner._canonical_json_bytes(left)) == left


def test_query_plan_normalization_accepts_driver_decoded_or_json_text() -> None:
    plan = [{"Plan": {"Node Type": "Index Scan", "Index Name": "example"}}]

    assert runner._normalize_explain_plan(plan) == plan
    assert runner._normalize_explain_plan(json.dumps(plan)) == plan


def test_retrieval_observation_hash_changes_with_vector_or_raw_score() -> None:
    base = [
        {
            "case_id": "q1",
            "query_embedding_sha256": "a" * 64,
            "hits": [
                {
                    "rank": 1,
                    "provision_id": "p1",
                    "raw_cosine_similarity": 0.9,
                }
            ],
        }
    ]
    changed_vector = copy.deepcopy(base)
    changed_vector[0]["query_embedding_sha256"] = "b" * 64
    changed_score = copy.deepcopy(base)
    changed_score[0]["hits"][0]["raw_cosine_similarity"] = 0.89

    original_hash = runner._retrieval_observation_sha256(base)

    assert runner._retrieval_observation_sha256(changed_vector) != original_hash
    assert runner._retrieval_observation_sha256(changed_score) != original_hash
