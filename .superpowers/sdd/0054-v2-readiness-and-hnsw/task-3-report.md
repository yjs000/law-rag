# Task 3 실행 보고서: v2 API 리소스 지연 초기화

## 작업 범위

- `apps/api/app/main.py`
- `apps/api/tests/test_v2_search.py`
- `apps/api/tests/test_v2_questions.py`
- 실제 PostgreSQL 연결·DDL·ingestion·HNSW query tuning은 수행하지 않았다.

## TDD 진행

1. DB URL만 설정된 격리 프로세스의 `app.main` import가 vector-store builder를 호출하지 않는 테스트와, v2 리소스 factory가 각 리소스를 한 번만 생성하는 테스트를 먼저 추가했다.
2. 구현 전 focused 테스트에서 `_build_llamaindex_resources`가 없어 RED를 확인했다.
3. 최소 구현 후 focused 테스트 GREEN을 확인했다.
   - 결과: `7 passed`

## 구현 내용

- module-level `llamaindex_vector_store`, `llamaindex_embedder`, `llamaindex_repository`를 모두 `None`으로 시작하도록 변경했다.
- `DATABASE_URL`과 `NVIDIA_API_KEY`가 모두 있을 때만 private `lru_cache` factory가 vector store, embedder, `LlamaIndexLegalRepository`를 생성한다.
- v2 resolver는 module global에 주입된 test double이 하나라도 있으면 이를 우선 반환해 기존 monkeypatch 계약을 보존한다.
- `/v2/search`와 `/v2/questions`는 resolver 결과 또는 필요한 리소스가 없을 때 기존 `v2_search_not_ready` 503을 반환한다.
- v1 repository/auth 초기화 및 `/v1/*` 경로는 변경하지 않았다.

## 검증

- `uv run python -m pytest tests/test_v2_search.py tests/test_v2_questions.py`
  - `7 passed`
- `uv run ruff check app/main.py tests/test_v2_search.py tests/test_v2_questions.py`
  - `All checks passed!`
- `uv run python -m pytest --basetemp C:\\development\\git\\law-rag\\.pytest-temp-task3 -q`
  - `648 passed, 3 skipped, 2 warnings`
- `git diff --check -- apps/api/app/main.py apps/api/tests/test_v2_search.py apps/api/tests/test_v2_questions.py`
  - 통과했다. 줄바꿈 형식 경고만 출력되었다.

기본 pytest 임시 디렉터리로 전체 suite를 실행했을 때는 Windows 임시 경로 쓰기 권한으로 77개 setup 오류가 발생했지만, workspace 전용 `--basetemp` 재실행에서는 코드 오류 없이 전체 suite가 통과했다. 테스트 중 실제 DB, DDL, 외부 ingestion은 실행하지 않았다.
