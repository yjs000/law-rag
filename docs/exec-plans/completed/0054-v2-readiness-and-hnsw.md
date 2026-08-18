# V2 준비 상태와 HNSW 구현 계획

> **에이전트 작업자 안내:** `superpowers:subagent-driven-development` 또는 `superpowers:executing-plans`를 태스크 단위로 사용한다.

**목표:** 성공한 v2 ingestion이 API를 열도록 만들고, v2 벡터 테이블 전용 HNSW cosine 인덱스를 운영자 통제로 도입한다.

**아키텍처:** `run_ingestion`은 벡터 저장 전 `running`, 저장·완료 마커 갱신 후 `completed`, 예외 발생 시 `failed`를 영속화한다. API는 **가장 최근 ingestion run이 `completed`일 때만** v2 리소스를 사용할 수 있으며, `running`·`failed`·실행 없음이면 부분 데이터를 노출하지 않고 503으로 닫는다. HNSW 인덱스 유무는 별도의 운영 상태다. HNSW가 없을 때는 exact cosine 검색으로 동작한다. API는 v2 리소스를 지연 생성해 v1 시작 경로를 분리한다.

## 전역 제약

- 출처·인용 위치 메타데이터와 시간 유효성 필터를 보존한다.
- v1 시작은 v2 인프라를 생성·설정하지 않는다.
- HNSW는 v2 물리 테이블 `data_law_rag_llamaindex`에만 적용한다.
- HNSW 설정은 cosine(`vector_cosine_ops`), `m=16`, `ef_construction=128`, 임베딩 차원 2,048이다.
- `ef_search=80`은 아직 구현하지 않았으며 미결정으로 둔다.
- HNSW 상태는 운영자 CLI의 `enable`, `disable`, `status`, `ensure`로만 변경한다. ingestion과 API 요청은 인덱스를 자동 생성·삭제하거나 모드를 바꾸지 않는다.
- 명시적 승인 없이 DB migration, ingestion, 인덱스 DDL을 실행하지 않는다.
- 테스트는 `python -m pytest`로 실행한다.

## Task 1: ingestion 실행 lifecycle

- [x] fake async engine으로 `running → completed`와 `running → failed` 전이 테스트를 먼저 작성한다.
- [x] `RETURNING id`와 파라미터화 SQL helper로 상태 전이를 구현한다.
- [x] v2 테스트·Ruff·diff 검증 후 `fix(law-rag-llamaindex): record ingestion readiness transitions`로 커밋한다.

### 결과 및 커밋

- `9a87eff fix(law-rag-llamaindex): record ingestion readiness transitions`: ingestion 시작·성공·실패 lifecycle을 기록하고 완료 전이의 원자적 파라미터를 추가했다.
- `e233e29 fix(law-rag-llamaindex): preserve original ingestion error`: 실패 마커 갱신 자체가 실패해도 최초 ingestion 예외를 보존하도록 보강했다.
- `run_ingestion`은 벡터 저장과 완료 마커 갱신이 모두 끝난 뒤에만 `completed`를 기록하고, 실패 시 `failed`를 기록한다.

## Task 2: v2 HNSW 인덱스 운영 모듈

**계약:** `HnswIndexManager`는 v2 벡터 테이블에 대해서만 `enable`, `disable`, `status`, `ensure`를 제공한다. `enable`은 `CREATE INDEX CONCURRENTLY`, `disable`은 `DROP INDEX CONCURRENTLY`를 사용한다. ingestion은 HNSW를 자동 생성·삭제하지 않고 현재 모드를 바꾸지 않는다.

- [x] enable·disable·status·ensure의 DDL, 옵션, autocommit, 안전한 table-name 검증 테스트를 먼저 작성한다.
- [x] `HnswIndexManager`와 운영자 전용 CLI 진입점을 구현한다. API 요청과 ingestion 함수는 이 상태를 바꾸지 않는다.
- [x] v2 테스트·Ruff 검증 후 `feat(law-rag-llamaindex): add managed v2 HNSW index`로 커밋한다.

### 결과 및 커밋

- `9b08739 feat(law-rag-llamaindex): add managed v2 HNSW index`: `enable`·`disable`·`status`·`ensure`와 운영자 CLI를 추가했다. `AUTOCOMMIT`, concurrent DDL, cosine 연산, `m=16`, `ef_construction=128`을 검증했다.
- `36fd334 fix(law-rag-llamaindex): restrict managed HNSW to v2 table`: `law_rag_llamaindex`만 허용하는 경계 검증과 import 시 DB 작업이 발생하지 않는 회귀 테스트를 추가했다.
- CLI 진입점은 `python -m law_rag_llamaindex.hnsw enable|disable|status|ensure`이며, 물리 인덱스는 `data_law_rag_llamaindex_embedding_hnsw_idx`다. HNSW가 없을 때 ingestion/API는 exact cosine 경로를 사용한다.

## Task 3: API 지연 초기화

- [x] DB만 있고 NVIDIA 키가 없는 v1 시작 경로와 v2 지연 초기화 테스트를 먼저 작성한다.
- [x] v2 store/embedder/repository를 private cached factory에서만 생성한다.
- [x] API 전체 검증 후 `fix(api): lazily initialize v2 retrieval resources`로 커밋한다.

### 결과 및 커밋

- `3efa94f fix(api): lazily initialize v2 retrieval resources`: `DATABASE_URL`과 `NVIDIA_API_KEY`가 모두 준비된 경우에만 v2 리소스를 private cached factory에서 생성하고, v1 시작 경로를 건드리지 않도록 했다.
- `347587c fix(api): guard v2 resource factory failures`: v2 리소스 factory 실패를 stable `v2_search_not_ready` 503으로 변환하고 민감한 예외 메시지를 응답에 노출하지 않도록 보강했다.
- `/v2/search`와 `/v2/questions`는 준비되지 않은 경우 503을 반환하며, v1 repository/auth 초기화와 `/v1/*` 경로는 변경하지 않았다.

## Task 4: 정책·설계·전체 검증

- [x] `AGENTS.md`의 전역 HNSW 금지 규칙을 제거하고 v2 전용 운영 범위로 좁힌다.
- [x] v2 HNSW 결정, ingestion lifecycle 순서, 운영자 CLI 통제, recall·p95 latency·index size·ingestion duration 평가 기준을 문서화한다.
- [x] `docs/design-docs/index.md`의 상태는 `구현 중`으로 유지한다.
- [x] v2·API·web 전체 검증과 변경 Python Ruff, `git diff --check`를 실행한다.
- [x] `docs: record v2 HNSW and readiness operations`으로 문서·계획·AGENTS 변경만 커밋한다.

### 운영 결정

- HNSW는 `data_law_rag_llamaindex`에만 적용하며, vector store 생성·ingestion·API 요청이 자동으로 상태를 변경하지 않는다.
- 운영자는 `enable`·`disable`·`status`·`ensure` CLI로만 인덱스 상태를 바꾼다. `enable`/`disable`은 concurrent DDL과 autocommit 연결을 사용한다.
- 설정은 cosine(`vector_cosine_ops`), `m=16`, `ef_construction=128`이다. `ef_search=80`은 아직 구현하지 않았고 미결정이다.
- HNSW 평가는 recall, p95 latency, index size, ingestion duration을 기준으로 한다. 실제 측정값은 아직 없으며 미결정이다.

### 전체 검증 보고서

검증은 2026-08-18에 실행했으며, 실제 DB 접속·migration·ingestion·HNSW DDL은 실행하지 않았다.

- `uv run --directory apps/law-rag-llamaindex python -m pytest`: `40 passed, 2 skipped, 2 warnings in 3.57s`로 성공했다. warning은 NVIDIA embedding 모델 유효성 확인 불가(`UserWarning`)와 workspace `.pytest_cache` 생성 권한 경고(`PytestCacheWarning`)였다.
- `uv run --directory apps/api python -m pytest`: 기본 Windows 임시 경로 권한 문제로 `573 passed, 3 skipped, 77 errors`가 발생했다. 오류는 모두 `C:\Users\Family\AppData\Local\Temp\pytest-of-Family`의 `PermissionError`이며 코드 assertion 실패가 아니었다.
- API 전체 suite를 쓰기 가능한 격리 경로로 재실행했다: `uv run --directory apps/api python -m pytest --basetemp C:\Users\Family\.codex\visualizations\2026\08\18\01a01389-993d-7662-815d-880eb429c274\pytest-task4-api` → `650 passed, 3 skipped, 2 warnings in 54.63s`. warning은 `httpx2` 설치를 권고하는 Starlette deprecation과 workspace `.pytest_cache` 생성 권한 경고였다.
- `pnpm --filter web test`: Vitest `16 test files passed`, `88 tests passed`로 성공했다. 별도 skip/warning은 없었다.
- 변경 Python Ruff:
  - `uv run --directory apps/law-rag-llamaindex ruff check src/law_rag_llamaindex/ingest.py src/law_rag_llamaindex/hnsw.py tests/test_ingest.py tests/test_hnsw.py` → `All checks passed!`
  - `uv run --directory apps/api ruff check app/main.py tests/test_v2_search.py tests/test_v2_questions.py` → `All checks passed!`
- `git diff --check`: staged 문서·AGENTS·계획 전체에 대해 통과했다.

### 완료 결과와 잔여 작업

- 2026-08-18 최종 보정 `5d11407`으로 최신 ingestion run이 `completed`인 경우에만 v2를 열고, run 상태·마커 조회·리소스 초기화 실패는 민감한 예외를 노출하지 않는 `v2_search_not_ready` 503으로 닫았다. 일시적인 리소스 초기화 실패는 성공한 결과만 캐시하는 방식으로 다음 요청에서 재시도한다.
- 최종 API 전체 재검증은 쓰기 가능한 임시 경로에서 `657 passed, 3 skipped, 2 warnings in 115.14s`로 통과했다. warning은 Starlette의 `httpx` 사용 중단 예정과 workspace pytest cache 권한이다.
- 최종 전체 재검토에서 P0/P1/P2가 없음을 확인했다. 최신 run 준비 상태 계약과 v1·실험 D HNSW 금지/v2 전용 예외의 문서 불일치도 `a7d9d84`로 정정했다.
- 실제 PostgreSQL migration·ingestion·HNSW DDL과 HNSW 성능 측정(recall, p95 latency, index size, ingestion duration)은 사용자 승인 전 실행하지 않았다. `ef_search=80`은 미구현·미결정이다.
