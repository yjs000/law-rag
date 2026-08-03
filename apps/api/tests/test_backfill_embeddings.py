import json
from uuid import uuid4

import httpx
import pytest
from openai import APITimeoutError

import scripts.backfill_embeddings as backfill_module
from app.adapters.postgres_repository import PostgresLegalRepository
from app.domain.embedding_profiles import NVIDIA_NEMOTRON_512_PROFILE
from scripts.backfill_embeddings import (
    CachedEmbedding,
    PendingProvision,
    _append_cache,
    _cache_pending,
    _embed_with_retry,
    _pending,
    _read_cache,
)


def _row(*, stored_sha256=None) -> dict:
    return {
        "provision_id": uuid4(),
        "document_title": "전기사업법",
        "path": "제7조/항①",
        "heading": "사업의 허가",
        "content": "전기사업을 하려는 자는 허가를 받아야 한다.",
        "stored_sha256": stored_sha256,
    }


def test_pending_uses_full_versioned_passage_hash() -> None:
    first = _row()
    pending, missing, stale = _pending([first])
    current = {**first, "stored_sha256": pending[0].source_text_sha256}
    changed = {**first, "stored_sha256": "0" * 64, "content": "변경된 본문"}

    current_pending, current_missing, current_stale = _pending([current])
    changed_pending, changed_missing, changed_stale = _pending([changed])

    assert missing == 1 and stale == 0
    assert current_pending == [] and current_missing == current_stale == 0
    assert len(changed_pending) == 1 and changed_missing == 0 and changed_stale == 1


@pytest.mark.asyncio
async def test_transient_embedding_failure_is_retried(monkeypatch) -> None:
    class Embedder:
        calls = 0

        async def embed(self, texts):
            self.calls += 1
            if self.calls == 1:
                raise APITimeoutError(request=httpx.Request("POST", "https://example.test"))
            return [[1.0, 0.0]]

    embedder = Embedder()

    async def no_sleep(_):
        return None

    monkeypatch.setattr(backfill_module.asyncio, "sleep", no_sleep)

    result = await _embed_with_retry(
        embedder,  # type: ignore[arg-type]
        ["본문"],
        max_retries=1,
        retry_base_seconds=0.01,
    )

    assert result == [[1.0, 0.0]]
    assert embedder.calls == 2


@pytest.mark.asyncio
async def test_repository_rejects_unknown_profile_before_database_access() -> None:
    repository = PostgresLegalRepository.__new__(PostgresLegalRepository)

    with pytest.raises(ValueError, match="unsupported embedding profile"):
        await repository.upsert_embeddings([(uuid4(), "0" * 64, [1.0])], "unknown", 512)


@pytest.mark.asyncio
async def test_repository_rejects_wrong_vector_dimensions_before_database_access() -> None:
    repository = PostgresLegalRepository.__new__(PostgresLegalRepository)

    with pytest.raises(ValueError, match="vector dimensions"):
        await repository.upsert_embeddings(
            [(uuid4(), "0" * 64, [1.0, 0.0])],
            NVIDIA_NEMOTRON_512_PROFILE.key,
            NVIDIA_NEMOTRON_512_PROFILE.stored_dimensions,
        )


def test_cache_round_trip_keeps_last_record_and_no_source_text(tmp_path) -> None:
    cache = tmp_path / "vectors.jsonl"
    provision_id = uuid4()
    first = PendingProvision(provision_id, "비저장 원문", "0" * 64)
    changed = PendingProvision(provision_id, "변경된 비저장 원문", "1" * 64)
    vector = [1.0] + [0.0] * 511

    _append_cache(cache, [first], [vector])
    _append_cache(cache, [changed], [vector])
    records, line_count = _read_cache(cache)

    assert line_count == 2
    assert records[str(provision_id)].source_text_sha256 == "1" * 64
    assert records[str(provision_id)].embedding == vector
    assert "비저장 원문" not in cache.read_text(encoding="utf-8")


def test_cache_pending_distinguishes_missing_stale_and_current() -> None:
    missing = PendingProvision(uuid4(), "a", "0" * 64)
    stale = PendingProvision(uuid4(), "b", "1" * 64)
    current = PendingProvision(uuid4(), "c", "2" * 64)
    vector = [1.0] + [0.0] * 511
    records = {
        str(stale.provision_id): CachedEmbedding(str(stale.provision_id), "f" * 64, vector),
        str(current.provision_id): CachedEmbedding(
            str(current.provision_id), current.source_text_sha256, vector
        ),
    }

    pending, missing_count, stale_count = _cache_pending(
        [missing, stale, current], records
    )

    assert pending == [missing, stale]
    assert missing_count == 1
    assert stale_count == 1


def test_read_cache_rejects_wrong_vector_dimensions(tmp_path) -> None:
    cache = tmp_path / "invalid.jsonl"
    payload = {
        "profile_key": NVIDIA_NEMOTRON_512_PROFILE.key,
        "dimensions": NVIDIA_NEMOTRON_512_PROFILE.stored_dimensions,
        "provision_id": str(uuid4()),
        "source_text_sha256": "0" * 64,
        "embedding": [1.0],
    }
    cache.write_text(json.dumps(payload) + "\n", encoding="utf-8")

    with pytest.raises(ValueError, match="512 dimensions"):
        _read_cache(cache)
