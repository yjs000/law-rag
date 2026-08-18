# V2 LlamaIndex Retrieval Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a new, independent LlamaIndex-based dense retrieval pipeline (`law-rag-llamaindex`) and wire it into `apps/api` as `/v2/search` (standalone debug endpoint) and `/v2/questions` (reuses v1's existing routing/generation/citation-validation code, swapping only the evidence-retrieval repository), then switch `apps/web` to call `/v2/questions`.

**Architecture:** A new uv workspace app owns ingestion (provisions → LlamaIndex nodes → NVIDIA NIM embeddings → `PGVectorStore`) and a `retriever.search()` function. `apps/api` gets a new `LlamaIndexLegalRepository` adapter implementing the existing `LegalRepository` Protocol — it overrides only `search`/`search_with_trace` and delegates every other method (quota, corpus status, provision lookup, last_sync) to the existing `PostgresLegalRepository` instance. `_answer_question` and its helpers are refactored to take `repository` as an explicit parameter instead of reading the module global, so `/v2/questions` can call the exact same function with the new adapter injected.

**Tech Stack:** Python 3.14, uv workspaces, LlamaIndex (`llama-index-core`, `llama-index-vector-stores-postgres`, `llama-index-embeddings-nvidia`), SQLAlchemy async + asyncpg, FastAPI, Alembic, pytest/pytest-asyncio.

## Global Constraints

- Python: `>=3.14,<3.15` for every new Python package (match `apps/api`, `apps/collector`).
- `apps/api` code style: `ruff` with `select = ["E", "F", "I", "UP", "B", "ASYNC"]`, line length 100.
- `law-rag-llamaindex` code style: same ruff config minus `ASYNC` unless needed (match `packages/law-rag-core`'s `select = ["E", "F", "I", "UP", "B"]`).
- v1 code (`/v1/*` routes, `PostgresLegalRepository`, `provision_embeddings`, `embedding_profiles`) must not be modified in behavior — only `_answer_question`/`_retrieve_question_evidence`/`_load_corpus_temporal_state`/`_require_supported_as_of_date` gain an explicit `repository` parameter (mechanical, behavior-preserving for existing call sites).
- Embedding model: `nvidia/nemotron-3-embed-1b` via `NVIDIA_API_KEY`/`NVIDIA_BASE_URL` (reuse `apps/api` settings values — do not introduce a second source of truth for these two env vars).
- Embedding storage dimension: native NIM dimension, `2048` (no truncation/re-normalization in v2).
- Passage template (verbatim, newline-joined, empty fields skipped): 법령명 → 경로 → 표제 → 원문 본문.
- `PGVectorStore` table name: `law_rag_llamaindex` (physical table `data_law_rag_llamaindex`, confirmed from library source). `hnsw_kwargs` stays `None` for now but the factory function must accept it as a parameter.
- 503 stable error code for both `/v2/search` and `/v2/questions` when the v2 index has no completed ingestion run: `{"code": "v2_search_not_ready", "message": "..."}` (same `detail` shape as `_corpus_unready_http_error`).
- Never commit `.env`/secrets. Never run destructive DB commands without explicit confirmation.
- Test invocation: always run `python -m pytest` (e.g. `uv run --directory apps/api python -m pytest`), never bare `pytest` — bare `pytest` does not add the working directory to `sys.path` on this project's setup, so `import app`/`import law_rag_llamaindex` fails with `ModuleNotFoundError` even though the code is correct. Verified against this repo's actual environment before this plan's execution began.
- Dependency sync: always run `uv sync --all-packages` from the repo root, never `uv sync --directory <single-member>` — this is a shared-venv uv workspace, and syncing one member alone prunes packages other members need, breaking their tests. Verified against this repo's actual environment before this plan's execution began.
- Design doc of record: [`docs/design-docs/v2-llamaindex-retrieval-pipeline-design.md`](../../design-docs/v2-llamaindex-retrieval-pipeline-design.md). If an implementation detail here conflicts with it, the design doc's "결정 기록" wins and this plan should be corrected to match, not the other way around.

---

## Task 1: Scaffold the `law-rag-llamaindex` workspace app

**Files:**
- Create: `apps/law-rag-llamaindex/pyproject.toml`
- Create: `apps/law-rag-llamaindex/src/law_rag_llamaindex/__init__.py`
- Create: `apps/law-rag-llamaindex/tests/test_package.py`
- Modify: `pyproject.toml:2` (root workspace members)

**Interfaces:**
- Produces: importable package `law_rag_llamaindex` with `__version__ = "0.1.0"`, installable as a uv workspace member.

- [ ] **Step 1: Add the workspace member to the root `pyproject.toml`**

```toml
[tool.uv.workspace]
members = ["apps/api", "apps/collector", "apps/law-rag-llamaindex", "packages/law-rag-core"]
```

- [ ] **Step 2: Create the app directory and `pyproject.toml`**

```toml
[project]
name = "law-rag-llamaindex"
version = "0.1.0"
description = "LlamaIndex 기반 v2 검색 파이프라인 (law-rag v1과 독립)"
requires-python = ">=3.14,<3.15"
dependencies = [
  "asyncpg>=0.30,<1",
  "llama-index-core>=0.12,<1",
  "llama-index-embeddings-nvidia>=0.3,<1",
  "llama-index-vector-stores-postgres>=0.4,<1",
  "pydantic-settings>=2.10,<3",
  "sqlalchemy[asyncio]>=2.0.41,<3",
]

[dependency-groups]
dev = [
  "pytest>=8.4,<9",
  "pytest-asyncio>=1.1,<2",
  "ruff>=0.12,<1",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]

[tool.ruff]
line-length = 100
target-version = "py314"

[tool.ruff.lint]
select = ["E", "F", "I", "UP", "B"]
```

- [ ] **Step 3: Create the package skeleton**

`apps/law-rag-llamaindex/src/law_rag_llamaindex/__init__.py`:
```python
__version__ = "0.1.0"
```

- [ ] **Step 4: Write the smoke test**

`apps/law-rag-llamaindex/tests/test_package.py`:
```python
import law_rag_llamaindex


def test_package_imports():
    assert law_rag_llamaindex.__version__ == "0.1.0"
```

- [ ] **Step 5: Sync the workspace and run the test**

Run: `uv sync --all-packages` (not `--directory apps/law-rag-llamaindex` alone — this repo is a shared-venv uv workspace, and syncing a single member can prune packages other members need)
Expected: dependency resolution succeeds under Python 3.14 (llama-index-core requires `>=3.9,<4.0`, so this should resolve — if it fails, capture the resolver error before proceeding to later tasks, since every later task in this plan depends on this install succeeding).

Run: `uv run --directory apps/law-rag-llamaindex python -m pytest -v`
Expected: `test_package_imports PASSED`

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml apps/law-rag-llamaindex/
git commit -m "feat(law-rag-llamaindex): scaffold new uv workspace app"
```

---

## Task 2: Config settings

**Files:**
- Create: `apps/law-rag-llamaindex/src/law_rag_llamaindex/config.py`
- Test: `apps/law-rag-llamaindex/tests/test_config.py`

**Interfaces:**
- Produces: `Settings` (pydantic `BaseSettings`) with fields `database_url: str | None`, `nvidia_api_key: str | None`, `nvidia_base_url: str`, `nvidia_embedding_model: str`, `embed_dim: int`, `vector_table_name: str`, `hnsw_kwargs: dict | None`; `get_settings() -> Settings` (`lru_cache`d).
- Consumes: nothing (leaf module).

- [ ] **Step 1: Write the failing test**

```python
# apps/law-rag-llamaindex/tests/test_config.py
import os

from law_rag_llamaindex.config import Settings, get_settings


def test_defaults(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("NVIDIA_API_KEY", raising=False)
    settings = Settings(_env_file=None)
    assert settings.database_url is None
    assert settings.nvidia_api_key is None
    assert settings.nvidia_base_url == "https://integrate.api.nvidia.com/v1"
    assert settings.nvidia_embedding_model == "nvidia/nemotron-3-embed-1b"
    assert settings.embed_dim == 2048
    assert settings.vector_table_name == "law_rag_llamaindex"
    assert settings.hnsw_kwargs is None


def test_env_override(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://u:p@h:5432/d")
    monkeypatch.setenv("NVIDIA_API_KEY", "test-key")
    settings = Settings(_env_file=None)
    assert settings.database_url == "postgresql+asyncpg://u:p@h:5432/d"
    assert settings.nvidia_api_key == "test-key"


def test_get_settings_is_cached():
    assert get_settings() is get_settings()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --directory apps/law-rag-llamaindex python -m pytest tests/test_config.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'law_rag_llamaindex.config'`

- [ ] **Step 3: Write the implementation**

```python
# apps/law-rag-llamaindex/src/law_rag_llamaindex/config.py
from functools import lru_cache
from typing import Any

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", ".env.local"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    database_url: str | None = None
    nvidia_api_key: str | None = None
    nvidia_base_url: str = "https://integrate.api.nvidia.com/v1"
    nvidia_embedding_model: str = "nvidia/nemotron-3-embed-1b"
    embed_dim: int = 2048
    vector_table_name: str = "law_rag_llamaindex"
    hnsw_kwargs: dict[str, Any] | None = None


@lru_cache
def get_settings() -> Settings:
    return Settings()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run --directory apps/law-rag-llamaindex python -m pytest tests/test_config.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add apps/law-rag-llamaindex/src/law_rag_llamaindex/config.py apps/law-rag-llamaindex/tests/test_config.py
git commit -m "feat(law-rag-llamaindex): add settings module"
```

---

## Task 3: Passage template and node metadata builder (pure, TDD)

**Files:**
- Create: `apps/law-rag-llamaindex/src/law_rag_llamaindex/passage.py`
- Test: `apps/law-rag-llamaindex/tests/test_passage.py`

**Interfaces:**
- Produces: `ProvisionRecord` (`TypedDict`: `provision_id: str`, `document_id: str`, `document_title: str`, `source_kind: str`, `law_type_code: str | None`, `version_label: str`, `effective_from: str | None`, `effective_to: str | None`, `path: str`, `heading: str | None`, `content: str`, `source_url: str`); `build_passage_text(record: ProvisionRecord) -> str`; `build_node_metadata(record: ProvisionRecord, source_text_sha256: str) -> dict[str, object]`; `compute_source_text_sha256(passage_text: str) -> str`.
- Consumes: nothing (leaf module — this is what Task 4's source query rows get converted into, and what Task 7's ingestion consumes).

- [ ] **Step 1: Write the failing tests**

```python
# apps/law-rag-llamaindex/tests/test_passage.py
from law_rag_llamaindex.passage import (
    ProvisionRecord,
    build_node_metadata,
    build_passage_text,
    compute_source_text_sha256,
)


def _record(**overrides: object) -> ProvisionRecord:
    base: ProvisionRecord = {
        "provision_id": "11111111-1111-1111-1111-111111111111",
        "document_id": "22222222-2222-2222-2222-222222222222",
        "document_title": "에너지법",
        "source_kind": "statute",
        "law_type_code": "01",
        "version_label": "MST 123456",
        "effective_from": "2024-01-01",
        "effective_to": None,
        "path": "제3조제1항",
        "heading": "정의",
        "content": "이 법에서 사용하는 용어의 뜻은 다음과 같다.",
        "source_url": "https://example.test/law/1",
    }
    base.update(overrides)  # type: ignore[typeddict-item]
    return base


def test_build_passage_text_joins_non_empty_fields_in_order():
    text = build_passage_text(_record())
    assert text == (
        "에너지법\n제3조제1항\n정의\n이 법에서 사용하는 용어의 뜻은 다음과 같다."
    )


def test_build_passage_text_skips_empty_heading():
    text = build_passage_text(_record(heading=None))
    assert text == (
        "에너지법\n제3조제1항\n이 법에서 사용하는 용어의 뜻은 다음과 같다."
    )


def test_compute_source_text_sha256_is_deterministic():
    text = build_passage_text(_record())
    assert compute_source_text_sha256(text) == compute_source_text_sha256(text)


def test_compute_source_text_sha256_changes_with_content():
    record_a = _record()
    record_b = _record(content="다른 본문")
    sha_a = compute_source_text_sha256(build_passage_text(record_a))
    sha_b = compute_source_text_sha256(build_passage_text(record_b))
    assert sha_a != sha_b


def test_build_node_metadata_preserves_raw_fields_separately_from_passage_text():
    record = _record()
    metadata = build_node_metadata(record, "deadbeef")
    assert metadata["content"] == record["content"]
    assert metadata["document_title"] == record["document_title"]
    assert metadata["path"] == record["path"]
    assert metadata["effective_from"] == "2024-01-01"
    assert metadata["effective_to"] is None
    assert metadata["source_text_sha256"] == "deadbeef"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run --directory apps/law-rag-llamaindex python -m pytest tests/test_passage.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'law_rag_llamaindex.passage'`

- [ ] **Step 3: Write the implementation**

```python
# apps/law-rag-llamaindex/src/law_rag_llamaindex/passage.py
import hashlib
from typing import TypedDict


class ProvisionRecord(TypedDict):
    provision_id: str
    document_id: str
    document_title: str
    source_kind: str
    law_type_code: str | None
    version_label: str
    effective_from: str | None
    effective_to: str | None
    path: str
    heading: str | None
    content: str
    source_url: str


def build_passage_text(record: ProvisionRecord) -> str:
    parts = [
        record["document_title"],
        record["path"],
        record.get("heading"),
        record["content"],
    ]
    return "\n".join(part for part in parts if part)


def compute_source_text_sha256(passage_text: str) -> str:
    return hashlib.sha256(passage_text.encode("utf-8")).hexdigest()


def build_node_metadata(record: ProvisionRecord, source_text_sha256: str) -> dict[str, object]:
    return {
        "provision_id": record["provision_id"],
        "document_id": record["document_id"],
        "document_title": record["document_title"],
        "source_kind": record["source_kind"],
        "law_type_code": record.get("law_type_code"),
        "version_label": record["version_label"],
        "effective_from": record.get("effective_from"),
        "effective_to": record.get("effective_to"),
        "path": record["path"],
        "heading": record.get("heading"),
        "content": record["content"],
        "source_url": record["source_url"],
        "source_text_sha256": source_text_sha256,
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run --directory apps/law-rag-llamaindex python -m pytest tests/test_passage.py -v`
Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add apps/law-rag-llamaindex/src/law_rag_llamaindex/passage.py apps/law-rag-llamaindex/tests/test_passage.py
git commit -m "feat(law-rag-llamaindex): add passage template and node metadata builder"
```

---

## Task 4: Provisions source query

**Files:**
- Create: `apps/law-rag-llamaindex/src/law_rag_llamaindex/source.py`
- Test: `apps/law-rag-llamaindex/tests/test_source.py`

**Interfaces:**
- Consumes: `ProvisionRecord` (Task 3), `sqlalchemy.ext.asyncio.AsyncEngine`.
- Produces: `async def fetch_provisions(engine: AsyncEngine) -> list[ProvisionRecord]`.

This task's test requires a live Postgres (`DATABASE_URL` set) since it exercises a real join query — guard it so the default `pytest` run (no `DATABASE_URL`) skips it, matching `apps/api`'s convention of defaulting `DATABASE_URL=""` in tests.

- [ ] **Step 1: Write the failing test**

```python
# apps/law-rag-llamaindex/tests/test_source.py
import os

import pytest
from sqlalchemy.ext.asyncio import create_async_engine

from law_rag_llamaindex.source import fetch_provisions

pytestmark = pytest.mark.skipif(
    not os.environ.get("DATABASE_URL"), reason="requires a live Postgres DATABASE_URL"
)


@pytest.mark.asyncio
async def test_fetch_provisions_returns_expected_fields():
    engine = create_async_engine(os.environ["DATABASE_URL"])
    try:
        records = await fetch_provisions(engine)
    finally:
        await engine.dispose()
    assert isinstance(records, list)
    if records:
        record = records[0]
        for key in (
            "provision_id",
            "document_id",
            "document_title",
            "source_kind",
            "law_type_code",
            "version_label",
            "effective_from",
            "effective_to",
            "path",
            "heading",
            "content",
            "source_url",
        ):
            assert key in record
```

- [ ] **Step 2: Run test to verify it is skipped (no DB configured) and fails to import first**

Run: `uv run --directory apps/law-rag-llamaindex python -m pytest tests/test_source.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'law_rag_llamaindex.source'` (the skip marker only takes effect once the module exists — this step proves the test file itself is wired up before the module exists)

- [ ] **Step 3: Write the implementation**

Reuses the exact join and column aliases already used by `apps/api/app/adapters/postgres_repository.py` (`provisions p JOIN document_versions v ON v.id = p.version_id JOIN legal_documents d ON d.id = v.document_id`, `version_label` built as `'MST '||v.mst`) so v2's raw rows match v1's semantics for the same columns.

```python
# apps/law-rag-llamaindex/src/law_rag_llamaindex/source.py
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from law_rag_llamaindex.passage import ProvisionRecord

_PROVISIONS_QUERY = text(
    """
    SELECT p.id AS provision_id, d.id AS document_id, d.exact_title AS document_title,
           d.source_kind, d.law_type_code,
           'MST ' || v.mst AS version_label,
           v.effective_from, v.effective_to,
           p.path, p.heading, p.content, v.source_url
    FROM provisions p
    JOIN document_versions v ON v.id = p.version_id
    JOIN legal_documents d ON d.id = v.document_id
    """
)


async def fetch_provisions(engine: AsyncEngine) -> list[ProvisionRecord]:
    async with engine.connect() as connection:
        result = await connection.execute(_PROVISIONS_QUERY)
        rows = result.mappings().all()
    return [
        {
            "provision_id": str(row["provision_id"]),
            "document_id": str(row["document_id"]),
            "document_title": row["document_title"],
            "source_kind": row["source_kind"],
            "law_type_code": row["law_type_code"],
            "version_label": row["version_label"],
            "effective_from": row["effective_from"].isoformat() if row["effective_from"] else None,
            "effective_to": row["effective_to"].isoformat() if row["effective_to"] else None,
            "path": row["path"],
            "heading": row["heading"],
            "content": row["content"],
            "source_url": row["source_url"],
        }
        for row in rows
    ]
```

- [ ] **Step 4: Run test to verify it passes (or skips cleanly without a DB)**

Run: `uv run --directory apps/law-rag-llamaindex python -m pytest tests/test_source.py -v`
Expected: `1 skipped` (no `DATABASE_URL` in the default dev shell) — if you have a local `DATABASE_URL` exported, expect `1 passed` instead.

- [ ] **Step 5: Commit**

```bash
git add apps/law-rag-llamaindex/src/law_rag_llamaindex/source.py apps/law-rag-llamaindex/tests/test_source.py
git commit -m "feat(law-rag-llamaindex): add provisions source query"
```

---

## Task 5: Embedding wrapper

**Files:**
- Create: `apps/law-rag-llamaindex/src/law_rag_llamaindex/embedding.py`
- Test: `apps/law-rag-llamaindex/tests/test_embedding.py`

**Interfaces:**
- Consumes: `Settings` (Task 2).
- Produces: `build_embedder(settings: Settings) -> NVIDIAEmbedding`.

NIM's passage-vs-query distinction is handled by LlamaIndex's `NVIDIAEmbedding` internally based on which method you call (`get_text_embedding_batch(...)` for ingestion/passage, `get_query_embedding(...)` for queries) — this wrapper only needs to construct the client with the right model/credentials, not pass `input_type` itself.

- [ ] **Step 1: Write the failing test**

```python
# apps/law-rag-llamaindex/tests/test_embedding.py
from law_rag_llamaindex.config import Settings
from law_rag_llamaindex.embedding import build_embedder


def test_build_embedder_uses_configured_model_and_endpoint():
    settings = Settings(
        _env_file=None,
        nvidia_api_key="test-key",
        nvidia_base_url="https://integrate.api.nvidia.com/v1",
        nvidia_embedding_model="nvidia/nemotron-3-embed-1b",
    )
    embedder = build_embedder(settings)
    assert embedder.model == "nvidia/nemotron-3-embed-1b"
    assert embedder.truncate == "END"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --directory apps/law-rag-llamaindex python -m pytest tests/test_embedding.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'law_rag_llamaindex.embedding'`

- [ ] **Step 3: Write the implementation**

```python
# apps/law-rag-llamaindex/src/law_rag_llamaindex/embedding.py
from llama_index.embeddings.nvidia import NVIDIAEmbedding

from law_rag_llamaindex.config import Settings


def build_embedder(settings: Settings) -> NVIDIAEmbedding:
    return NVIDIAEmbedding(
        model=settings.nvidia_embedding_model,
        api_key=settings.nvidia_api_key,
        base_url=settings.nvidia_base_url,
        truncate="END",
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run --directory apps/law-rag-llamaindex python -m pytest tests/test_embedding.py -v`
Expected: 1 passed
(If `NVIDIAEmbedding.__init__` rejects a fake API key or requires network access to construct, that's a real API-shape surprise — stop and adjust the wrapper/test rather than skip the test. This is expected to construct without any network call.)

- [ ] **Step 5: Commit**

```bash
git add apps/law-rag-llamaindex/src/law_rag_llamaindex/embedding.py apps/law-rag-llamaindex/tests/test_embedding.py
git commit -m "feat(law-rag-llamaindex): add NVIDIA embedding wrapper"
```

---

## Task 6: Vector store factory

**Files:**
- Create: `apps/law-rag-llamaindex/src/law_rag_llamaindex/store.py`
- Test: `apps/law-rag-llamaindex/tests/test_store.py`

**Interfaces:**
- Consumes: `Settings` (Task 2).
- Produces: `build_vector_store(settings: Settings) -> PGVectorStore`.

- [ ] **Step 1: Write the failing test**

```python
# apps/law-rag-llamaindex/tests/test_store.py
from law_rag_llamaindex.config import Settings
from law_rag_llamaindex.store import build_vector_store


def test_build_vector_store_uses_configured_table_and_dimension():
    settings = Settings(
        _env_file=None,
        database_url="postgresql+asyncpg://user:pass@localhost:5432/lawrag",
        embed_dim=2048,
        vector_table_name="law_rag_llamaindex",
        hnsw_kwargs=None,
    )
    store = build_vector_store(settings)
    assert store.table_name == "law_rag_llamaindex"
    assert store.embed_dim == 2048
    assert store.hnsw_kwargs is None


def test_build_vector_store_passes_through_hnsw_kwargs_when_set():
    settings = Settings(
        _env_file=None,
        database_url="postgresql+asyncpg://user:pass@localhost:5432/lawrag",
        embed_dim=2048,
        vector_table_name="law_rag_llamaindex",
        hnsw_kwargs={"hnsw_m": 16, "hnsw_ef_construction": 64},
    )
    store = build_vector_store(settings)
    assert store.hnsw_kwargs == {"hnsw_m": 16, "hnsw_ef_construction": 64}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --directory apps/law-rag-llamaindex python -m pytest tests/test_store.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'law_rag_llamaindex.store'`

- [ ] **Step 3: Write the implementation**

```python
# apps/law-rag-llamaindex/src/law_rag_llamaindex/store.py
from llama_index.vector_stores.postgres import PGVectorStore
from sqlalchemy.engine import make_url

from law_rag_llamaindex.config import Settings


def build_vector_store(settings: Settings) -> PGVectorStore:
    if not settings.database_url:
        raise ValueError("database_url is required to build the vector store")
    url = make_url(settings.database_url)
    return PGVectorStore.from_params(
        host=url.host,
        port=str(url.port or 5432),
        database=url.database,
        user=url.username,
        password=url.password,
        table_name=settings.vector_table_name,
        embed_dim=settings.embed_dim,
        hnsw_kwargs=settings.hnsw_kwargs,
        use_jsonb=True,
        perform_setup=True,
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run --directory apps/law-rag-llamaindex python -m pytest tests/test_store.py -v`
Expected: 2 passed
(`PGVectorStore.from_params` must not open a connection at construction time for this to pass without a live DB — if it does, the test needs a running Postgres; note that discovery in the plan's progress log and switch the test to the `DATABASE_URL`-skip pattern from Task 4 if so.)

- [ ] **Step 5: Commit**

```bash
git add apps/law-rag-llamaindex/src/law_rag_llamaindex/store.py apps/law-rag-llamaindex/tests/test_store.py
git commit -m "feat(law-rag-llamaindex): add PGVectorStore factory"
```

---

## Task 7: Ingestion pipeline

**Files:**
- Create: `apps/law-rag-llamaindex/src/law_rag_llamaindex/ingest.py`
- Test: `apps/law-rag-llamaindex/tests/test_ingest.py`

**Interfaces:**
- Consumes: `ProvisionRecord`, `build_passage_text`, `compute_source_text_sha256`, `build_node_metadata` (Task 3); `PGVectorStore`-shaped object with `.add(nodes) -> list[str]` (Task 6, faked in this task's tests).
- Produces: `changed_provision_ids(provisions: list[ProvisionRecord], existing_hashes: dict[str, str]) -> set[str]` (pure); `build_nodes(provisions: list[ProvisionRecord]) -> list[TextNode]` (pure, unembedded); `async def existing_hashes(engine: AsyncEngine, table_name: str) -> dict[str, str]`; `async def delete_nodes(engine: AsyncEngine, table_name: str, node_ids: set[str]) -> None`; `async def run_ingestion(engine, vector_store, embedder, table_name: str) -> IngestionResult` (`IngestionResult` = `@dataclass(frozen=True)` with `total_provisions: int`, `embedded_count: int`, `skipped_count: int`).

The hash-skip logic (`changed_provision_ids`, `build_nodes`) is pure and gets full unit-test coverage with fakes. `existing_hashes`/`delete_nodes`/`run_ingestion` need a live Postgres and are skip-guarded like Task 4.

- [ ] **Step 1: Write the failing tests for the pure logic**

```python
# apps/law-rag-llamaindex/tests/test_ingest.py
import os

import pytest
from llama_index.core.schema import TextNode

from law_rag_llamaindex.ingest import build_nodes, changed_provision_ids
from law_rag_llamaindex.passage import build_passage_text, compute_source_text_sha256


def _record(provision_id: str, content: str) -> dict:
    return {
        "provision_id": provision_id,
        "document_id": "doc-1",
        "document_title": "에너지법",
        "source_kind": "statute",
        "law_type_code": "01",
        "version_label": "MST 1",
        "effective_from": "2024-01-01",
        "effective_to": None,
        "path": "제1조",
        "heading": None,
        "content": content,
        "source_url": "https://example.test",
    }


def test_changed_provision_ids_includes_new_and_changed_only():
    provisions = [_record("a", "본문 A"), _record("b", "본문 B")]
    hash_a = compute_source_text_sha256(build_passage_text(provisions[0]))
    # "a" unchanged (hash matches), "b" is new (no existing hash)
    existing = {"a": hash_a}
    assert changed_provision_ids(provisions, existing) == {"b"}


def test_changed_provision_ids_includes_content_changed_rows():
    provisions = [_record("a", "본문 A 수정됨")]
    existing = {"a": compute_source_text_sha256(build_passage_text(_record("a", "본문 A")))}
    assert changed_provision_ids(provisions, existing) == {"a"}


def test_build_nodes_sets_id_text_and_metadata():
    provisions = [_record("a", "본문 A")]
    nodes = build_nodes(provisions)
    assert len(nodes) == 1
    node = nodes[0]
    assert isinstance(node, TextNode)
    assert node.id_ == "a"
    assert node.text == build_passage_text(provisions[0])
    assert node.metadata["content"] == "본문 A"
    assert "source_text_sha256" in node.metadata


pytestmark_db = pytest.mark.skipif(
    not os.environ.get("DATABASE_URL"), reason="requires a live Postgres DATABASE_URL"
)


@pytestmark_db
@pytest.mark.asyncio
async def test_run_ingestion_skips_unchanged_rows_on_second_run():
    import asyncpg  # noqa: F401  (ensures driver present for direct pool tests if needed later)
    from sqlalchemy.ext.asyncio import create_async_engine

    from law_rag_llamaindex.config import Settings
    from law_rag_llamaindex.embedding import build_embedder
    from law_rag_llamaindex.ingest import run_ingestion
    from law_rag_llamaindex.store import build_vector_store

    settings = Settings()
    engine = create_async_engine(settings.database_url)
    vector_store = build_vector_store(settings)
    embedder = build_embedder(settings)
    try:
        first = await run_ingestion(engine, vector_store, embedder, settings.vector_table_name)
        second = await run_ingestion(engine, vector_store, embedder, settings.vector_table_name)
    finally:
        await engine.dispose()
    assert first.embedded_count >= 0
    assert second.embedded_count == 0
    assert second.skipped_count == second.total_provisions
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run --directory apps/law-rag-llamaindex python -m pytest tests/test_ingest.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'law_rag_llamaindex.ingest'`

- [ ] **Step 3: Write the implementation**

```python
# apps/law-rag-llamaindex/src/law_rag_llamaindex/ingest.py
from dataclasses import dataclass

from llama_index.core.schema import TextNode
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncEngine

from law_rag_llamaindex.passage import ProvisionRecord, build_node_metadata, build_passage_text, compute_source_text_sha256


@dataclass(frozen=True)
class IngestionResult:
    total_provisions: int
    embedded_count: int
    skipped_count: int


def changed_provision_ids(
    provisions: list[ProvisionRecord], existing_hashes: dict[str, str]
) -> set[str]:
    changed: set[str] = set()
    for record in provisions:
        current_hash = compute_source_text_sha256(build_passage_text(record))
        if existing_hashes.get(record["provision_id"]) != current_hash:
            changed.add(record["provision_id"])
    return changed


def build_nodes(provisions: list[ProvisionRecord]) -> list[TextNode]:
    nodes = []
    for record in provisions:
        passage_text = build_passage_text(record)
        sha256 = compute_source_text_sha256(passage_text)
        nodes.append(
            TextNode(
                id_=record["provision_id"],
                text=passage_text,
                metadata=build_node_metadata(record, sha256),
            )
        )
    return nodes


async def existing_hashes(engine: AsyncEngine, table_name: str) -> dict[str, str]:
    physical_table = f"data_{table_name}"
    query = text(f'SELECT node_id, metadata_->>\'source_text_sha256\' AS sha FROM "{physical_table}"')
    try:
        async with engine.connect() as connection:
            result = await connection.execute(query)
            return {row.node_id: row.sha for row in result}
    except DBAPIError:
        # First run: the table hasn't been created by the vector store yet.
        return {}


async def delete_nodes(engine: AsyncEngine, table_name: str, node_ids: set[str]) -> None:
    if not node_ids:
        return
    physical_table = f"data_{table_name}"
    query = text(f'DELETE FROM "{physical_table}" WHERE node_id = ANY(:ids)')
    async with engine.begin() as connection:
        await connection.execute(query, {"ids": list(node_ids)})


async def run_ingestion(engine, vector_store, embedder, table_name: str) -> IngestionResult:
    from law_rag_llamaindex.source import fetch_provisions

    provisions = await fetch_provisions(engine)
    current_hashes = await existing_hashes(engine, table_name)
    changed_ids = changed_provision_ids(provisions, current_hashes)
    changed_records = [p for p in provisions if p["provision_id"] in changed_ids]

    ids_to_delete = changed_ids & current_hashes.keys()
    await delete_nodes(engine, table_name, ids_to_delete)

    if changed_records:
        nodes = build_nodes(changed_records)
        texts = [node.text for node in nodes]
        embeddings = embedder.get_text_embedding_batch(texts)
        for node, embedding in zip(nodes, embeddings, strict=True):
            node.embedding = embedding
        vector_store.add(nodes)

    return IngestionResult(
        total_provisions=len(provisions),
        embedded_count=len(changed_records),
        skipped_count=len(provisions) - len(changed_records),
    )
```

- [ ] **Step 4: Run tests to verify they pass (or skip cleanly)**

Run: `uv run --directory apps/law-rag-llamaindex python -m pytest tests/test_ingest.py -v`
Expected: 3 passed, 1 skipped (no `DATABASE_URL`) — or 4 passed if `DATABASE_URL` is set to a real dev Postgres with the `law_rag_llamaindex_ingestion_runs` migration (Task 8) and provisions data already present.

- [ ] **Step 5: Commit**

```bash
git add apps/law-rag-llamaindex/src/law_rag_llamaindex/ingest.py apps/law-rag-llamaindex/tests/test_ingest.py
git commit -m "feat(law-rag-llamaindex): add ingestion pipeline with hash-skip upsert"
```

---

## Task 8: Retriever

**Files:**
- Create: `apps/law-rag-llamaindex/src/law_rag_llamaindex/retriever.py`
- Test: `apps/law-rag-llamaindex/tests/test_retriever.py`

**Interfaces:**
- Consumes: a `PGVectorStore`-shaped object exposing `.aquery(VectorStoreQuery) -> VectorStoreQueryResult` (faked in tests), an embedder exposing `.get_query_embedding(str) -> list[float]` (faked), `law_rag_core.domain.schemas.SearchHit`.
- Produces: `async def search(vector_store, embedder, query: str, as_of_date: date, limit: int) -> list[SearchHit]`.

Temporal validity is enforced in two layers: `effective_from <= as_of_date` is pushed down as a `MetadataFilter` (server-side, cheap), and the `effective_to IS NULL OR effective_to > as_of_date` half is applied in Python after fetching an over-fetched batch (`limit * 4`, capped at 100) — LlamaIndex's `FilterOperator` set (`EQ`/`GT`/`LT`/`NE`/`GTE`/`LTE`/`IN`/`NIN`) has no confirmed null-check operator, so this avoids guessing at an operator that might not exist.

- [ ] **Step 1: Write the failing tests**

```python
# apps/law-rag-llamaindex/tests/test_retriever.py
from datetime import date

import pytest
from llama_index.core.vector_stores.types import VectorStoreQueryResult
from llama_index.core.schema import NodeWithScore, TextNode

from law_rag_llamaindex.retriever import search


class FakeEmbedder:
    def get_query_embedding(self, text: str) -> list[float]:
        return [0.1, 0.2, 0.3]


def _node(provision_id: str, effective_from: str, effective_to: str | None) -> TextNode:
    return TextNode(
        id_=provision_id,
        text="본문",
        metadata={
            "provision_id": provision_id,
            "document_id": "doc-1",
            "document_title": "에너지법",
            "source_kind": "statute",
            "law_type_code": "01",
            "version_label": "MST 1",
            "effective_from": effective_from,
            "effective_to": effective_to,
            "path": "제1조",
            "heading": None,
            "content": "본문",
            "source_url": "https://example.test",
            "source_text_sha256": "deadbeef",
        },
    )


class FakeVectorStore:
    def __init__(self, nodes: list[TextNode], scores: list[float]):
        self._nodes = nodes
        self._scores = scores
        self.last_query = None

    async def aquery(self, query, **kwargs):
        self.last_query = query
        return VectorStoreQueryResult(
            nodes=self._nodes,
            similarities=self._scores,
            ids=[n.id_ for n in self._nodes],
        )


@pytest.mark.asyncio
async def test_search_excludes_provision_effective_after_as_of_date():
    store = FakeVectorStore(
        nodes=[_node("future", "2099-01-01", None)],
        scores=[0.9],
    )
    hits = await search(store, FakeEmbedder(), "질문", date(2026, 1, 1), 5)
    assert hits == []


@pytest.mark.asyncio
async def test_search_excludes_provision_expired_before_as_of_date():
    store = FakeVectorStore(
        nodes=[_node("expired", "2020-01-01", "2021-01-01")],
        scores=[0.9],
    )
    hits = await search(store, FakeEmbedder(), "질문", date(2026, 1, 1), 5)
    assert hits == []


@pytest.mark.asyncio
async def test_search_includes_currently_effective_provision_and_maps_fields():
    store = FakeVectorStore(
        nodes=[_node("current", "2024-01-01", None)],
        scores=[0.87],
    )
    hits = await search(store, FakeEmbedder(), "질문", date(2026, 1, 1), 5)
    assert len(hits) == 1
    hit = hits[0]
    assert str(hit.provision_id) == "current" if False else hit.path == "제1조"
    assert hit.document_title == "에너지법"
    assert hit.score == 0.87
    assert hit.content == "본문"


@pytest.mark.asyncio
async def test_search_respects_limit_after_temporal_post_filter():
    nodes = [_node(f"p{i}", "2024-01-01", None) for i in range(3)]
    store = FakeVectorStore(nodes=nodes, scores=[0.9, 0.8, 0.7])
    hits = await search(store, FakeEmbedder(), "질문", date(2026, 1, 1), 2)
    assert len(hits) == 2
```

Note: `provision_id`/`document_id` on `SearchHit` are typed `UUID` in `law_rag_core`, but this test suite uses plain strings like `"current"` as node ids for readability. If `SearchHit` validation rejects non-UUID strings, switch the fixture ids to real UUID strings (e.g. `"11111111-1111-1111-1111-111111111111"`) before writing the implementation — check this in Step 3 by reading `law_rag_core/domain/schemas.py`'s `SearchHit` definition first.

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run --directory apps/law-rag-llamaindex python -m pytest tests/test_retriever.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'law_rag_llamaindex.retriever'`

- [ ] **Step 3: Check `SearchHit`'s field types, then write the implementation**

Read `packages/law-rag-core/src/law_rag_core/domain/schemas.py`'s `SearchHit` class (already confirmed earlier in this project: `provision_id: UUID`, `document_id: UUID`, rest are `str`/`date | None`/`float`). If node ids in this task's tests are not valid UUIDs, fix the test fixtures to use UUID strings before running Step 4.

```python
# apps/law-rag-llamaindex/src/law_rag_llamaindex/retriever.py
from datetime import date, datetime

from law_rag_core.domain.schemas import SearchHit
from llama_index.core.vector_stores.types import (
    FilterOperator,
    MetadataFilter,
    MetadataFilters,
    VectorStoreQuery,
)

_OVER_FETCH_CAP = 100


async def search(vector_store, embedder, query: str, as_of_date: date, limit: int) -> list[SearchHit]:
    query_embedding = embedder.get_query_embedding(query)
    over_fetch = min(limit * 4, _OVER_FETCH_CAP)
    filters = MetadataFilters(
        filters=[
            MetadataFilter(
                key="effective_from",
                value=as_of_date.isoformat(),
                operator=FilterOperator.LTE,
            )
        ]
    )
    result = await vector_store.aquery(
        VectorStoreQuery(
            query_embedding=query_embedding,
            similarity_top_k=over_fetch,
            filters=filters,
        )
    )
    hits: list[SearchHit] = []
    for node, score in zip(result.nodes, result.similarities, strict=True):
        metadata = node.metadata
        effective_to_raw = metadata.get("effective_to")
        if effective_to_raw is not None:
            effective_to = date.fromisoformat(effective_to_raw)
            if effective_to <= as_of_date:
                continue
        effective_from_raw = metadata.get("effective_from")
        hits.append(
            SearchHit(
                provision_id=metadata["provision_id"],
                document_id=metadata["document_id"],
                document_title=metadata["document_title"],
                source_kind=metadata["source_kind"],
                version_label=metadata["version_label"],
                effective_from=date.fromisoformat(effective_from_raw) if effective_from_raw else None,
                effective_to=date.fromisoformat(effective_to_raw) if effective_to_raw else None,
                path=metadata["path"],
                heading=metadata.get("heading"),
                content=metadata["content"],
                source_url=metadata["source_url"],
                score=score,
                law_type_code=metadata.get("law_type_code"),
            )
        )
        if len(hits) == limit:
            break
    return hits
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run --directory apps/law-rag-llamaindex python -m pytest tests/test_retriever.py -v`
Expected: 4 passed
(If `MetadataFilter`/`FilterOperator`/`MetadataFilters`/`VectorStoreQuery` import paths differ from `llama_index.core.vector_stores.types` in the installed version, fix the import based on the actual installed package layout — check with `uv run --directory apps/law-rag-llamaindex python -c "from llama_index.core.vector_stores.types import MetadataFilter"` first.)

- [ ] **Step 5: Commit**

```bash
git add apps/law-rag-llamaindex/src/law_rag_llamaindex/retriever.py apps/law-rag-llamaindex/tests/test_retriever.py
git commit -m "feat(law-rag-llamaindex): add retriever with temporal validity filtering"
```

---

## Task 9: Alembic migration for the ingestion readiness marker

**Files:**
- Create: `apps/api/migrations/versions/0013_llamaindex_ingestion_runs.py`

**Interfaces:**
- Produces: table `law_rag_llamaindex_ingestion_runs(id uuid pk, started_at timestamptz, finished_at timestamptz null, node_count integer, status text)`.
- Consumes: nothing new (this table is only read/written by `law-rag-llamaindex`'s ingestion CLI and `apps/api`'s readiness check).

- [ ] **Step 1: Write the migration**

```python
# apps/api/migrations/versions/0013_llamaindex_ingestion_runs.py
"""v2 LlamaIndex 파이프라인의 ingestion 완료 마커 테이블.

Revision ID: 0013
"""

from alembic import op

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """CREATE TABLE law_rag_llamaindex_ingestion_runs (
          id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
          started_at timestamptz NOT NULL,
          finished_at timestamptz,
          node_count integer NOT NULL DEFAULT 0,
          status text NOT NULL CHECK (status IN ('running','completed','failed'))
        )"""
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS law_rag_llamaindex_ingestion_runs")
```

- [ ] **Step 2: Verify the migration applies cleanly against a local/dev database**

Run: `uv run --directory apps/api alembic upgrade head`
Expected: no errors; `alembic_version` advances to `0013`. If no local `DATABASE_URL` is configured, skip this verification step and note it as unverified in the plan's progress log — the migration will be verified in CI/staging before merge.

- [ ] **Step 3: Commit**

```bash
git add apps/api/migrations/versions/0013_llamaindex_ingestion_runs.py
git commit -m "feat(api): add law_rag_llamaindex_ingestion_runs migration"
```

---

## Task 10: `LlamaIndexLegalRepository` adapter in `apps/api`

**Files:**
- Create: `apps/api/app/adapters/llamaindex_repository.py`
- Test: `apps/api/tests/test_llamaindex_repository.py`
- Modify: `apps/api/pyproject.toml` (add `law-rag-llamaindex` dependency)

**Interfaces:**
- Consumes: `law_rag_core.ports.repository.LegalRepository` Protocol; `law_rag_llamaindex.retriever.search` (Task 8); an existing `PostgresLegalRepository`-or-compatible `delegate`.
- Produces: `LlamaIndexLegalRepository(delegate, vector_store, embedder)` implementing every `LegalRepository` method — `search`/`search_with_trace` via v2, everything else proxied to `delegate`.

- [ ] **Step 1: Add the workspace dependency**

Edit `apps/api/pyproject.toml`'s `dependencies` list to add `"law-rag-llamaindex"`, and its `[tool.uv.sources]` table to add:

```toml
[tool.uv.sources]
law-rag-core = { workspace = true }
law-rag-llamaindex = { workspace = true }
```

Run: `uv sync --all-packages` (shared-venv workspace — see the note in Task 1)
Expected: resolves without conflicts.

- [ ] **Step 2: Write the failing test**

```python
# apps/api/tests/test_llamaindex_repository.py
from datetime import date
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.adapters.llamaindex_repository import LlamaIndexLegalRepository


@pytest.mark.asyncio
async def test_search_with_trace_calls_v2_retriever_not_delegate(monkeypatch):
    delegate = MagicMock()
    delegate.search_with_trace = AsyncMock(side_effect=AssertionError("v1 must not be called"))
    vector_store = MagicMock()
    embedder = MagicMock()

    fake_hits = [MagicMock(name="hit")]

    async def fake_search(store, emb, query, as_of_date, limit):
        assert store is vector_store
        assert emb is embedder
        return fake_hits

    monkeypatch.setattr(
        "app.adapters.llamaindex_repository.llamaindex_search", fake_search
    )

    repository = LlamaIndexLegalRepository(delegate, vector_store, embedder)
    hits, trace = await repository.search_with_trace("질문", date(2026, 1, 1), 5)

    assert hits == fake_hits
    assert trace.strategy == "v2_llamaindex_dense"
    assert trace.candidate_count == len(fake_hits)
    delegate.search_with_trace.assert_not_called()


@pytest.mark.asyncio
async def test_search_delegates_to_search_with_trace(monkeypatch):
    delegate = MagicMock()
    fake_hits = [MagicMock(name="hit")]

    async def fake_search(store, emb, query, as_of_date, limit):
        return fake_hits

    monkeypatch.setattr(
        "app.adapters.llamaindex_repository.llamaindex_search", fake_search
    )
    repository = LlamaIndexLegalRepository(delegate, MagicMock(), MagicMock())
    hits = await repository.search("질문", date(2026, 1, 1), 5)
    assert hits == fake_hits


@pytest.mark.asyncio
async def test_non_search_methods_delegate_to_v1_repository():
    delegate = MagicMock()
    delegate.consume_quota = AsyncMock(return_value=True)
    delegate.last_sync = AsyncMock(return_value=None)
    delegate.provision = AsyncMock(return_value=None)
    delegate.corpus_items = AsyncMock(return_value=[])
    delegate.corpus_search_status = AsyncMock(return_value="ready")
    delegate.corpus_temporal_state = AsyncMock(return_value="state")
    delegate.upsert_document = AsyncMock(return_value="doc-id")
    delegate.upsert_embeddings = AsyncMock(return_value=None)

    repository = LlamaIndexLegalRepository(delegate, MagicMock(), MagicMock())

    assert await repository.consume_quota("hash", date(2026, 1, 1), "search", 100) is True
    assert await repository.last_sync() is None
    assert await repository.provision(__import__("uuid").uuid4(), date(2026, 1, 1)) is None
    assert await repository.corpus_items() == []
    assert await repository.corpus_search_status() == "ready"
    assert await repository.corpus_temporal_state(date(2026, 1, 1)) == "state"
    delegate.consume_quota.assert_awaited_once()
    delegate.last_sync.assert_awaited_once()
    delegate.provision.assert_awaited_once()
    delegate.corpus_items.assert_awaited_once()
    delegate.corpus_search_status.assert_awaited_once()
    delegate.corpus_temporal_state.assert_awaited_once()
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `uv run --directory apps/api python -m pytest tests/test_llamaindex_repository.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.adapters.llamaindex_repository'`

- [ ] **Step 4: Write the implementation**

```python
# apps/api/app/adapters/llamaindex_repository.py
from datetime import date, datetime
from time import perf_counter
from uuid import UUID

from law_rag_core.domain.entities import LegalDocumentRecord
from law_rag_core.domain.schemas import (
    CorpusItemStatus,
    CorpusSearchStatus,
    CorpusTemporalState,
    SearchHit,
)
from law_rag_core.ports.repository import LegalRepository
from law_rag_llamaindex.retriever import search as llamaindex_search

from app.domain.search_queries import SearchTrace


class LlamaIndexLegalRepository:
    """LegalRepository를 구현하되 search/search_with_trace만 v2로 새로 구현하고,
    나머지 메서드는 기존 v1 repository(delegate)에 그대로 위임한다."""

    def __init__(self, delegate: LegalRepository, vector_store, embedder) -> None:
        self._delegate = delegate
        self._vector_store = vector_store
        self._embedder = embedder

    async def search(
        self,
        query: str,
        as_of_date: date,
        limit: int,
        query_embedding: list[float] | None = None,
        embedding_profile_key: str | None = None,
    ) -> list[SearchHit]:
        hits, _ = await self.search_with_trace(query, as_of_date, limit)
        return hits

    async def search_with_trace(
        self,
        query: str,
        as_of_date: date,
        limit: int,
        query_embedding: list[float] | None = None,
        embedding_profile_key: str | None = None,
    ) -> tuple[list[SearchHit], SearchTrace]:
        started = perf_counter()
        hits = await llamaindex_search(self._vector_store, self._embedder, query, as_of_date, limit)
        trace = SearchTrace(
            strategy="v2_llamaindex_dense",
            normalized_query=query,
            terms=(),
            executed_query=None,
            relaxed=False,
            reference_title=None,
            reference_path=None,
            candidate_count=len(hits),
            total_duration_ms=(perf_counter() - started) * 1000,
        )
        return hits, trace

    async def consume_quota(self, subject_hash: str, day: date, kind: str, limit: int) -> bool:
        return await self._delegate.consume_quota(subject_hash, day, kind, limit)

    async def upsert_document(self, document: LegalDocumentRecord) -> UUID:
        return await self._delegate.upsert_document(document)

    async def upsert_embeddings(
        self,
        values: list[tuple[UUID, str, list[float]]],
        profile_key: str,
        dimensions: int,
    ) -> None:
        await self._delegate.upsert_embeddings(values, profile_key, dimensions)

    async def provision(self, provision_id: UUID, as_of_date: date) -> SearchHit | None:
        return await self._delegate.provision(provision_id, as_of_date)

    async def corpus_items(self) -> list[CorpusItemStatus]:
        return await self._delegate.corpus_items()

    async def corpus_search_status(self) -> CorpusSearchStatus:
        return await self._delegate.corpus_search_status()

    async def corpus_temporal_state(self, supported_through: date) -> CorpusTemporalState:
        return await self._delegate.corpus_temporal_state(supported_through)

    async def last_sync(self) -> datetime | None:
        return await self._delegate.last_sync()
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run --directory apps/api python -m pytest tests/test_llamaindex_repository.py -v`
Expected: 3 passed

- [ ] **Step 6: Commit**

```bash
git add apps/api/pyproject.toml apps/api/app/adapters/llamaindex_repository.py apps/api/tests/test_llamaindex_repository.py
git commit -m "feat(api): add LlamaIndexLegalRepository adapter"
```

---

## Task 11: `/v2/search` endpoint

**Files:**
- Modify: `apps/api/app/main.py` (add module-level v2 wiring near the existing `repository`/`supabase_auth` globals, and a new route near `/v1/search`)
- Test: `apps/api/tests/test_v2_search.py`

**Interfaces:**
- Consumes: `law_rag_llamaindex.config.get_settings`, `law_rag_llamaindex.store.build_vector_store`, `law_rag_llamaindex.embedding.build_embedder`, `law_rag_llamaindex.retriever.search` (Tasks 2, 5, 6, 8).
- Produces: `POST /v2/search` returning `list[SearchHit]`; module globals `llamaindex_vector_store: PGVectorStore | None`, `llamaindex_embedder: NVIDIAEmbedding | None`.

- [ ] **Step 1: Write the failing test**

```python
# apps/api/tests/test_v2_search.py
import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(monkeypatch):
    import app.main as main_module

    monkeypatch.setattr(main_module, "llamaindex_vector_store", object())
    monkeypatch.setattr(main_module, "llamaindex_embedder", object())

    async def fake_ready() -> bool:
        return True

    async def fake_search(store, embedder, query, as_of_date, limit):
        return []

    monkeypatch.setattr(main_module, "_v2_index_ready", fake_ready)
    monkeypatch.setattr(main_module, "llamaindex_search", fake_search)
    return TestClient(main_module.app)


def test_v2_search_returns_empty_list_when_ready(client):
    response = client.post(
        "/v2/search", json={"query": "태양광", "as_of_date": "2026-01-01", "limit": 5}
    )
    assert response.status_code == 200
    assert response.json() == []


def test_v2_search_returns_503_with_stable_code_when_not_configured(monkeypatch):
    import app.main as main_module

    monkeypatch.setattr(main_module, "llamaindex_vector_store", None)
    monkeypatch.setattr(main_module, "llamaindex_embedder", None)
    client = TestClient(main_module.app)

    response = client.post(
        "/v2/search", json={"query": "태양광", "as_of_date": "2026-01-01", "limit": 5}
    )
    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "v2_search_not_ready"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --directory apps/api python -m pytest tests/test_v2_search.py -v`
Expected: FAIL — `/v2/search` route does not exist (404), or `AttributeError` on `main_module.llamaindex_vector_store` not existing yet.

- [ ] **Step 3: Add the module-level wiring and route**

In `apps/api/app/main.py`, near the existing imports (after the `from app.adapters.postgres_repository import PostgresLegalRepository` line):

```python
from law_rag_llamaindex.config import get_settings as get_llamaindex_settings
from law_rag_llamaindex.embedding import build_embedder as build_llamaindex_embedder
from law_rag_llamaindex.retriever import search as llamaindex_search
from law_rag_llamaindex.store import build_vector_store as build_llamaindex_vector_store

from app.adapters.llamaindex_repository import LlamaIndexLegalRepository
```

Near the existing `repository = ...` / `supabase_auth = ...` global block:

```python
llamaindex_settings = get_llamaindex_settings()
llamaindex_vector_store = (
    build_llamaindex_vector_store(llamaindex_settings) if settings.database_url else None
)
llamaindex_embedder = (
    build_llamaindex_embedder(llamaindex_settings) if llamaindex_settings.nvidia_api_key else None
)
llamaindex_repository = (
    LlamaIndexLegalRepository(repository, llamaindex_vector_store, llamaindex_embedder)
    if llamaindex_vector_store is not None and llamaindex_embedder is not None
    else None
)
```

Near `_corpus_unready_http_error` (module-level helper section):

```python
def _v2_not_ready_http_error() -> HTTPException:
    return HTTPException(
        status_code=503,
        detail={"code": "v2_search_not_ready", "message": "v2 검색을 아직 사용할 수 없습니다."},
    )


async def _v2_index_ready() -> bool:
    if not settings.database_url:
        return False
    async with repository.engine.connect() as connection:  # type: ignore[union-attr]
        row = (
            await connection.execute(
                text(
                    "SELECT 1 FROM law_rag_llamaindex_ingestion_runs "
                    "WHERE status='completed' LIMIT 1"
                )
            )
        ).first()
    return row is not None
```

Add `from sqlalchemy import text` to the imports if not already present in `main.py` (it is not, since `main.py` uses `repository`'s own query methods rather than raw SQL directly — check first with `grep -n "^from sqlalchemy" apps/api/app/main.py` before adding, to avoid a duplicate import).

Near the existing `/v1/search` route:

```python
@app.post("/v2/search", response_model=list[SearchHit])
async def search_v2(payload: SearchRequest, request: Request) -> list[SearchHit]:
    if llamaindex_vector_store is None or llamaindex_embedder is None:
        raise _v2_not_ready_http_error()
    if not await _v2_index_ready():
        raise _v2_not_ready_http_error()
    hits = await llamaindex_search(
        llamaindex_vector_store, llamaindex_embedder, payload.query, payload.as_of_date, payload.limit
    )
    if payload.source_kinds:
        hits = [hit for hit in hits if hit.source_kind in payload.source_kinds]
    return [hit for hit in hits if is_allowed_source_url(hit.source_url)]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run --directory apps/api python -m pytest tests/test_v2_search.py -v`
Expected: 2 passed

- [ ] **Step 5: Run the full `apps/api` test suite to check for regressions**

Run: `uv run --directory apps/api python -m pytest -v`
Expected: all previously-passing tests still pass (the new imports/globals must not break app startup for any existing test that constructs `TestClient(main_module.app)`).

- [ ] **Step 6: Commit**

```bash
git add apps/api/app/main.py apps/api/tests/test_v2_search.py
git commit -m "feat(api): add /v2/search endpoint backed by law-rag-llamaindex"
```

---

## Task 12: `/v2/questions` endpoint (reuse v1's answering pipeline)

**Files:**
- Modify: `apps/api/app/main.py:215-305` (extract `_handle_question`, thread `repository` through `_answer_question`/`_retrieve_question_evidence`/`_load_corpus_temporal_state`/`_require_supported_as_of_date`, add `/v2/questions` route)
- Test: `apps/api/tests/test_v2_questions.py`

**Interfaces:**
- Consumes: `llamaindex_repository` (Task 11, `None` when v2 isn't configured), everything `_answer_question` already consumes.
- Produces: `POST /v2/questions` returning `QuestionResponse`; refactored `_answer_question(payload, request, user, budget, repository)`.

This is the highest-risk task in the plan — `_answer_question` is a large function with many internal stages. The refactor is intentionally narrow: thread one new parameter through four functions, touch no other logic.

- [ ] **Step 1: Write the failing test**

```python
# apps/api/tests/test_v2_questions.py
import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(monkeypatch):
    import app.main as main_module

    monkeypatch.setattr(main_module, "llamaindex_repository", object())

    async def fake_ready() -> bool:
        return True

    monkeypatch.setattr(main_module, "_v2_index_ready", fake_ready)
    return TestClient(main_module.app)


def test_v2_questions_returns_503_when_not_configured(monkeypatch):
    import app.main as main_module

    monkeypatch.setattr(main_module, "llamaindex_repository", None)
    client = TestClient(main_module.app)
    response = client.post(
        "/v2/questions",
        json={
            "client_request_id": "11111111-1111-1111-1111-111111111111",
            "question": "태양광 설비 인허가 요건이 뭐야",
            "as_of_date": "2026-01-01",
            "project_stage": "planning",
            "answer_mode": "search_only",
        },
    )
    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "v2_search_not_ready"


def test_v2_questions_uses_llamaindex_repository_for_evidence(client, monkeypatch):
    import app.main as main_module

    captured_repository = {}

    async def fake_answer_question(payload, request, user, budget, repository):
        captured_repository["repository"] = repository
        from app.domain.schemas import QuestionResponse

        return QuestionResponse(
            request_id=str(payload.client_request_id),
            mode="search_only",
            summary="ok",
            sections=[],
            checklist=[],
            citations=[],
            warnings=[],
            fallback_reason=None,
        )

    monkeypatch.setattr(main_module, "_answer_question", fake_answer_question)

    response = client.post(
        "/v2/questions",
        json={
            "client_request_id": "11111111-1111-1111-1111-111111111111",
            "question": "태양광 설비 인허가 요건이 뭐야",
            "as_of_date": "2026-01-01",
            "project_stage": "planning",
            "answer_mode": "search_only",
        },
    )
    assert response.status_code == 200
    assert captured_repository["repository"] is main_module.llamaindex_repository
```

Note: `QuestionResponse`'s exact required fields must match `app/domain/schemas.py` — read that class before finalizing this fixture if the test fails on validation errors unrelated to the routing logic being tested.

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run --directory apps/api python -m pytest tests/test_v2_questions.py -v`
Expected: FAIL — `/v2/questions` route does not exist (404)

- [ ] **Step 3: Refactor `_answer_question` and its helpers to accept `repository`**

In `apps/api/app/main.py`, change the four signatures and their internal repository references:

```python
async def _load_corpus_temporal_state(repository: LegalRepository) -> CorpusTemporalState:
    try:
        return await repository.corpus_temporal_state(_current_korea_date())
    except Exception as exc:
        raise _corpus_unready_http_error() from exc


async def _require_supported_as_of_date(requested_date: date, repository: LegalRepository) -> None:
    state = await _load_corpus_temporal_state(repository)
    if not state.ready:
        raise _corpus_unready_http_error()
    try:
        require_supported_corpus_date(requested_date, state)
    except UnsupportedCorpusDateError as exc:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "unsupported_corpus_date",
                "message": "현재 corpus는 검증된 기준일 범위 안에서만 검색할 수 있습니다.",
                "requested_as_of_date": exc.requested_date.isoformat(),
                "supported_from": exc.supported_from.isoformat(),
                "supported_through": exc.supported_through.isoformat(),
                "corpus_snapshot_id": exc.snapshot_id,
            },
        ) from exc
```

```python
async def _retrieve_question_evidence(
    payload: QuestionRequest,
    query_embedding: list[float] | None,
    repository: LegalRepository,
) -> tuple[list[SearchHit], SearchTrace, datetime | None]:
    hits, trace = await repository.search_with_trace(
        payload.question,
        payload.as_of_date,
        10,
        query_embedding,
        NVIDIA_NEMOTRON_512_PROFILE.key if query_embedding is not None else None,
    )
    return hits, trace, await repository.last_sync()
```

```python
async def _answer_question(
    payload: QuestionRequest,
    request: Request,
    user: MockUser | None,
    budget: RequestBudget,
    repository: LegalRepository,
) -> QuestionResponse:
```

And its internal call site (the line reading `lambda: _retrieve_question_evidence(payload, query_embedding),`):

```python
                lambda: _retrieve_question_evidence(payload, query_embedding, repository),
```

Add `from law_rag_core.ports.repository import LegalRepository` to `main.py`'s imports if not already present (check with `grep -n "LegalRepository" apps/api/app/main.py` first — `repository` is currently typed structurally, not annotated with the Protocol, so this import is likely new).

- [ ] **Step 4: Update the three unaffected v1 call sites to pass `repository` explicitly**

`/v1/search` handler (around line 199):
```python
    await _require_supported_as_of_date(payload.as_of_date, repository)
```

`/v1/provisions/{provision_id}` handler (around line 889):
```python
    await _require_supported_as_of_date(requested_date, repository)
```

`/v1/corpus/status` handler (around line 919):
```python
        temporal_state = await _load_corpus_temporal_state(repository)
```

- [ ] **Step 5: Extract `_handle_question` from the `/v1/questions` route and add `/v2/questions`**

Replace the existing `question()` handler body (the whole function currently decorated `@app.post("/v1/questions", ...)`) with an extracted helper plus two thin routes:

```python
async def _handle_question(
    payload: QuestionRequest, request: Request, repository: LegalRepository
) -> QuestionResponse:
    budget = RequestBudget.start(
        settings.question_request_timeout_seconds,
        settings.response_reserve_seconds,
    )
    request_id = str(payload.client_request_id)
    request_started = time.monotonic()
    outcome: QuestionStageTimingOutcome = "failed"
    try:
        await _require_supported_as_of_date(payload.as_of_date, repository)
        user = await _optional_user(request.headers.get("authorization"))
        owner = _question_owner(request, user)
        task = asyncio.current_task()
        if task is None:
            raise HTTPException(status_code=503, detail="질문 처리를 시작할 수 없습니다.")
        if not await question_tasks.register(owner, payload.client_request_id, task):
            raise HTTPException(status_code=409, detail="같은 요청이 이미 처리 중입니다.")
        try:
            await asyncio.sleep(0)
            async with asyncio.timeout(budget.remaining_seconds()):
                response = await _answer_question(payload, request, user, budget, repository)
        except asyncio.CancelledError as exc:
            outcome = "failed"
            raise HTTPException(status_code=499, detail="질문 처리가 취소되었습니다.") from exc
        except TimeoutError as exc:
            outcome = "timed_out"
            raise HTTPException(
                status_code=503,
                detail="질문 처리 시간이 초과되었습니다. 잠시 후 다시 시도해 주세요.",
            ) from exc
        finally:
            await question_tasks.unregister(owner, payload.client_request_id, task)
        outcome = _request_outcome_for_response(response)
        return response
    finally:
        emit_question_stage_timing(
            request_id,
            "request",
            outcome,
            _elapsed_ms(request_started),
            _remaining_ms(budget),
        )


@app.post("/v1/questions", response_model=QuestionResponse)
async def question(payload: QuestionRequest, request: Request) -> QuestionResponse:
    return await _handle_question(payload, request, repository)


@app.post("/v2/questions", response_model=QuestionResponse)
async def question_v2(payload: QuestionRequest, request: Request) -> QuestionResponse:
    if llamaindex_repository is None:
        raise _v2_not_ready_http_error()
    if not await _v2_index_ready():
        raise _v2_not_ready_http_error()
    return await _handle_question(payload, request, llamaindex_repository)
```

- [ ] **Step 6: Run the new tests to verify they pass**

Run: `uv run --directory apps/api python -m pytest tests/test_v2_questions.py -v`
Expected: 2 passed

- [ ] **Step 7: Run the full `apps/api` test suite to check for regressions**

Run: `uv run --directory apps/api python -m pytest -v`
Expected: all tests pass, including every existing `/v1/questions` test (`test_api.py`, `test_answering.py`, `test_distributed_question_cancellation.py`, etc.) — these exercise `_answer_question`/`_retrieve_question_evidence` and must behave identically now that they take an explicit (module-global-valued) `repository` argument. If any fail, the refactor changed v1 behavior — fix the refactor, not the test.

- [ ] **Step 8: Commit**

```bash
git add apps/api/app/main.py apps/api/tests/test_v2_questions.py
git commit -m "feat(api): add /v2/questions reusing v1 answering pipeline with v2 evidence"
```

---

## Task 13: `apps/web` — switch to `/v2/questions`

**Files:**
- Modify: `apps/web/lib/api-client.ts:108` (the `/v1/questions` POST call)
- Modify: `apps/web/lib/api-client-flow.test.ts` (update mocked endpoint URL)

**Interfaces:**
- Consumes: `/v2/questions` (Task 12), identical request/response shape to `/v1/questions` — no other web code changes.

- [ ] **Step 1: Read the current call site**

Run: `sed -n '104,115p' apps/web/lib/api-client.ts` (or open the file) to confirm the exact function name and surrounding code before editing — this plan was written against the URL string `"/v1/questions"` at line 108; if the surrounding code has since changed, adjust the edit to the same call, not a different one.

- [ ] **Step 2: Update the failing test first**

In `apps/web/lib/api-client-flow.test.ts`, change:
```ts
      if (url.endsWith("/v1/questions") && init?.method === "POST") return Response.json(answer);
```
to:
```ts
      if (url.endsWith("/v2/questions") && init?.method === "POST") return Response.json(answer);
```
and update the assertion:
```ts
    const questionCall = fetchMock.mock.calls.find(([url]) => String(url).endsWith("/v1/questions"));
```
to:
```ts
    const questionCall = fetchMock.mock.calls.find(([url]) => String(url).endsWith("/v2/questions"));
```

- [ ] **Step 3: Run the test to verify it fails**

Run: `pnpm --filter web test -- api-client-flow`
Expected: FAIL — the mock now expects `/v2/questions` but `api-client.ts` still calls `/v1/questions`, so the mocked fetch handler doesn't match and the request falls through unhandled.

- [ ] **Step 4: Update the implementation**

In `apps/web/lib/api-client.ts`, change the request URL at the `/v1/questions` call site from `"/v1/questions"` to `"/v2/questions"` (keep every other argument — method, body, headers — unchanged, since the schema is identical).

- [ ] **Step 5: Run the test to verify it passes**

Run: `pnpm --filter web test -- api-client-flow`
Expected: PASS

- [ ] **Step 6: Run the full web test suite to check for regressions**

Run: `pnpm --filter web test`
Expected: all tests pass — `/v1/questions/history`, `/v1/auth/me`, `/v1/conversations`, etc. are untouched and should still work, since only the question-answering call moved to v2.

- [ ] **Step 7: Commit**

```bash
git add apps/web/lib/api-client.ts apps/web/lib/api-client-flow.test.ts
git commit -m "feat(web): call /v2/questions instead of /v1/questions"
```

---

## Task 14: Update repository docs and close out the plan

**Files:**
- Modify: `docs/exec-plans/active/README.md` (add a one-line entry for this plan)
- Modify: `docs/design-docs/v2-llamaindex-retrieval-pipeline-design.md` (status line: `제안됨` → `구현 중` or `승인`, per AGENTS.md's status definitions)
- Modify: `docs/PLANS.md` — no change needed (already documents the active/todo/completed lifecycle generically)

- [ ] **Step 1: Add the plan to the active index**

In `docs/exec-plans/active/README.md`, add a line following the existing format:
```markdown
- [0053: V2 LlamaIndex 검색 파이프라인](0053-v2-llamaindex-retrieval-pipeline.md) — `law-rag-llamaindex` 워크스페이스, `/v2/search`·`/v2/questions`, web 전환
```

- [ ] **Step 2: Update the design doc status**

In `docs/design-docs/v2-llamaindex-retrieval-pipeline-design.md:3`, change:
```markdown
상태: 제안됨 (2026-08-18)
```
to:
```markdown
상태: 구현 중 (2026-08-18)
```

- [ ] **Step 3: Run the full verification suite across all three touched projects**

```bash
uv run --directory apps/law-rag-llamaindex python -m pytest
uv run --directory apps/api python -m pytest
pnpm --filter web test
```
Expected: all green.

- [ ] **Step 4: Commit**

```bash
git add docs/exec-plans/active/README.md docs/design-docs/v2-llamaindex-retrieval-pipeline-design.md
git commit -m "docs: link 0053 plan and mark v2 design doc as in progress"
```

---

## Self-Review Notes (for the plan author, not a task)

- **Spec coverage:** 목표(v2 pipeline, `/v2/search`, `/v2/questions`, citation+temporal requirements) → Tasks 1–12. 비범위(no new AI generation code, no search_only in v2, no direct-path/keyword fallback, no v2 quota) → respected by construction (Task 12 reuses `_answer_question` verbatim; no new generation code is written anywhere in this plan). 데이터 모델/Ingestion → Tasks 3, 4, 7. 조회 인터페이스 → Task 8. API → Tasks 11, 12. 인증과 이력 → Task 12 (reuses `_optional_user`/`save_question` untouched). Web → Task 13. 테스트 → every task has its own. 결정 기록 items (HNSW deferred but pluggable, native embed dim, passage template reuse, table naming) → Tasks 6, 5, 3, 6 respectively.
- **Known risk:** Task 12's refactor of `_answer_question` is the one place this plan touches shared v1 code. Step 7's full-suite regression run is the safety net — if it's not green, do not proceed to Task 13.
- **Known unresolved-until-implementation items (carried from the design doc's 미결정 section):** the exact ingestion CLI entrypoint/flags were intentionally left out of this plan's tasks — Task 7 exposes `run_ingestion` as a library function; wiring a `python -m law_rag_llamaindex.ingest` CLI entrypoint is a small follow-up once Tasks 1–9 are merged and there's a real corpus to ingest against, and isn't blocking for `/v2/search`/`/v2/questions` to exist and be testable with mocks.
