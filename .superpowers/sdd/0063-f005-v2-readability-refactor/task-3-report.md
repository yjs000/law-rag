# Task 3 실행 보고서: v1/v2 HTTP router 분리

## 범위

- `app.main`을 FastAPI app factory와 production composition entry point로 축소했다.
- v1 transport는 질문·취소, account/history, corpus로 분리했다.
- v2 transport는 search, execution prepare/cancel, SSE presenter/core/finalize로 분리했다.
- 기존 `app.main` monkeypatch seam은 production getter와 re-exported helper를 유지하고, 새 router/application code는 요청 시 그 module 상태를 읽는다.
- LlamaIndex 패키지와 제품·설계 문서는 변경하지 않았다.

## 경계 결정

- 최초 추출 과정에서 1,643줄 compatibility module을 만들었으나, Task 3의 500줄 모듈 경계에 맞지 않아 즉시 삭제했다.
- 대신 v1 answer 흐름을 `application/v1/{retrieval,answering,guidance}.py`로 쪼개고, 각 HTTP 책임은 `api/v1/*`와 `api/v2/*`에만 등록했다.
- 모든 새/refactored F005 module과 `main.py`는 500줄 미만이다. `main.py`는 369줄이다. 기존 500줄 초과 adapter는 변경하지 않았다.

## TDD 및 회귀

1. `test_api_route_registration.py`를 먼저 추가했다. `app.api` package가 없어 collection이 실패하는 RED를 확인했다.
2. versioned router와 `create_app()` composition을 구현한 뒤 같은 test가 GREEN(1 passed)임을 확인했다.
3. supplemental account-history test에서 mock login route가 404인 것을 발견했다. 추출 시 첫 decorator가 함께 이동하지 않은 것이 원인이었고, decorator 하나를 복원한 뒤 관련 75 tests가 모두 통과했다.

## 검증

- `uv run --directory apps/api ruff check app tests` → `All checks passed!`
- `uv run --directory apps/api python -m pytest tests/test_api_route_registration.py tests/test_api.py tests/test_v2_search.py tests/test_v2_question_executions.py -v -p no:cacheprovider` → `29 passed` (TestClient deprecation warning 1건)
- `uv run --directory apps/api python -m pytest tests/test_mock_auth_history.py tests/test_corpus_temporal_contract.py tests/test_question_cancellation.py tests/test_routing_pipeline.py tests/test_ai_fallback.py tests/test_grounding_gate.py -q -p no:cacheprovider` → `75 passed` (같은 deprecation warning 1건)
- file-size check: `main.py` 및 새/refactored F005 modules 모두 500줄 미만. 기존 adapter 4개만 500줄 초과이며 범위 밖으로 변경하지 않았다.
- `git diff --check` 통과. Windows CRLF 변환 경고만 출력됐다.

## Graphify

- `graphify update .`를 실행했으나 기존 worktree의 권한 거부 test-cache directories를 스캔하지 못해 rebuild가 실패했다. 코드·테스트 검증에는 영향이 없었고 해당 cache directories를 변경하거나 삭제하지 않았다.

## Fix round 1 (review 반영)

- `create_app(app_dependencies)`가 `lifespan`만 사용하고 route handler는 전역 `app.main` resource를 읽던 결함을 수정했다. custom factory 요청은 `ContextVar` 기반 request facade를 통해 해당 factory의 repository, v2 service, phase limiter, auth/identity, LlamaIndex resources를 사용한다. production `app`은 전역 module lookup을 유지하므로 기존 `app.main` monkeypatch seam을 보존한다.
- 새 request-level regression은 distinct factory repository가 `/v1/search` 응답을 만들고, distinct v2 resource 및 readiness repository가 `/v2/search`를 처리함을 확인한다.
- v1 question transport가 로컬 import한 `_answer_question`을 직접 호출하던 결함을 수정하고 request-time `main._answer_question` lookup으로 복구했다. 이에 대한 monkeypatch regression을 추가했다.
- route registration test는 v1/v2의 전체 public method/path set과 module owner를 검증하도록 확대했다.
- RED: custom factory v1 search는 전역 빈 결과를 반환했고, v1 answer seam patch는 503을 반환했다. custom v2 search도 전역 readiness repository 때문에 503을 반환했다.
- GREEN/verification: `uv run --directory apps/api ruff check app tests` → `All checks passed!`; focused route/API regressions → `107 passed` (기존 TestClient deprecation warning 1건).
