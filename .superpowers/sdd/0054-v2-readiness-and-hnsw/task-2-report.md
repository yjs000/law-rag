# Task 2 실행 보고서: 관리형 v2 HNSW 인덱스

## 작업 범위

- `apps/law-rag-llamaindex/src/law_rag_llamaindex/hnsw.py`
- `apps/law-rag-llamaindex/tests/test_hnsw.py`
- 기존 ingestion, API, store factory는 수정하지 않았다.
- 실제 PostgreSQL 접속이나 인덱스 생성·삭제 DDL은 실행하지 않았다.

## TDD 진행

1. fake async engine/connection을 사용하는 테스트를 먼저 작성했다. 테스트는 enable/disable의 AUTOCOMMIT 설정과 SQL, catalog status 결과, ensure의 존재·부재 분기, 잘못된 식별자 거부를 검증한다.
2. 구현 전 focused 테스트를 실행해 `law_rag_llamaindex.hnsw` 모듈이 없어지는 RED를 확인했다.
   - 명령: `python -m pytest apps/law-rag-llamaindex/tests/test_hnsw.py -q`
   - RED 원인: `ModuleNotFoundError: No module named 'law_rag_llamaindex.hnsw'`
3. 최소 구현 후 같은 focused 테스트의 GREEN을 확인했다.
   - 결과: `14 passed`

## 구현 내용

- `HnswIndexManager(engine, table_name)`이 `data_{table_name}` 물리 테이블과 `data_{table_name}_embedding_hnsw_idx` 인덱스 식별자를 구성한다.
- `table_name`은 `[a-z0-9_]+` 정규식으로 경계에서 검증하며, 대문자·공백·구분자·SQL 조각 및 비문자열 입력은 `ValueError`로 거부한다.
- `status()`는 `pg_class`와 `pg_namespace`를 조회하고 `public` 스키마의 정확한 인덱스 이름을 SQL 파라미터로 검사한다.
- `ensure()`는 status가 `True`이면 `False`를 반환하고, 없을 때만 `enable()`을 호출한 뒤 `True`를 반환한다.
- `enable()`은 `isolation_level="AUTOCOMMIT"` 연결에서 다음 계약의 DDL을 실행한다.
  - `CREATE INDEX CONCURRENTLY IF NOT EXISTS`
  - `USING hnsw (embedding vector_cosine_ops)`
  - `WITH (m = 16, ef_construction = 128)`
- `disable()`은 같은 AUTOCOMMIT 연결에서 `DROP INDEX CONCURRENTLY IF EXISTS`를 실행한다.
- CLI는 `python -m law_rag_llamaindex.hnsw enable|disable|status|ensure`를 제공한다. `Settings`의 `DATABASE_URL`이 없으면 `SystemExit`로 실패하며, 인덱스 상태 변경은 이 수동 CLI 경로에서만 수행된다. 실행 후에는 async engine을 dispose한다.
- SQL 값은 파라미터로 전달하고, 동적 식별자는 허용 목록 검증 이후에만 구성했다.

## 검증

- `python -m pytest tests/test_hnsw.py -q`
  - `14 passed`
- `python -m pytest -q`
  - `38 passed, 2 skipped`
- `ruff check apps/law-rag-llamaindex/src/law_rag_llamaindex/hnsw.py apps/law-rag-llamaindex/tests/test_hnsw.py`
  - `All checks passed!`
- `git diff --check`는 커밋 직전에 대상 파일 기준으로 재실행한다.

pytest 실행 중 기존 환경의 `.pytest_cache` 쓰기 권한 경고와 NVIDIA 임베딩 모델 유효성 경고가 출력되었으나, 테스트 결과에는 영향을 주지 않았다. 실제 DB·DDL 검증은 요청 범위에 따라 수행하지 않았다.

## Fix round 1: P1 v2 테이블 경계 및 import 안전성

- 검토에서 지적된 v2 전용 경계를 반영해 `table_name`이 정확히 `law_rag_llamaindex`일 때만 생성자를 통과하도록 강화했다. 기존 `[a-z0-9_]+` 검증은 유지하되, `other_table`처럼 문법상 안전한 다른 테이블명도 `ValueError`로 거부한다.
- `sqlalchemy.ext.asyncio.create_async_engine`를 감시한 뒤 모듈을 reload하는 회귀 테스트를 추가했다. import 시 engine 생성, DB 연결, DDL 실행 또는 CLI 진입이 발생하면 테스트가 실패한다.
- RED: `other_table` 케이스에서 `1 failed, 15 passed`를 확인했다.
- GREEN focused: `16 passed`
- GREEN full v2: `40 passed, 2 skipped`
- Ruff: 수정 대상 파일 `All checks passed!`
- `git diff --check`: 통과(줄바꿈 형식 경고만 출력)
