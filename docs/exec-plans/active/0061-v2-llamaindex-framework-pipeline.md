> 작업 ID: `F-005`
> 상태: `Picked Up`
> 유형: `Feature`
> 보조 라벨: `Data`, `Reliability`, `Security`, `Performance`
> 선행 조건: 없음
> 참고 범위:
> - `docs/design-docs/v2-llamaindex-framework-redesign.md` §5~§11 — generation, execution, phase API 정본 계약
> - `apps/api/app/main.py` L58-L132, L272-L308 — 현 v2 구성과 단일 `/v2/questions` 경계
> - `apps/law-rag-llamaindex/src/law_rag_llamaindex/` — 기존 ingestion/retrieval adapter
> - `apps/web/lib/api-client.ts` L107-L114 — 교체할 v2 transport

# V2 LlamaIndex 프레임워크 파이프라인 개편 구현 계획

> **에이전트 작업자를 위한 안내:** 필수 서브스킬: 이 계획을 태스크 단위로 구현하려면 superpowers:subagent-driven-development(권장) 또는 superpowers:executing-plans를 사용하세요. 각 단계는 체크박스(`- [ ]`) 문법으로 진행 상황을 추적합니다.

**목표:** generation으로 격리된 LlamaIndex 색인과 서버 정본 `question_execution`을 도입하고, 기존 v2 단일 질문 API를 prepare/core/finalize phase API와 검증된 SSE로 교체한다.

**아키텍처:** `apps/law-rag-llamaindex`는 generation catalog, source fingerprint, active index cache 및 LlamaIndex ingestion/query/synthesis adapter를 소유한다. `apps/api`의 domain/application은 execution 상태 전이, frozen citation, grounding, issue ledger, DB capacity lease와 final response를 결정하며 FastAPI는 JSON/SSE transport로만 노출한다. 웹은 닫힌 `next_action`만 따라 호출하고 마지막 `complete.response`로 화면 상태를 교체한다.

**기술 스택:** Python 3.14, FastAPI, SQLAlchemy async, Alembic, PostgreSQL/pgvector, LlamaIndex, NVIDIA NIM, Next.js/React/TypeScript, pytest/pytest-asyncio, Vitest.

**Spec:** `docs/design-docs/v2-llamaindex-framework-redesign.md`

## 전역 제약 조건

- v1의 request/response와 동작은 회귀 테스트로 보존하며 v1은 LlamaIndex 또는 generation table을 직접 사용하지 않는다.
- domain/application은 FastAPI, SQLAlchemy, LlamaIndex, NVIDIA SDK 타입을 import하지 않는다. adapter와 composition root만 SDK를 안다.
- 법률 주장은 frozen citation registry의 인용 위치가 있어야 한다. raw token·질문 원문·provider body·인증정보를 event와 log에 기록하지 않는다.
- corpus source는 국가법령정보 공동활용 Open API 데이터만 사용한다. generation 실패는 active pointer를 바꾸지 않는다.
- 새 generation에는 `IngestionPipeline`의 chunk/embedding만 쓰며 `vector_store` 주입, `DocstoreStrategy.UPSERTS`, 기존 active table 쓰기를 금지한다.
- `PGVectorStore`에는 composition root가 만든 sync/async engine을 주입한다. prepare는 12초, core/finalize는 각 57초, Ultra phase budget은 55초, reserve는 2초이며 v1의 52초 계약은 바꾸지 않는다.
- DB TTL capacity lease만 provider admission을 제어한다. 1초 안에 얻지 못하거나 DB 확인에 실패하면 provider 호출 전 `503 system_busy`로 fail-closed한다.
- prepare는 owner + `Idempotency-Key`, phase는 `(execution_id, phase)`로 중복을 막는다. crash 뒤 provider 완료 여부가 불명이면 자동 재호출하지 않고 `phase_recovery_required`로 끝낸다.
- 운영 DB migration·hosted NVIDIA·실제 100-concurrent 실행은 별도 명시 승인 없이는 실행하지 않고 disposable DB/fake adapter로 검증한다.

---

## 단계 구조

| 단계 | 책임 | 핵심 산출물 |
| --- | --- | --- |
| 1~3 | generation storage/index | catalog, immutable table, active pin/router |
| 4~6 | execution application | typed event/grounding, repository/lease, phase coordinator |
| 7~8 | transport and UI | SSE API, web closed-action state machine |
| 9~10 | confidence | load/observability contract, full verification/docs |

### Task 1: Generation·execution persistence migration

**Files:** Create `apps/api/migrations/versions/0015_v2_generations_and_executions.py`, `apps/api/tests/test_v2_execution_migration.py`; modify `docs/generated/db-schema.md` only after a real disposable migration result.

**Interfaces:** tables `retrieval_generations`, `retrieval_generation_sources`, singleton `retrieval_active_generation`, `question_executions`, `question_execution_events`, `question_execution_issues`, `provider_capacity_leases`. Execution holds private payload, owner/capability hash, idempotency key, generation pin, version, phase deadline/lease, frozen citations, verified response, status/outcome/expires_at.

- [ ] Write a failing migration-contract test asserting unique `(owner_scope, prepare_idempotency_key)`, `(execution_id, phase, sequence)`, `(provider, slot)`, TTL/status indexes, and singleton pointer.
- [ ] Run `uv run --directory apps/api python -m pytest tests/test_v2_execution_migration.py -v`; expect missing revision/table contract failure.
- [ ] Implement revision 0015 using UUID PKs, UTC timestamps, checked text statuses, JSONB private/event payloads, source fingerprint unique indexes, and no question text in telemetry tables.
- [ ] Re-run the focused test. If a disposable DB is available, run `uv run --directory apps/api python -m alembic upgrade head` and regenerate `docs/generated/db-schema.md`; otherwise record it unverified.
- [ ] Commit: `git add apps/api/migrations apps/api/tests/test_v2_execution_migration.py docs/generated/db-schema.md && git commit -m "feat(api): add v2 generation and execution schema"`.

### Task 2: Generation-aware ingestion and atomic publish

**Files:** Modify `source.py`, `ingest.py`, `store.py`, `config.py`; create `generations.py`, `tests/test_generations.py`, `tests/test_generation_ingest.py` under `apps/law-rag-llamaindex`.

**Interfaces:** `GenerationRepository.start/record_source/publish/rollback/active`; `GenerationVectorStoreFactory.for_generation(generation_id)`; `run_ingestion(...)` returns verified inactive-or-published generation result.

- [ ] Write failing tests: same fingerprint copies vectors DB-to-DB; transform fingerprint causes full rebuild; add/validation failure retains active pointer; publish atomically swaps one pointer.
- [ ] Run `uv run --directory apps/law-rag-llamaindex python -m pytest tests/test_generations.py tests/test_generation_ingest.py -v`; expect import failure.
- [ ] Implement a validated canonical `ProvisionRecord` reader, UUID-derived allowlisted table names, `IngestionPipeline` chunk/embedding then new-table `PGVectorStore.add()`, and source coverage/deterministic node ID/lineage/finite-dimension checks before publish.
- [ ] Run the focused tests and `tests/test_ingest.py`; expect pass.
- [ ] Commit: `git add apps/law-rag-llamaindex && git commit -m "feat(llamaindex): publish verified retrieval generations"`.

### Task 3: Pinned active index and router/query-engine adapter

**Files:** Modify `retriever.py`, `store.py`, `__init__.py`; create `active_index.py`, `router.py`, `query_engine.py`, `tests/test_active_index.py`, `tests/test_router.py`.

**Interfaces:** `ActiveVectorIndexProvider.get_pinned(generation_id) -> ActiveIndex`; `LegalRouteSelector.select(question) -> RouteDecision`; `RouteQueryEngineFactory.build(route, index) -> QueryEngine`.

- [ ] Write failing tests: pointer swap affects only later requests, in-flight generation pin survives, query embedding is called once, invalid metadata/date range is excluded, selector failure is `routing_unavailable` and no-search.
- [ ] Run `uv run --directory apps/law-rag-llamaindex python -m pytest tests/test_active_index.py tests/test_router.py -v`; expect missing modules.
- [ ] Implement engine-injected `VectorStoreIndex` cached by generation ID. Preserve current route taxonomy but never turn provider/schema timeout into a guessed route.
- [ ] Run focused tests and `tests/test_retriever.py`; expect pass.
- [ ] Commit: `git add apps/law-rag-llamaindex && git commit -m "feat(llamaindex): add pinned active index and router"`.

### Task 4: Pure execution domain, grounding and final-answer contract

**Files:** Create `apps/api/app/domain/question_execution.py`, `grounding.py`, `answer_events.py`, `pipeline_issues.py`; create `app/application/final_answer.py`, `phase_deadline.py`; create `tests/test_question_execution_domain.py`, `test_v2_grounding_events.py`, `test_v2_phase_deadline.py`.

**Interfaces:** `ExecutionStatus`, `NextAction`, `GroundedSentence`, `GroundedSection`, `CitationRegistry`, `PipelineIssue`, `AnswerEvent`; `FinalAnswerCoordinator.finalize(snapshot, evidence, issues, remaining_seconds)`; `PhaseDeadline.remaining_seconds()`.

- [ ] Write failing tests for unknown actions, absent/unknown citations, unsupported number/norm/overclaim, terminal event exclusivity, verified core plus finalize failure producing `complete(outcome="degraded")`, and one shared 55-second repair/detail budget.
- [ ] Run `uv run --directory apps/api python -m pytest tests/test_question_execution_domain.py tests/test_v2_grounding_events.py tests/test_v2_phase_deadline.py -v`; expect import failure.
- [ ] Implement pure code: grounding reads only frozen citation text; fallback/limitations are legal-claim-free constants; issues retain only public reason, recoverability, stage and phase.
- [ ] Run focused tests and `tests/test_grounding_gate.py`; expect pass.
- [ ] Commit: `git add apps/api/app/domain apps/api/app/application apps/api/tests && git commit -m "feat(api): add v2 execution and grounding domain"`.

### Task 5: Execution repository and global capacity lease

**Files:** Create `app/ports/question_execution.py`, `app/adapters/postgres_question_execution.py`, `memory_question_execution.py`, `capacity_leases.py`, `tests/test_question_execution_repository.py`, `test_capacity_leases.py`; modify repository ports/adapters.

**Interfaces:** `QuestionExecutionRepository.prepare_or_get/get_owned/transition_phase/append_event/append_issue/complete/cancel/expire`; `ConcurrencyLimiter.acquire(phase, deadline) -> Lease | SystemBusy`; every transition uses expected version.

- [ ] Write failing tests: owner/key deduplication, foreign/capability 404, running/completed phase replay, competing starts make one admission, stale reclaim/release after cancellation, DB error gives `SystemBusy`.
- [ ] Run `uv run --directory apps/api python -m pytest tests/test_question_execution_repository.py tests/test_capacity_leases.py -v`; expect missing ports/adapters.
- [ ] Implement Postgres short transactions and conditional transitions only; provider work outside transactions. Memory adapter mirrors semantics. Persist event before emission; expiry releases generation pin/lease.
- [ ] Re-run focused tests; expect pass.
- [ ] Commit: `git add apps/api/app apps/api/tests && git commit -m "feat(api): persist v2 executions and capacity leases"`.

### Task 6: Preparation service, phase coordinator, grounded streams

**Files:** Create `question_preparation.py`, `question_phase_coordinator.py`, `question_phase_streaming.py`; modify `settings.py`, `observability.py`, `nvidia_nim_answerer.py`; create `tests/test_question_preparation.py`, `test_question_phase_coordinator.py`, `test_v2_phase_streaming.py`; create `apps/law-rag-llamaindex/src/law_rag_llamaindex/synthesis.py`.

**Interfaces:** `QuestionPreparationService.prepare(payload, owner, idempotency_key) -> PreparedExecution`; `QuestionPhaseCoordinator.start_core/start_finalize`; `GroundedResponseSynthesizer.astream_phase`; `QuestionPhaseStreamingService.stream` emits only verified events.

- [ ] Write failing tests: repeated prepare does one route/retrieval, generation pin survives pointer swap, router timeout issue, safe no-evidence path, expiry/retry deadline preservation, crash uncertainty blocks invocation, raw tokens absent, core failure defers repair, event sequence replayable.
- [ ] Run the three focused API test modules; expect missing service behavior.
- [ ] Implement validation/auth/quota/readiness/date before prepare; persist route/evidence/registry before `generate_core`; core emits verified summary only. Finalize derives repair/detail solely from saved status, shares a phase budget, keeps exposed core, saves logged-in history before complete, and emits typed no-raw-exception errors.
- [ ] Run focused tests plus `tests/test_answer_quality_contract.py` and `tests/test_corpus_temporal_contract.py`; expect pass.
- [ ] Commit: `git add apps/law-rag-llamaindex apps/api/app apps/api/tests && git commit -m "feat(v2): coordinate grounded answer phases"`.

### Task 7: FastAPI prepare/core/finalize routes and removal of the v2 single route

**Files:** Modify `apps/api/app/main.py`, `domain/schemas.py`, `vercel.json`; create `app/adapters/sse_presenter.py`, `tests/test_v2_question_executions.py`; modify/remove obsolete assertions in `tests/test_v2_questions.py`.

**Interfaces:** JSON `POST /v2/question-executions`; SSE `POST /v2/question-executions/{id}/core|finalize`; stream-start validation errors are HTTP and post-start errors are typed SSE.

- [ ] Write failing tests for required idempotency header, SSE content/event JSON, closed action sequence, replay, pre-stream 503 busy, owner isolation, cancellation, and exact removal of `/v2/questions`.
- [ ] Run `uv run --directory apps/api python -m pytest tests/test_v2_question_executions.py -v`; expect 404.
- [ ] Implement thin FastAPI validation/auth/service calls. `StreamingResponse` serializes persisted events only, never raw tokens. Preserve every `/v1/*` route and the Vercel 60-second hard cap.
- [ ] Run replacement tests and `tests/test_api.py tests/test_question_timeout_budget.py`; expect pass.
- [ ] Commit: `git add apps/api && git commit -m "feat(api): replace v2 question route with execution phases"`.

### Task 8: Web closed-next-action state machine

**Files:** Modify `apps/web/lib/api-client.ts`, `contracts.ts`, `generation-retry.ts`, `chat-state.ts`, `app/page.tsx`; create `lib/v2-execution.ts`, `v2-execution.test.ts`; modify `api-client-flow.test.ts`, `chat-state.test.ts`.

**Interfaces:** `runV2Execution(input, deps) -> Promise<QuestionResponse>` creates one `Idempotency-Key`, follows only known actions, and replaces partial UI state from final `complete.response`.

- [ ] Write failing Vitest cases: prepare→core→finalize, core direct complete, repair, one phase reconnect, abort cancellation, busy display, unknown action stop, authoritative final replacement.
- [ ] Run `npm --prefix apps/web test -- v2-execution.test.ts`; expect missing module/old single-request failure.
- [ ] Implement validated POST-SSE parsing and phase-aware reconnect. The client never posts evidence, route or repair kind and never infers an action from answer text.
- [ ] Run focused Vitest and `npm --prefix apps/web run typecheck`; expect pass.
- [ ] Commit: `git add apps/web && git commit -m "feat(web): follow authoritative v2 execution protocol"`.

### Task 9: Reliability, observability and load-contract regression

**Files:** Create `apps/api/tests/test_v2_execution_load_contract.py`, `test_v2_execution_observability.py`; modify `observability.py`, `settings.py`, design decision record.

- [ ] Write fake-clock/fake-limiter tests for 100 simulated clients: bounded admission, core priority/finalize reserve, <2-second busy without provider call, reconnect deadline preservation, cancellation release, terminal exclusivity and log privacy.
- [ ] Run `uv run --directory apps/api python -m pytest tests/test_v2_execution_load_contract.py tests/test_v2_execution_observability.py -v`; expect missing behavior.
- [ ] Implement safe phase/admission/reconnect/terminal metrics with execution correlation hash only and configuration for slot/TTL/pool values. Do not invent production numeric values.
- [ ] Run focused tests and `tests/test_privacy.py`; expect pass.
- [ ] Commit: `git add apps/api docs/design-docs/v2-llamaindex-framework-redesign.md && git commit -m "test(v2): lock execution reliability contract"`.

### Task 10: Whole-workspace verification and completion

**Files:** Modify `docs/ROADMAP.md`, `docs/CURRENT_STATE.md`, `docs/exec-plans/active/README.md`; move this plan to `docs/exec-plans/completed/` only when all prior tasks finish.

- [ ] Run backend gates: `uv run --directory apps/law-rag-llamaindex python -m pytest -v`; `uv run --directory apps/api python -m pytest -v`; each app's ruff check.
- [ ] Run web gates: `npm --prefix apps/web run lint`; `npm --prefix apps/web run typecheck`; `npm --prefix apps/web test`.
- [ ] Run `git diff --check` and `git status --short`; exclude `.env`, credentials, corpus full text, fake generated schema, and unrelated user changes. Record hosted/DB checks unverified if no approved environment exists.
- [ ] Record actual commits/test output/residual operational values, move the plan, mark F-005 Done, and update CURRENT_STATE only when no picked-up milestone remains.
- [ ] Commit: `git add docs && git commit -m "docs: complete v2 framework pipeline plan"`.

## Plan self-review

- Covers generation publish/rollback (1–3), execution/idempotency/TTL (1, 5–6), grounded streaming/fallback (4, 6–7), client protocol (8), timeout/admission/load (5, 6, 9), and v1/migration evidence (7, 10).
- Provider slots, lease TTL and pool size are intentionally measured configuration values—not assumed production constants.
- Domain events/next actions originate in Task 4, persist in Task 5, coordinate in Task 6, stream in Task 7, and are consumed in Task 8.

## Milestone review gates

1. **Generation-based indexing and active pointer:** Tasks 1–3. Commit and review after an inactive generation can be verified and atomically published; no execution API change ships in this milestone.
2. **question_execution persistence, transitions, and idempotency:** Tasks 4–5. Commit and review after owner isolation, phase replay, crash fail-closed behavior, and capacity leases have dedicated tests.
3. **prepare/core/finalize API and grounded SSE:** Tasks 6–7. Freeze API contract tests before route replacement, then commit/review only when v1 regressions remain green.
4. **Web state machine, load/reconnect, and operational verification:** Tasks 8–10. Commit/review web protocol and reliability contracts separately; record any unapproved hosted/DB checks as unverified rather than simulate success.
