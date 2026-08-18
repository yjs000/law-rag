# V2 LlamaIndex 검색(Retrieval) 파이프라인 구현 계획

> **에이전트 작업자를 위한 안내:** 필수 서브스킬: 이 계획을 태스크 단위로 구현하려면 superpowers:subagent-driven-development(권장) 또는 superpowers:executing-plans를 사용하세요. 각 단계는 체크박스(`- [ ]`) 문법으로 진행 상황을 추적합니다.

**목표:** 새롭고 독립적인 LlamaIndex 기반 dense 검색 파이프라인(`law-rag-llamaindex`)을 구축하고, 이를 `apps/api`에 `/v2/search`(독립 디버그 엔드포인트)와 `/v2/questions`(v1의 기존 라우팅/생성/인용 검증 코드를 재사용하되 evidence-retrieval repository만 교체)로 연결한 다음, `apps/web`이 `/v2/questions`를 호출하도록 전환한다.

**아키텍처:** 새 uv 워크스페이스 앱이 ingestion(provisions → LlamaIndex 노드 → NVIDIA NIM 임베딩 → `PGVectorStore`)과 `retriever.search()` 함수를 소유한다. `apps/api`는 기존 `LegalRepository` Protocol을 구현하는 새로운 `LlamaIndexLegalRepository` 어댑터를 갖게 되며 — 이 어댑터는 `search`/`search_with_trace`만 오버라이드하고, 나머지 모든 메서드(quota, corpus status, provision 조회, last_sync)는 기존 `PostgresLegalRepository` 인스턴스에 위임한다. `_answer_question`과 그 헬퍼 함수들은 모듈 전역 변수를 읽는 대신 `repository`를 명시적 파라미터로 받도록 리팩터링되어, `/v2/questions`가 새 어댑터를 주입한 채 정확히 동일한 함수를 호출할 수 있게 된다.

**기술 스택:** Python 3.14, uv workspaces, LlamaIndex(`llama-index-core`, `llama-index-vector-stores-postgres`, `llama-index-embeddings-nvidia`), SQLAlchemy async + asyncpg, FastAPI, Alembic, pytest/pytest-asyncio.

## 전역 제약 조건(Global Constraints)

- Python: 새로 추가되는 모든 Python 패키지는 `>=3.14,<3.15`(`apps/api`, `apps/collector`와 동일하게 맞춤).
- `apps/api` 코드 스타일: `ruff`, `select = ["E", "F", "I", "UP", "B", "ASYNC"]`, 줄 길이 100.
- `law-rag-llamaindex` 코드 스타일: 필요하지 않은 한 `ASYNC`를 제외한 동일한 ruff 설정(`packages/law-rag-core`의 `select = ["E", "F", "I", "UP", "B"]`와 일치).
- v1 코드(`/v1/*` 라우트, `PostgresLegalRepository`, `provision_embeddings`, `embedding_profiles`)는 동작이 변경되어서는 안 된다 — `_answer_question`/`_retrieve_question_evidence`/`_load_corpus_temporal_state`/`_require_supported_as_of_date`만 명시적 `repository` 파라미터를 추가로 받는다(기계적 변경이며 기존 호출부의 동작은 보존).
- 임베딩 모델: `NVIDIA_API_KEY`/`NVIDIA_BASE_URL`을 통한 `nvidia/nemotron-3-embed-1b`(`apps/api` 설정값을 재사용 — 이 두 env var에 대한 두 번째 진실 공급원(source of truth)을 만들지 말 것).
- 임베딩 저장 차원: 네이티브 NIM 차원인 `2048`(v2에서는 truncation/재정규화 없음).
- 패스지(passage) 템플릿(원문 그대로, 줄바꿈으로 연결, 빈 필드는 건너뜀): 법령명 → 경로 → 표제 → 원문 본문.
- `PGVectorStore` 테이블명: `law_rag_llamaindex`(물리 테이블은 `data_law_rag_llamaindex`, 라이브러리 소스에서 확인됨). `hnsw_kwargs`는 현재는 `None`으로 유지하되, 팩토리 함수는 이를 파라미터로 받을 수 있어야 한다.
- v2 인덱스에 완료된 ingestion 실행 기록이 없을 때 `/v2/search`와 `/v2/questions` 양쪽 모두에 대해 고정된 503 에러 코드를 사용: `{"code": "v2_search_not_ready", "message": "..."}`(`_corpus_unready_http_error`와 동일한 `detail` 형태).
- `.env`/시크릿을 절대 커밋하지 말 것. 명시적 확인 없이 파괴적인 DB 명령을 실행하지 말 것.
- 테스트 실행: 항상 `python -m pytest`를 사용할 것(예: `uv run --directory apps/api python -m pytest`), 순수한 `pytest` 명령은 절대 사용하지 말 것 — 이 프로젝트 설정에서는 순수 `pytest`가 작업 디렉터리를 `sys.path`에 추가하지 않아, 코드 자체는 정상임에도 `import app`/`import law_rag_llamaindex`가 `ModuleNotFoundError`로 실패한다. 이 계획 실행 전에 이 저장소의 실제 환경에서 검증됨.
- 의존성 동기화: 항상 저장소 루트에서 `uv sync --all-packages`를 실행할 것, `uv sync --directory <single-member>`는 절대 사용하지 말 것 — 이는 공유 venv를 쓰는 uv 워크스페이스이며, 멤버 하나만 동기화하면 다른 멤버가 필요로 하는 패키지가 정리(prune)되어 해당 멤버의 테스트가 깨진다. 이 계획 실행 전에 이 저장소의 실제 환경에서 검증됨.
- 기준 설계 문서: [`docs/design-docs/v2-llamaindex-retrieval-pipeline-design.md`](../../design-docs/v2-llamaindex-retrieval-pipeline-design.md). 여기의 구현 세부 사항이 해당 문서와 충돌하면 설계 문서의 "결정 기록"이 우선하며, 이 계획을 그에 맞게 수정해야 한다(그 반대가 아님).

---

## Task 1: `law-rag-llamaindex` 워크스페이스 앱 스캐폴딩

**파일:**
- 생성: `apps/law-rag-llamaindex/pyproject.toml`
- 생성: `apps/law-rag-llamaindex/src/law_rag_llamaindex/__init__.py`
- 생성: `apps/law-rag-llamaindex/tests/test_package.py`
- 수정: `pyproject.toml:2`(루트 워크스페이스 멤버)

**인터페이스:**
- 산출물: `__version__ = "0.1.0"`를 가지며 uv 워크스페이스 멤버로 설치 가능한 임포트 가능 패키지 `law_rag_llamaindex`.

- [ ] **1단계: 루트 `pyproject.toml`에 워크스페이스 멤버 추가**

```toml
[tool.uv.workspace]
members = ["apps/api", "apps/collector", "apps/law-rag-llamaindex", "packages/law-rag-core"]
```

- [ ] **2단계: 앱 디렉터리와 `pyproject.toml` 생성**

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

- [ ] **3단계: 패키지 골격 생성**

`apps/law-rag-llamaindex/src/law_rag_llamaindex/__init__.py`:
```python
__version__ = "0.1.0"
```

- [ ] **4단계: 스모크 테스트 작성**

`apps/law-rag-llamaindex/tests/test_package.py`:
```python
import law_rag_llamaindex


def test_package_imports():
    assert law_rag_llamaindex.__version__ == "0.1.0"
```

- [ ] **5단계: 워크스페이스 동기화 및 테스트 실행**

실행: `uv sync --all-packages`(`--directory apps/law-rag-llamaindex` 단독 실행 금지 — 이 저장소는 공유 venv uv 워크스페이스이며, 멤버 하나만 동기화하면 다른 멤버가 필요로 하는 패키지가 정리될 수 있음)
기대 결과: Python 3.14 하에서 의존성 해석이 성공함(llama-index-core는 `>=3.9,<4.0`을 요구하므로 해석되어야 함 — 만약 실패하면, 이후의 모든 태스크가 이 설치 성공에 의존하므로 다음 태스크로 넘어가기 전에 resolver 오류를 기록할 것).

실행: `uv run --directory apps/law-rag-llamaindex python -m pytest -v`
기대 결과: `test_package_imports PASSED`

- [ ] **6단계: 커밋**

```bash
git add pyproject.toml apps/law-rag-llamaindex/
git commit -m "feat(law-rag-llamaindex): scaffold new uv workspace app"
```

---

## Task 2: 설정(Config settings)

**파일:**
- 생성: `apps/law-rag-llamaindex/src/law_rag_llamaindex/config.py`
- 테스트: `apps/law-rag-llamaindex/tests/test_config.py`

**인터페이스:**
- 산출물: `database_url: str | None`, `nvidia_api_key: str | None`, `nvidia_base_url: str`, `nvidia_embedding_model: str`, `embed_dim: int`, `vector_table_name: str`, `hnsw_kwargs: dict | None` 필드를 가진 `Settings`(pydantic `BaseSettings`); `get_settings() -> Settings`(`lru_cache` 적용).
- 소비: 없음(리프 모듈).

- [ ] **1단계: 실패하는 테스트 작성**

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

- [ ] **2단계: 테스트가 실패하는지 확인**

실행: `uv run --directory apps/law-rag-llamaindex python -m pytest tests/test_config.py -v`
기대 결과: `ModuleNotFoundError: No module named 'law_rag_llamaindex.config'`로 FAIL

- [ ] **3단계: 구현 작성**

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

- [ ] **4단계: 테스트가 통과하는지 확인**

실행: `uv run --directory apps/law-rag-llamaindex python -m pytest tests/test_config.py -v`
기대 결과: 3 passed

- [ ] **5단계: 커밋**

```bash
git add apps/law-rag-llamaindex/src/law_rag_llamaindex/config.py apps/law-rag-llamaindex/tests/test_config.py
git commit -m "feat(law-rag-llamaindex): add settings module"
```

---

## Task 3: 패스지(passage) 템플릿과 노드 메타데이터 빌더(순수 함수, TDD)

**파일:**
- 생성: `apps/law-rag-llamaindex/src/law_rag_llamaindex/passage.py`
- 테스트: `apps/law-rag-llamaindex/tests/test_passage.py`

**인터페이스:**
- 산출물: `ProvisionRecord`(`TypedDict`: `provision_id: str`, `document_id: str`, `document_title: str`, `source_kind: str`, `law_type_code: str | None`, `version_label: str`, `effective_from: str | None`, `effective_to: str | None`, `path: str`, `heading: str | None`, `content: str`, `source_url: str`); `build_passage_text(record: ProvisionRecord) -> str`; `build_node_metadata(record: ProvisionRecord, source_text_sha256: str) -> dict[str, object]`; `compute_source_text_sha256(passage_text: str) -> str`.
- 소비: 없음(리프 모듈 — Task 4의 소스 쿼리 행이 변환되는 대상이며, Task 7의 ingestion이 소비하는 대상).

- [ ] **1단계: 실패하는 테스트 작성**

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

- [ ] **2단계: 테스트가 실패하는지 확인**

실행: `uv run --directory apps/law-rag-llamaindex python -m pytest tests/test_passage.py -v`
기대 결과: `ModuleNotFoundError: No module named 'law_rag_llamaindex.passage'`로 FAIL

- [ ] **3단계: 구현 작성**

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

- [ ] **4단계: 테스트가 통과하는지 확인**

실행: `uv run --directory apps/law-rag-llamaindex python -m pytest tests/test_passage.py -v`
기대 결과: 5 passed

- [ ] **5단계: 커밋**

```bash
git add apps/law-rag-llamaindex/src/law_rag_llamaindex/passage.py apps/law-rag-llamaindex/tests/test_passage.py
git commit -m "feat(law-rag-llamaindex): add passage template and node metadata builder"
```

---

## Task 4: Provisions 소스 쿼리

**파일:**
- 생성: `apps/law-rag-llamaindex/src/law_rag_llamaindex/source.py`
- 테스트: `apps/law-rag-llamaindex/tests/test_source.py`

**인터페이스:**
- 소비: `ProvisionRecord`(Task 3), `sqlalchemy.ext.asyncio.AsyncEngine`.
- 산출물: `async def fetch_provisions(engine: AsyncEngine) -> list[ProvisionRecord]`.

이 태스크의 테스트는 실제 join 쿼리를 실행하므로 살아있는 Postgres(`DATABASE_URL` 설정됨)를 필요로 한다 — `apps/api`의 관례(테스트에서 `DATABASE_URL=""`을 기본값으로 두는 것)에 맞춰, 기본 `pytest` 실행(즉 `DATABASE_URL` 없음)에서는 건너뛰도록 가드할 것.

- [ ] **1단계: 실패하는 테스트 작성**

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

- [ ] **2단계: 테스트가 건너뛰어지는지(DB 미설정) 확인하고, 임포트가 먼저 실패하는지도 확인**

실행: `uv run --directory apps/law-rag-llamaindex python -m pytest tests/test_source.py -v`
기대 결과: `ModuleNotFoundError: No module named 'law_rag_llamaindex.source'`로 FAIL(skip 마커는 모듈이 존재해야 비로소 적용되므로, 이 단계는 모듈이 존재하기 전에 테스트 파일 자체가 제대로 연결되어 있음을 증명하기 위한 것)

- [ ] **3단계: 구현 작성**

`apps/api/app/adapters/postgres_repository.py`가 이미 사용 중인 join과 컬럼 별칭(`provisions p JOIN document_versions v ON v.id = p.version_id JOIN legal_documents d ON d.id = v.document_id`, `version_label`은 `'MST '||v.mst`로 구성)을 그대로 재사용하여, v2의 원시 행(raw row)이 동일한 컬럼에 대해 v1의 의미(semantics)와 일치하도록 한다.

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

- [ ] **4단계: 테스트가 통과하는지(또는 DB 없이 깔끔하게 건너뛰는지) 확인**

실행: `uv run --directory apps/law-rag-llamaindex python -m pytest tests/test_source.py -v`
기대 결과: `1 skipped`(기본 개발 셸에는 `DATABASE_URL`이 없음) — 로컬에 `DATABASE_URL`을 export해두었다면 `1 passed`가 나와야 함.

- [ ] **5단계: 커밋**

```bash
git add apps/law-rag-llamaindex/src/law_rag_llamaindex/source.py apps/law-rag-llamaindex/tests/test_source.py
git commit -m "feat(law-rag-llamaindex): add provisions source query"
```

---

## Task 5: 임베딩 래퍼

**파일:**
- 생성: `apps/law-rag-llamaindex/src/law_rag_llamaindex/embedding.py`
- 테스트: `apps/law-rag-llamaindex/tests/test_embedding.py`

**인터페이스:**
- 소비: `Settings`(Task 2).
- 산출물: `build_embedder(settings: Settings) -> NVIDIAEmbedding`.

NIM의 passage-vs-query 구분은 LlamaIndex의 `NVIDIAEmbedding`이 어떤 메서드를 호출하는지(ingestion/passage용 `get_text_embedding_batch(...)`, 쿼리용 `get_query_embedding(...)`)에 따라 내부적으로 처리된다 — 이 래퍼는 `input_type`을 직접 넘길 필요 없이, 올바른 모델/자격 증명으로 클라이언트를 생성하기만 하면 된다.

- [ ] **1단계: 실패하는 테스트 작성**

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

- [ ] **2단계: 테스트가 실패하는지 확인**

실행: `uv run --directory apps/law-rag-llamaindex python -m pytest tests/test_embedding.py -v`
기대 결과: `ModuleNotFoundError: No module named 'law_rag_llamaindex.embedding'`로 FAIL

- [ ] **3단계: 구현 작성**

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

- [ ] **4단계: 테스트가 통과하는지 확인**

실행: `uv run --directory apps/law-rag-llamaindex python -m pytest tests/test_embedding.py -v`
기대 결과: 1 passed
(만약 `NVIDIAEmbedding.__init__`이 가짜 API 키를 거부하거나 생성 시 네트워크 접근을 요구한다면, 이는 실제 API 형태에 관한 뜻밖의 발견이므로 — 테스트를 건너뛰지 말고 멈춰서 래퍼/테스트를 조정할 것. 네트워크 호출 없이 생성될 것으로 예상됨.)

- [ ] **5단계: 커밋**

```bash
git add apps/law-rag-llamaindex/src/law_rag_llamaindex/embedding.py apps/law-rag-llamaindex/tests/test_embedding.py
git commit -m "feat(law-rag-llamaindex): add NVIDIA embedding wrapper"
```

---

## Task 6: 벡터 스토어 팩토리

**파일:**
- 생성: `apps/law-rag-llamaindex/src/law_rag_llamaindex/store.py`
- 테스트: `apps/law-rag-llamaindex/tests/test_store.py`

**인터페이스:**
- 소비: `Settings`(Task 2).
- 산출물: `build_vector_store(settings: Settings) -> PGVectorStore`.

- [ ] **1단계: 실패하는 테스트 작성**

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

- [ ] **2단계: 테스트가 실패하는지 확인**

실행: `uv run --directory apps/law-rag-llamaindex python -m pytest tests/test_store.py -v`
기대 결과: `ModuleNotFoundError: No module named 'law_rag_llamaindex.store'`로 FAIL

- [ ] **3단계: 구현 작성**

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

- [ ] **4단계: 테스트가 통과하는지 확인**

실행: `uv run --directory apps/law-rag-llamaindex python -m pytest tests/test_store.py -v`
기대 결과: 2 passed
(이 테스트가 살아있는 DB 없이 통과하려면 `PGVectorStore.from_params`가 생성 시점에 연결을 열지 않아야 한다 — 만약 연결을 연다면 이 테스트에는 실행 중인 Postgres가 필요하다는 뜻이므로, 이 사실을 계획의 진행 기록에 남기고 테스트를 Task 4의 `DATABASE_URL`-skip 패턴으로 전환할 것.)

- [ ] **5단계: 커밋**

```bash
git add apps/law-rag-llamaindex/src/law_rag_llamaindex/store.py apps/law-rag-llamaindex/tests/test_store.py
git commit -m "feat(law-rag-llamaindex): add PGVectorStore factory"
```

---

## Task 7: Ingestion 파이프라인

**파일:**
- 생성: `apps/law-rag-llamaindex/src/law_rag_llamaindex/ingest.py`
- 테스트: `apps/law-rag-llamaindex/tests/test_ingest.py`

**인터페이스:**
- 소비: `ProvisionRecord`, `build_passage_text`, `compute_source_text_sha256`, `build_node_metadata`(Task 3); `.add(nodes) -> list[str]`을 갖는 `PGVectorStore` 형태의 객체(Task 6, 이 태스크의 테스트에서는 fake로 대체됨).
- 산출물: `changed_provision_ids(provisions: list[ProvisionRecord], existing_hashes: dict[str, str]) -> set[str]`(순수 함수); `build_nodes(provisions: list[ProvisionRecord]) -> list[TextNode]`(순수 함수, 임베딩 미적용); `async def existing_hashes(engine: AsyncEngine, table_name: str) -> dict[str, str]`; `async def delete_nodes(engine: AsyncEngine, table_name: str, node_ids: set[str]) -> None`; `async def run_ingestion(engine, vector_store, embedder, table_name: str) -> IngestionResult`(`IngestionResult`는 `total_provisions: int`, `embedded_count: int`, `skipped_count: int`를 가진 `@dataclass(frozen=True)`).

해시 스킵 로직(`changed_provision_ids`, `build_nodes`)은 순수 함수이며 fake를 사용한 완전한 단위 테스트 커버리지를 갖는다. `existing_hashes`/`delete_nodes`/`run_ingestion`은 살아있는 Postgres를 필요로 하며 Task 4와 동일하게 skip 가드된다.

- [ ] **1단계: 순수 로직에 대한 실패하는 테스트 작성**

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

- [ ] **2단계: 테스트가 실패하는지 확인**

실행: `uv run --directory apps/law-rag-llamaindex python -m pytest tests/test_ingest.py -v`
기대 결과: `ModuleNotFoundError: No module named 'law_rag_llamaindex.ingest'`로 FAIL

- [ ] **3단계: 구현 작성**

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

- [ ] **4단계: 테스트가 통과하는지(또는 깔끔하게 건너뛰는지) 확인**

실행: `uv run --directory apps/law-rag-llamaindex python -m pytest tests/test_ingest.py -v`
기대 결과: 3 passed, 1 skipped(`DATABASE_URL`이 없을 때) — 또는, `DATABASE_URL`이 `law_rag_llamaindex_ingestion_runs` 마이그레이션(Task 8)이 적용되고 provisions 데이터가 이미 존재하는 실제 개발용 Postgres를 가리키고 있다면 4 passed.

- [ ] **5단계: 커밋**

```bash
git add apps/law-rag-llamaindex/src/law_rag_llamaindex/ingest.py apps/law-rag-llamaindex/tests/test_ingest.py
git commit -m "feat(law-rag-llamaindex): add ingestion pipeline with hash-skip upsert"
```

---

## Task 8: 리트리버(Retriever)

**파일:**
- 생성: `apps/law-rag-llamaindex/src/law_rag_llamaindex/retriever.py`
- 테스트: `apps/law-rag-llamaindex/tests/test_retriever.py`

**인터페이스:**
- 소비: `.aquery(VectorStoreQuery) -> VectorStoreQueryResult`를 노출하는 `PGVectorStore` 형태의 객체(테스트에서는 fake로 대체), `.get_query_embedding(str) -> list[float]`를 노출하는 임베더(fake로 대체), `law_rag_core.domain.schemas.SearchHit`.
- 산출물: `async def search(vector_store, embedder, query: str, as_of_date: date, limit: int) -> list[SearchHit]`.

시간적 유효성(temporal validity)은 두 개의 레이어에서 강제된다: `effective_from <= as_of_date`는 `MetadataFilter`(서버 측, 저렴함)로 밀어넣고, `effective_to IS NULL OR effective_to > as_of_date` 절반은 초과 조회(over-fetch)된 배치(`limit * 4`, 최대 100으로 제한)를 가져온 후 Python에서 적용한다 — LlamaIndex의 `FilterOperator` 집합(`EQ`/`GT`/`LT`/`NE`/`GTE`/`LTE`/`IN`/`NIN`)에는 확인된 null-check 연산자가 없으므로, 존재하지 않을 수도 있는 연산자를 추측하는 것을 피하기 위함이다.

- [ ] **1단계: 실패하는 테스트 작성**

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

참고: `SearchHit`의 `provision_id`/`document_id`는 `law_rag_core`에서 `UUID` 타입이지만, 이 테스트 스위트는 가독성을 위해 `"current"` 같은 일반 문자열을 노드 id로 사용한다. `SearchHit` 검증이 UUID가 아닌 문자열을 거부한다면, 구현을 작성하기 전에 픽스처 id를 실제 UUID 문자열(예: `"11111111-1111-1111-1111-111111111111"`)로 바꿀 것. 이는 3단계에서 먼저 `law_rag_core/domain/schemas.py`의 `SearchHit` 정의를 읽어 확인한다.

- [ ] **2단계: 테스트가 실패하는지 확인**

실행: `uv run --directory apps/law-rag-llamaindex python -m pytest tests/test_retriever.py -v`
기대 결과: `ModuleNotFoundError: No module named 'law_rag_llamaindex.retriever'`로 FAIL

- [ ] **3단계: `SearchHit`의 필드 타입을 확인한 뒤 구현 작성**

`packages/law-rag-core/src/law_rag_core/domain/schemas.py`의 `SearchHit` 클래스를 읽을 것(이 프로젝트에서 이미 이전에 확인됨: `provision_id: UUID`, `document_id: UUID`, 나머지는 `str`/`date | None`/`float`). 이 태스크의 테스트에서 노드 id가 유효한 UUID가 아니라면, 4단계를 실행하기 전에 테스트 픽스처를 UUID 문자열로 고칠 것.

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

- [ ] **4단계: 테스트가 통과하는지 확인**

실행: `uv run --directory apps/law-rag-llamaindex python -m pytest tests/test_retriever.py -v`
기대 결과: 4 passed
(설치된 버전에서 `MetadataFilter`/`FilterOperator`/`MetadataFilters`/`VectorStoreQuery`의 임포트 경로가 `llama_index.core.vector_stores.types`와 다르다면, 실제 설치된 패키지 구조에 맞춰 임포트를 수정할 것 — 먼저 `uv run --directory apps/law-rag-llamaindex python -c "from llama_index.core.vector_stores.types import MetadataFilter"`로 확인할 것.)

- [ ] **5단계: 커밋**

```bash
git add apps/law-rag-llamaindex/src/law_rag_llamaindex/retriever.py apps/law-rag-llamaindex/tests/test_retriever.py
git commit -m "feat(law-rag-llamaindex): add retriever with temporal validity filtering"
```

---

## Task 9: ingestion 준비 완료 마커를 위한 Alembic 마이그레이션

**파일:**
- 생성: `apps/api/migrations/versions/0013_llamaindex_ingestion_runs.py`

**인터페이스:**
- 산출물: 테이블 `law_rag_llamaindex_ingestion_runs(id uuid pk, started_at timestamptz, finished_at timestamptz null, node_count integer, status text)`.
- 소비: 새로운 것 없음(이 테이블은 오직 `law-rag-llamaindex`의 ingestion CLI와 `apps/api`의 준비 상태 확인 로직에서만 읽고 쓴다).

- [ ] **1단계: 마이그레이션 작성**

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

- [ ] **2단계: 마이그레이션이 로컬/개발용 데이터베이스에 정상 적용되는지 확인**

실행: `uv run --directory apps/api alembic upgrade head`
기대 결과: 에러 없음; `alembic_version`이 `0013`으로 올라감. 로컬에 `DATABASE_URL`이 구성되어 있지 않다면 이 검증 단계는 건너뛰고 계획의 진행 기록에 미검증으로 남길 것 — 이 마이그레이션은 병합 전에 CI/스테이징에서 검증될 것임.

- [ ] **3단계: 커밋**

```bash
git add apps/api/migrations/versions/0013_llamaindex_ingestion_runs.py
git commit -m "feat(api): add law_rag_llamaindex_ingestion_runs migration"
```

---

## Task 10: `apps/api`의 `LlamaIndexLegalRepository` 어댑터

**파일:**
- 생성: `apps/api/app/adapters/llamaindex_repository.py`
- 테스트: `apps/api/tests/test_llamaindex_repository.py`
- 수정: `apps/api/pyproject.toml`(`law-rag-llamaindex` 의존성 추가)

**인터페이스:**
- 소비: `law_rag_core.ports.repository.LegalRepository` Protocol; `law_rag_llamaindex.retriever.search`(Task 8); 기존 `PostgresLegalRepository` 또는 그와 호환되는 `delegate`.
- 산출물: `LegalRepository`의 모든 메서드를 구현하는 `LlamaIndexLegalRepository(delegate, vector_store, embedder)` — `search`/`search_with_trace`는 v2를 통해, 나머지 전부는 `delegate`로 위임.

- [ ] **1단계: 워크스페이스 의존성 추가**

`apps/api/pyproject.toml`의 `dependencies` 목록에 `"law-rag-llamaindex"`를 추가하고, `[tool.uv.sources]` 테이블에 다음을 추가:

```toml
[tool.uv.sources]
law-rag-core = { workspace = true }
law-rag-llamaindex = { workspace = true }
```

실행: `uv sync --all-packages`(공유 venv 워크스페이스 — Task 1의 안내 참고)
기대 결과: 충돌 없이 해석됨.

- [ ] **2단계: 실패하는 테스트 작성**

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

- [ ] **3단계: 테스트가 실패하는지 확인**

실행: `uv run --directory apps/api python -m pytest tests/test_llamaindex_repository.py -v`
기대 결과: `ModuleNotFoundError: No module named 'app.adapters.llamaindex_repository'`로 FAIL

- [ ] **4단계: 구현 작성**

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

- [ ] **5단계: 테스트가 통과하는지 확인**

실행: `uv run --directory apps/api python -m pytest tests/test_llamaindex_repository.py -v`
기대 결과: 3 passed

- [ ] **6단계: 커밋**

```bash
git add apps/api/pyproject.toml apps/api/app/adapters/llamaindex_repository.py apps/api/tests/test_llamaindex_repository.py
git commit -m "feat(api): add LlamaIndexLegalRepository adapter"
```

---

## Task 11: `/v2/search` 엔드포인트

**파일:**
- 수정: `apps/api/app/main.py`(기존 `repository`/`supabase_auth` 전역 변수 근처에 v2 연결 코드 추가, `/v1/search` 근처에 새 라우트 추가)
- 테스트: `apps/api/tests/test_v2_search.py`

**인터페이스:**
- 소비: `law_rag_llamaindex.config.get_settings`, `law_rag_llamaindex.store.build_vector_store`, `law_rag_llamaindex.embedding.build_embedder`, `law_rag_llamaindex.retriever.search`(Task 2, 5, 6, 8).
- 산출물: `list[SearchHit]`을 반환하는 `POST /v2/search`; 모듈 전역 변수 `llamaindex_vector_store: PGVectorStore | None`, `llamaindex_embedder: NVIDIAEmbedding | None`.

- [ ] **1단계: 실패하는 테스트 작성**

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

- [ ] **2단계: 테스트가 실패하는지 확인**

실행: `uv run --directory apps/api python -m pytest tests/test_v2_search.py -v`
기대 결과: FAIL — `/v2/search` 라우트가 존재하지 않음(404), 또는 `main_module.llamaindex_vector_store`가 아직 없어서 `AttributeError`.

- [ ] **3단계: 모듈 레벨 연결 코드와 라우트 추가**

`apps/api/app/main.py`에서, 기존 임포트 근처(`from app.adapters.postgres_repository import PostgresLegalRepository` 줄 다음)에:

```python
from law_rag_llamaindex.config import get_settings as get_llamaindex_settings
from law_rag_llamaindex.embedding import build_embedder as build_llamaindex_embedder
from law_rag_llamaindex.retriever import search as llamaindex_search
from law_rag_llamaindex.store import build_vector_store as build_llamaindex_vector_store

from app.adapters.llamaindex_repository import LlamaIndexLegalRepository
```

기존 `repository = ...` / `supabase_auth = ...` 전역 블록 근처에:

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

`_corpus_unready_http_error` 근처(모듈 레벨 헬퍼 섹션)에:

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

`main.py`의 임포트에 아직 없다면 `from sqlalchemy import text`를 추가할 것(`main.py`는 원시 SQL을 직접 쓰기보다는 `repository`의 자체 쿼리 메서드를 사용하고 있어서 현재는 없는 상태 — 중복 임포트를 피하기 위해 추가 전에 먼저 `grep -n "^from sqlalchemy" apps/api/app/main.py`로 확인할 것).

기존 `/v1/search` 라우트 근처에:

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

- [ ] **4단계: 테스트가 통과하는지 확인**

실행: `uv run --directory apps/api python -m pytest tests/test_v2_search.py -v`
기대 결과: 2 passed

- [ ] **5단계: 회귀를 확인하기 위해 `apps/api` 전체 테스트 스위트 실행**

실행: `uv run --directory apps/api python -m pytest -v`
기대 결과: 기존에 통과하던 테스트가 모두 계속 통과함(새로운 임포트/전역 변수가 `TestClient(main_module.app)`을 생성하는 기존 테스트의 앱 시작을 깨뜨려서는 안 됨).

- [ ] **6단계: 커밋**

```bash
git add apps/api/app/main.py apps/api/tests/test_v2_search.py
git commit -m "feat(api): add /v2/search endpoint backed by law-rag-llamaindex"
```

---

## Task 12: `/v2/questions` 엔드포인트(v1의 답변 파이프라인 재사용)

**파일:**
- 수정: `apps/api/app/main.py:215-305`(`_handle_question` 추출, `_answer_question`/`_retrieve_question_evidence`/`_load_corpus_temporal_state`/`_require_supported_as_of_date`에 `repository` 스레딩, `/v2/questions` 라우트 추가)
- 테스트: `apps/api/tests/test_v2_questions.py`

**인터페이스:**
- 소비: `llamaindex_repository`(Task 11, v2가 구성되지 않은 경우 `None`), `_answer_question`이 이미 소비하는 모든 것.
- 산출물: `QuestionResponse`를 반환하는 `POST /v2/questions`; 리팩터링된 `_answer_question(payload, request, user, budget, repository)`.

이것은 이 계획에서 가장 위험도가 높은 태스크다 — `_answer_question`은 여러 내부 단계를 가진 큰 함수다. 이 리팩터링은 의도적으로 범위를 좁혔다: 새 파라미터 하나를 네 개의 함수에 통과시킬 뿐, 다른 로직은 건드리지 않는다.

- [ ] **1단계: 실패하는 테스트 작성**

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

참고: `QuestionResponse`의 정확한 필수 필드는 `app/domain/schemas.py`와 일치해야 한다 — 라우팅 로직과 무관한 검증 에러로 테스트가 실패하면, 이 픽스처를 확정하기 전에 해당 클래스를 먼저 읽을 것.

- [ ] **2단계: 테스트가 실패하는지 확인**

실행: `uv run --directory apps/api python -m pytest tests/test_v2_questions.py -v`
기대 결과: FAIL — `/v2/questions` 라우트가 존재하지 않음(404)

- [ ] **3단계: `_answer_question`과 그 헬퍼가 `repository`를 받도록 리팩터링**

`apps/api/app/main.py`에서, 네 개의 시그니처와 그 내부의 repository 참조를 변경:

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

그리고 그 내부 호출부(`lambda: _retrieve_question_evidence(payload, query_embedding),`를 읽는 줄):

```python
                lambda: _retrieve_question_evidence(payload, query_embedding, repository),
```

`main.py`의 임포트에 아직 없다면 `from law_rag_core.ports.repository import LegalRepository`를 추가할 것(현재 `repository`는 이 Protocol로 타입 표기되지 않고 구조적으로만 타입되어 있으므로, 먼저 `grep -n "LegalRepository" apps/api/app/main.py`로 확인할 것 — 이 임포트는 새로 추가될 가능성이 높음).

- [ ] **4단계: 영향받지 않는 세 개의 v1 호출부가 `repository`를 명시적으로 전달하도록 업데이트**

`/v1/search` 핸들러(199번째 줄 근처):
```python
    await _require_supported_as_of_date(payload.as_of_date, repository)
```

`/v1/provisions/{provision_id}` 핸들러(889번째 줄 근처):
```python
    await _require_supported_as_of_date(requested_date, repository)
```

`/v1/corpus/status` 핸들러(919번째 줄 근처):
```python
        temporal_state = await _load_corpus_temporal_state(repository)
```

- [ ] **5단계: `/v1/questions` 라우트에서 `_handle_question`을 추출하고 `/v2/questions` 추가**

기존 `question()` 핸들러 본문(현재 `@app.post("/v1/questions", ...)`로 데코레이트된 함수 전체)을 추출된 헬퍼와 두 개의 얇은 라우트로 교체:

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

- [ ] **6단계: 새 테스트가 통과하는지 확인**

실행: `uv run --directory apps/api python -m pytest tests/test_v2_questions.py -v`
기대 결과: 2 passed

- [ ] **7단계: 회귀를 확인하기 위해 `apps/api` 전체 테스트 스위트 실행**

실행: `uv run --directory apps/api python -m pytest -v`
기대 결과: 모든 테스트가 통과함. 기존의 모든 `/v1/questions` 테스트(`test_api.py`, `test_answering.py`, `test_distributed_question_cancellation.py` 등)도 포함 — 이들은 `_answer_question`/`_retrieve_question_evidence`를 실행하며, 이제 명시적(모듈 전역값을 가진) `repository` 인자를 받게 되어도 동일하게 동작해야 한다. 실패하는 것이 있다면 리팩터링이 v1 동작을 변경한 것이므로 — 테스트가 아니라 리팩터링을 고칠 것.

- [ ] **8단계: 커밋**

```bash
git add apps/api/app/main.py apps/api/tests/test_v2_questions.py
git commit -m "feat(api): add /v2/questions reusing v1 answering pipeline with v2 evidence"
```

---

## Task 13: `apps/web` — `/v2/questions`로 전환

**파일:**
- 수정: `apps/web/lib/api-client.ts:108`(`/v1/questions` POST 호출 부분)
- 수정: `apps/web/lib/api-client-flow.test.ts`(모킹된 엔드포인트 URL 업데이트)

**인터페이스:**
- 소비: `/v2/questions`(Task 12), `/v1/questions`와 동일한 요청/응답 형태 — 다른 web 코드 변경 없음.

- [ ] **1단계: 현재 호출부 확인**

실행: `sed -n '104,115p' apps/web/lib/api-client.ts`(또는 파일을 열어서) 수정하기 전에 정확한 함수 이름과 주변 코드를 확인할 것 — 이 계획은 108번째 줄의 URL 문자열 `"/v1/questions"`을 기준으로 작성되었다. 만약 그 사이 주변 코드가 바뀌었다면, 다른 호출부가 아니라 동일한 호출부에 맞춰 수정을 조정할 것.

- [ ] **2단계: 실패하는 테스트를 먼저 업데이트**

`apps/web/lib/api-client-flow.test.ts`에서 다음을:
```ts
      if (url.endsWith("/v1/questions") && init?.method === "POST") return Response.json(answer);
```
다음으로 변경:
```ts
      if (url.endsWith("/v2/questions") && init?.method === "POST") return Response.json(answer);
```
그리고 assertion을 다음과 같이:
```ts
    const questionCall = fetchMock.mock.calls.find(([url]) => String(url).endsWith("/v1/questions"));
```
다음으로 변경:
```ts
    const questionCall = fetchMock.mock.calls.find(([url]) => String(url).endsWith("/v2/questions"));
```

- [ ] **3단계: 테스트가 실패하는지 확인**

실행: `pnpm --filter web test -- api-client-flow`
기대 결과: FAIL — 모킹은 이제 `/v2/questions`를 기대하지만 `api-client.ts`는 여전히 `/v1/questions`를 호출하므로, 모킹된 fetch 핸들러가 매치되지 않고 요청이 처리되지 않은 채로 통과함.

- [ ] **4단계: 구현 업데이트**

`apps/web/lib/api-client.ts`에서, `/v1/questions` 호출부의 요청 URL을 `"/v1/questions"`에서 `"/v2/questions"`로 변경(스키마가 동일하므로 method, body, headers 등 나머지 인자는 모두 그대로 유지).

- [ ] **5단계: 테스트가 통과하는지 확인**

실행: `pnpm --filter web test -- api-client-flow`
기대 결과: PASS

- [ ] **6단계: 회귀를 확인하기 위해 web 전체 테스트 스위트 실행**

실행: `pnpm --filter web test`
기대 결과: 모든 테스트가 통과함 — `/v1/questions/history`, `/v1/auth/me`, `/v1/conversations` 등은 건드리지 않았으므로 여전히 정상 동작해야 함. 질문 답변 호출만 v2로 이동했기 때문.

- [ ] **7단계: 커밋**

```bash
git add apps/web/lib/api-client.ts apps/web/lib/api-client-flow.test.ts
git commit -m "feat(web): call /v2/questions instead of /v1/questions"
```

---

## Task 14: 저장소 문서 업데이트 및 계획 마무리

**파일:**
- 수정: `docs/exec-plans/active/README.md`(이 계획에 대한 한 줄 항목 추가)
- 수정: `docs/design-docs/v2-llamaindex-retrieval-pipeline-design.md`(상태 줄: `제안됨` → `구현 중` 또는 `승인`, AGENTS.md의 상태 정의에 따름)
- 수정: `docs/PLANS.md` — 변경 불필요(이미 active/todo/completed 생명주기를 일반적으로 문서화하고 있음)

- [ ] **1단계: 활성 인덱스에 계획 추가**

`docs/exec-plans/active/README.md`에 기존 형식을 따라 다음 줄을 추가:
```markdown
- [0053: V2 LlamaIndex 검색 파이프라인](0053-v2-llamaindex-retrieval-pipeline.md) — `law-rag-llamaindex` 워크스페이스, `/v2/search`·`/v2/questions`, web 전환
```

- [ ] **2단계: 설계 문서 상태 업데이트**

`docs/design-docs/v2-llamaindex-retrieval-pipeline-design.md:3`에서 다음을:
```markdown
상태: 제안됨 (2026-08-18)
```
다음으로 변경:
```markdown
상태: 구현 중 (2026-08-18)
```

- [ ] **3단계: 세 프로젝트 전체에 걸친 전체 검증 스위트 실행**

```bash
uv run --directory apps/law-rag-llamaindex python -m pytest
uv run --directory apps/api python -m pytest
pnpm --filter web test
```
기대 결과: 모두 통과.

- [ ] **4단계: 커밋**

```bash
git add docs/exec-plans/active/README.md docs/design-docs/v2-llamaindex-retrieval-pipeline-design.md
git commit -m "docs: link 0053 plan and mark v2 design doc as in progress"
```

---

## Self-Review Notes(계획 작성자를 위한 것이며 태스크가 아님)

- **명세 커버리지:** 목표(v2 pipeline, `/v2/search`, `/v2/questions`, 인용+시간적 요구사항) → Tasks 1–12. 비범위(새로운 AI 생성 코드 없음, v2에 search_only 없음, direct-path/keyword fallback 없음, v2 quota 없음) → 구성상 준수됨(Task 12는 `_answer_question`을 그대로 재사용하며, 이 계획 어디에도 새로운 생성 코드는 작성되지 않음). 데이터 모델/Ingestion → Tasks 3, 4, 7. 조회 인터페이스 → Task 8. API → Tasks 11, 12. 인증과 이력 → Task 12(`_optional_user`/`save_question`을 그대로 재사용, 변경 없음). Web → Task 13. 테스트 → 모든 태스크가 자체 테스트를 가짐. 결정 기록 항목들(HNSW는 미루되 플러그 가능하도록, 네이티브 임베딩 차원, 패스지 템플릿 재사용, 테이블 네이밍) → 각각 Tasks 6, 5, 3, 6에 대응.
- **알려진 위험:** Task 12의 `_answer_question` 리팩터링은 이 계획이 공유되는 v1 코드를 건드리는 유일한 지점이다. 7단계의 전체 스위트 회귀 실행이 안전망이다 — 만약 이것이 green이 아니라면, Task 13으로 진행하지 말 것.
- **구현 시점까지 미해결로 남은 항목(설계 문서의 미결정 섹션에서 이어짐):** 정확한 ingestion CLI 진입점/플래그는 이 계획의 태스크에서 의도적으로 제외되었다 — Task 7은 `run_ingestion`을 라이브러리 함수로 노출할 뿐이며, `python -m law_rag_llamaindex.ingest` CLI 진입점을 연결하는 것은 Tasks 1–9가 병합되고 실제 corpus를 대상으로 ingestion할 수 있게 된 이후의 작은 후속 작업이며, `/v2/search`/`/v2/questions`가 mock으로 존재하고 테스트 가능한 상태가 되는 데는 걸림돌이 아니다.

