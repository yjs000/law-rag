> 작업 ID: `TD-001`
> 상태: `Done`
> 유형: `Tech Debt`
> 보조 라벨: 없음
> 선행 조건: 없음
> 참고 범위:
> - `apps/api/app/main.py` L1-L2040 — API 조립, HTTP endpoint, 업무 함수가 한 모듈에 혼재
> - `apps/api/tests/conftest.py` L20-L67 — `app.main` patch 호환성

# API main 모듈화 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `app.main:app`와 HTTP contract를 지키며 FastAPI URL 등록을 책임별로 분리한다.

**Architecture:** `main.py`는 composition과 기존 handler를 유지한다. `app/api/`는 router 등록만 맡고, handler는 explicit endpoint registry로 받는다.

**Tech Stack:** Python 3.14, FastAPI, pytest, Ruff, uv.

**Spec:** 승인된 대화 설계 (2026-08-28) — 최소 수정, 가독성, API 계약 보존.

## Global Constraints

- `app.main:app`, URL, status code, response model, CORS를 변경하지 않는다.
- 법률 근거·인용, 개인정보, 인증 불변조건을 보존한다.
- `app.main`의 monkeypatch names를 유지한다.
- Fast mode: red-first TDD 대신 회귀 test와 전체 검증을 실행한다.

### Task 1: API registration boundary

**Files:** create `apps/api/app/api/routes.py`; modify `apps/api/app/main.py`; test `apps/api/tests/test_api_route_registration.py`.

- [x] 기존 endpoint callable을 `ApiEndpoints` dataclass로 선언한다.
- [x] catalog, questions, auth/history `APIRouter`를 URL·HTTP method·response model과 함께 등록한다.
- [x] `main.py`에서 모든 handler를 등록하고 decorator를 제거한다.
- [x] OpenAPI path와 operation ID 회귀 test를 작성한다.
- [x] Focused test: `uv run --directory apps/api python -m pytest tests/test_api.py tests/test_v2_search.py tests/test_v2_question_executions.py tests/test_api_route_registration.py -v`.

### Task 2: API quality verification

**Files:** modify `apps/api/app/api/routes.py`, `apps/api/app/main.py`, `apps/api/tests/test_api_route_registration.py`.

- [x] Public URL, method, response model, operation ID를 기존 contract와 대조한다.
- [x] `uv run --directory apps/api ruff check app tests` 및 `uv run --directory apps/api python -m pytest -v`를 실행한다.
- [x] `pnpm.cmd verify`, `git diff --check`를 실행한다.

### Task 3: Plan lifecycle

**Files:** this plan; `docs/exec-plans/active/README.md`; `docs/ROADMAP.md`.

- [x] 검증 증거·결과·잔여 작업을 기록한다.
- [x] plan을 `docs/exec-plans/completed/`로 이동하고 indexes를 갱신한다.
- [x] implementation, documentation commits only stage their own files.

## Completion

- Result: FastAPI URL registration is grouped into catalog, question, and auth/history routers; endpoint implementations and `app.main` patch points remain unchanged.
- Verification: `pnpm.cmd verify` on 2026-08-28 (core 26 tests; API 683 tests), plus `ruff check` and the focused API contract suite.
- Review: scoped review findings on roadmap status and OpenAPI/CORS regression coverage were corrected and re-reviewed as addressed.
- Residual: `graphify update .` was attempted but cannot scan pre-existing access-denied `.pytest-temp-task3*` directories; no graph artifact was modified by this task.
