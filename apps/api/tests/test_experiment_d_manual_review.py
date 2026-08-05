from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import pytest

from app.domain.embedding_profiles import NVIDIA_NEMOTRON_512_PROFILE
from app.domain.schemas import CorpusSearchStatus
from scripts.evaluate_experiment_d_gold import (
    CorpusSnapshot,
    DenseCandidate,
    RetrievalState,
)
from scripts.experiment_d_corpus import SourceProvision
from scripts.experiment_d_manual_review import (
    RUN_ID_PATTERN,
    ManualRunError,
    _new_run_id,
    run_manual_retrieval,
)
from scripts.experiment_d_manual_review_contract import load_manual_pilot_artifacts


class FakeEmbedder:
    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    async def embed(self, texts: list[str]) -> list[list[float]]:
        self.calls.append(texts)
        return [[1.0, *([0.0] * 511)] for _ in texts]


def test_generated_run_id_satisfies_run_id_contract() -> None:
    run_id = _new_run_id(datetime(2026, 8, 5, 1, 2, 3, 4005, tzinfo=UTC))

    assert run_id.startswith("d10-20260805t010203004005z-")
    assert RUN_ID_PATTERN.fullmatch(run_id) is not None


def _provision(index: int, *, path: str, parent_path: str | None) -> SourceProvision:
    return SourceProvision(
        provision_id=f"provision-{index:02d}",
        version_id="version-1",
        document_id="document-1",
        document_title="전기사업법",
        source_kind="law",
        mst="12345",
        effective_from=date(2026, 1, 1),
        effective_to=None,
        source_url="https://example.test/law",
        path=path,
        parent_path=parent_path,
        heading="제목" if parent_path is None else None,
        content=f"조문 내용 {index}",
        ordinal=index,
    )


def _provisions() -> tuple[SourceProvision, ...]:
    values = [
        _provision(1, path="제1조", parent_path=None),
        _provision(2, path="제1조/항1", parent_path="제1조"),
    ]
    values.extend(
        _provision(index, path=f"제{index - 1}조", parent_path=None)
        for index in range(3, 12)
    )
    return tuple(values)


def _retrieval_state(*, locked: bool, vector_count: int) -> RetrievalState:
    profile = {
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
    settings = {
        "transaction_isolation": "read committed" if locked else "repeatable read",
        "transaction_read_only": "on",
        "postgresql_version": "17.0",
        "postgresql_version_num": "170000",
        "search_path": "pg_catalog, public, extensions, pg_temp",
        "enable_seqscan": "on",
        "enable_indexscan": "on",
        "enable_bitmapscan": "on",
        "random_page_cost": "4",
        "effective_cache_size": "1GB",
        "work_mem": "4MB",
    }
    return RetrievalState(
        profile=profile,
        vector_count=vector_count,
        non_unit_vector_count=0,
        vector_fingerprint_sha256="a" * 64,
        pgvector_version="0.8.0",
        retrieval_settings=settings,
        state_fingerprint_sha256=("c" if locked else "b") * 64,
    )


def _snapshot(*, locked: bool, provisions: tuple[SourceProvision, ...]) -> CorpusSnapshot:
    return CorpusSnapshot(
        status=CorpusSearchStatus(ready=True),
        provisions=provisions,
        retrieval_state=_retrieval_state(locked=locked, vector_count=len(provisions)),
    )


def _candidates(
    provisions: tuple[SourceProvision, ...], *, tied: bool = False
) -> list[DenseCandidate]:
    candidates: list[DenseCandidate] = []
    for rank, provision in enumerate(provisions[:11], 1):
        score = 1.0 - rank / 100
        if tied and rank == 11:
            score = 0.9
        candidates.append(
            DenseCandidate(
                provision_id=provision.provision_id,
                document_id=provision.document_id,
                document_title=provision.document_title,
                source_kind=provision.source_kind,
                version_label="현행",
                effective_from=provision.effective_from,
                effective_to=provision.effective_to,
                path=provision.path,
                heading=provision.heading,
                content=provision.content,
                source_url=provision.source_url,
                score=score,
            )
        )
    return candidates


class FakeLockedReader:
    def __init__(
        self,
        snapshot: CorpusSnapshot,
        candidates: list[DenseCandidate],
    ) -> None:
        self._snapshot = snapshot
        self._candidates = candidates
        self.search_count = 0

    async def snapshot(self) -> CorpusSnapshot:
        return self._snapshot

    async def search(self, **_: Any) -> list[DenseCandidate]:
        self.search_count += 1
        return list(self._candidates)


class FakeBackend:
    def __init__(self, initial: CorpusSnapshot, reader: FakeLockedReader) -> None:
        self._initial = initial
        self.reader = reader

    async def snapshot(self) -> CorpusSnapshot:
        return self._initial

    @asynccontextmanager
    async def locked_reader(self):
        yield self.reader


def _code_provenance() -> dict[str, object]:
    return {
        "git_commit": "1" * 40,
        "critical_code_dirty": False,
        "critical_file_sha256": {"runner": "2" * 64},
    }


async def _run(
    tmp_path: Path,
    *,
    backend: FakeBackend,
    embedder: FakeEmbedder,
    run_id: str,
):
    return await run_manual_retrieval(
        load_manual_pilot_artifacts(),
        backend,
        lambda: embedder,
        output_dir=tmp_path / "runs",
        cache_path=tmp_path / "query-cache.json",
        code_provenance=_code_provenance(),
        as_of_date=date(2026, 8, 5),
        run_id=run_id,
        started_at=datetime(2026, 8, 5, 1, tzinfo=UTC),
        completed_at_factory=lambda: datetime(2026, 8, 5, 1, 1, tzinfo=UTC),
    )


async def test_run_embeds_all_misses_once_and_publishes_raw_and_article_contexts(
    tmp_path: Path,
) -> None:
    provisions = _provisions()
    reader = FakeLockedReader(
        _snapshot(locked=True, provisions=provisions),
        _candidates(provisions),
    )
    backend = FakeBackend(_snapshot(locked=False, provisions=provisions), reader)
    embedder = FakeEmbedder()

    published = await _run(tmp_path, backend=backend, embedder=embedder, run_id="d10-test-1")

    assert [len(call) for call in embedder.calls] == [10]
    assert reader.search_count == 10
    assert published.json_path.exists()
    assert published.markdown_path.exists()
    assert published.payload["stdout_sha256"]
    first_case = published.payload["cases"][0]
    assert len(first_case["raw_candidates"]) == 10
    assert first_case["raw_candidates"][0]["content"] == "조문 내용 1"
    assert first_case["article_contexts"][0]["context_provision_count"] == 2
    assert first_case["article_contexts"][0]["provisions"][1]["parent_path"] == "제1조"
    assert "정답 없는 수동 진단 초안" in published.markdown_path.read_text(encoding="utf-8")


async def test_second_same_snapshot_run_reuses_all_cached_query_vectors(tmp_path: Path) -> None:
    provisions = _provisions()
    snapshot_initial = _snapshot(locked=False, provisions=provisions)
    snapshot_locked = _snapshot(locked=True, provisions=provisions)
    first_embedder = FakeEmbedder()
    await _run(
        tmp_path,
        backend=FakeBackend(
            snapshot_initial,
            FakeLockedReader(snapshot_locked, _candidates(provisions)),
        ),
        embedder=first_embedder,
        run_id="d10-cache-first",
    )
    second_embedder = FakeEmbedder()

    published = await _run(
        tmp_path,
        backend=FakeBackend(
            snapshot_initial,
            FakeLockedReader(snapshot_locked, _candidates(provisions)),
        ),
        embedder=second_embedder,
        run_id="d10-cache-second",
    )

    assert second_embedder.calls == []
    inputs = published.payload["inputs"]
    assert inputs["query_cache_hit_count"] == 10
    assert inputs["query_cache_miss_count"] == 0
    assert inputs["query_embedding_request_count"] == 0


async def test_cutoff_tie_fails_without_publishing_result(tmp_path: Path) -> None:
    provisions = _provisions()
    reader = FakeLockedReader(
        _snapshot(locked=True, provisions=provisions),
        _candidates(provisions, tied=True),
    )
    backend = FakeBackend(_snapshot(locked=False, provisions=provisions), reader)

    with pytest.raises(ManualRunError, match="unresolved_cutoff_tie"):
        await _run(tmp_path, backend=backend, embedder=FakeEmbedder(), run_id="d10-tie")

    assert not (tmp_path / "runs" / "d10-tie").exists()


async def test_fewer_than_eleven_candidates_fails_without_publishing_result(
    tmp_path: Path,
) -> None:
    provisions = _provisions()
    reader = FakeLockedReader(
        _snapshot(locked=True, provisions=provisions),
        _candidates(provisions)[:10],
    )
    backend = FakeBackend(_snapshot(locked=False, provisions=provisions), reader)

    with pytest.raises(ManualRunError, match="dense_search_candidate_count_mismatch"):
        await _run(tmp_path, backend=backend, embedder=FakeEmbedder(), run_id="d10-short")

    assert not (tmp_path / "runs" / "d10-short").exists()


async def test_snapshot_drift_after_embedding_fails_before_search(tmp_path: Path) -> None:
    provisions = _provisions()
    changed = (*provisions[:-1], _provision(12, path="제11조", parent_path=None))
    reader = FakeLockedReader(
        _snapshot(locked=True, provisions=changed),
        _candidates(changed),
    )
    backend = FakeBackend(_snapshot(locked=False, provisions=provisions), reader)

    with pytest.raises(ManualRunError, match="corpus_changed_after_query_embedding"):
        await _run(tmp_path, backend=backend, embedder=FakeEmbedder(), run_id="d10-drift")

    assert reader.search_count == 0
    assert not (tmp_path / "runs" / "d10-drift").exists()
