# F-006 대화형 clarification workflow Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

> 작업 ID: `F-006`
> 상태: `Picked Up`
> 유형: `Feature`
> 보조 라벨: `Reliability`, `Security`, `UX`
> 선행 조건: [승인된 설계](../../superpowers/specs/2026-09-03-conversational-clarification-workflow-design.md)
> 참고 범위:
> - `apps/api/app/application/v2/phase_service.py` — v2 prepare/core/finalize 정본 흐름
> - `apps/api/app/domain/grounding.py` — frozen citation 검증 경계
> - `packages/law-rag-core/src/law_rag_core/domain/schemas.py` — API 계약 정본

**Goal:** 사용자 사실 부족 질문을 grounded interim 답변과 재개 가능한 clarification case 대화로 처리한다.

**Architecture:** 별도 `clarification_cases`가 장기 대화 상태를 소유하고, 요청마다 LlamaIndex Workflow가 case를 읽어 NVIDIA Ultra 판단과 서버 검증을 조정한다. 기존 question execution은 각 턴의 검색·생성·citation snapshot만 소유하며, `interim`, `full`, `conditional` 정책은 구조화 claim 검증 뒤에만 응답으로 공개한다.

**Tech Stack:** Python 3.14, Pydantic, FastAPI, SQLAlchemy async/Alembic, LlamaIndex Workflows, NVIDIA NIM, pytest, Next.js/TypeScript, Vitest.

**Spec:** `docs/superpowers/specs/2026-09-03-conversational-clarification-workflow-design.md`

## Global Constraints

- 법률 주장은 frozen citation registry의 citation ID를 가져야 한다.
- claim 검증은 텍스트 금칙어가 아니라 `GroundedClaim` 구조와 case 상태만 사용한다.
- case 원문과 fact 값은 telemetry, 로그, 공개 SSE event에 기록하지 않는다.
- case는 owner scope 또는 익명 capability hash로만 접근하며 24시간 뒤 만료한다.
- 모든 blocking fact가 answered이면 자동 full 답변, 명시 요청이면 conditional 답변, 그 외는 interim 답변과 waiting state다.
- 최초 포맷은 모든 blocking fact, 이후 포맷은 남은 전부; 6개 이상일 때만 3~5개 그룹으로 보인다.
- v1 API와 기존 v2 legal-search 계약은 회귀 없이 유지한다.

---

### Task 1: Case domain과 결정론적 claim 정책

**Files:**
- Create: `apps/api/app/domain/clarification.py`
- Modify: `apps/api/app/domain/grounding.py`, `apps/api/tests/test_grounding.py`
- Create: `apps/api/tests/test_clarification_domain.py`

**Interfaces:**
- Produces `FactStatus`, `AnswerPolicy`, `RequiredFact`, `ClarificationCase`, `GroundedClaim`, `validate_claim()`.
- `ClarificationCase.all_blocking_facts_answered()` returns true only when every blocking fact is `answered`.
- `validate_claim(claim, case, citations)` checks non-empty text/citations, citation membership, and fact status by claim kind.

- [x] Write failing domain tests for answered/declined removal, 1–5 vs 6+ fact grouping, full-policy sufficiency, and stale case version rejection.
- [x] Run `uv run --directory apps/api python -m pytest tests/test_clarification_domain.py tests/test_grounding_gate.py -v`; observe missing domain module before implementation.
- [x] Implement immutable domain models and pure transition/formatting functions; do not import FastAPI, SQLAlchemy, LlamaIndex, or NVIDIA SDK.
- [x] Add `GroundedClaim` validation: general rules have citations and no fact IDs; case application has citations and non-empty answered fact IDs; conditional has citations and known fact IDs.
- [x] Re-run the focused tests; pass.
- [x] Commit `feat(api): add clarification case domain`.

### Task 2: Case persistence, migration, ownership and expiry

**Files:**
- Create: `apps/api/migrations/versions/0017_clarification_cases.py`
- Create: `apps/api/app/ports/clarification_case.py`
- Create: `apps/api/app/adapters/postgres_clarification_case.py`, `apps/api/app/adapters/memory_clarification_case.py`
- Create: `apps/api/tests/test_clarification_case_repository.py`, `apps/api/tests/test_clarification_case_migration.py`

**Interfaces:**
- `ClarificationCaseRepository.create_or_get`, `get_owned`, `merge`, `mark_waiting`, `complete`, `cancel`, `expire`.
- `merge(case_id, owner_scope, expected_version, facts)` returns the incremented snapshot or raises conflict; anonymous calls also require the capability hash.

- [x] Write failing migration tests for UUID PK, owner/capability fields, JSONB facts, status check, expiry index, and `(case_id, version)` optimistic update contract.
- [x] Write memory/Postgres contract tests for owner isolation, wrong anonymous capability, expiration, and simultaneous version updates.
- [x] Run the two focused test modules; observe missing migration/port/adapters before implementation.
- [x] Implement migration and matching memory/Postgres adapters; use short transactions and never write raw user input to events/issues.
- [x] Re-run focused tests; pass.
- [ ] Commit `feat(api): persist clarification cases securely`.

### Task 3: NVIDIA turn judgment and LlamaIndex clarification workflow

**Files:**
- Create: `apps/api/app/adapters/nvidia_nim_clarification.py`
- Create: `apps/api/app/application/clarification_workflow.py`
- Modify: `apps/api/app/bootstrap.py`, `apps/api/app/application/v2/dependencies.py`
- Create: `apps/api/tests/test_clarification_workflow.py`, `apps/api/tests/test_nvidia_nim_clarification.py`

**Interfaces:**
- `ClarificationTurnJudgment` has `intent`, `submitted_facts`, and initial `required_facts` candidates.
- `ClarificationWorkflow.run_turn(request, owner)` returns `ClarificationOutcome(case, policy, question_format)`.
- initial route uses the configured NVIDIA Ultra router; continuation uses structured intent/fact extraction only.

- [ ] Write failing tests that assert initial output contains all blocking facts, continuation removes answered/declined facts, six facts expose a 3–5-item group, and free conversation retains the case.
- [ ] Add fake NVIDIA tests for invalid JSON/provider failure; assert no case mutation on failure.
- [ ] Run focused tests; expect missing workflow and adapter imports.
- [ ] Implement custom LlamaIndex `Event` classes and `Workflow` steps for load/create, interpret, validate/merge, policy decision, and question formatting. `Context` must contain only request-local identifiers.
- [ ] Wire factories at the composition root; no domain/application import may depend on SDK types.
- [ ] Re-run focused tests; expect pass.
- [ ] Commit `feat(api): orchestrate clarification conversations`.

### Task 4: V2 policy-aware generation and grounding

**Files:**
- Modify: `apps/api/app/adapters/openai_answerer.py`, `apps/api/app/adapters/nvidia_nim_answerer.py`, `apps/api/app/application/v2/phase_service.py`, `apps/api/app/application/v2/grounding.py`
- Modify: `packages/law-rag-core/src/law_rag_core/domain/schemas.py`
- Create: `apps/api/tests/test_clarification_answering.py`

**Interfaces:**
- `QuestionRequest` gains optional case reference fields; `QuestionResponse` gains optional structured clarification continuation.
- answerer structured output includes `GroundedClaim[]`; phase service passes confirmed/unresolved facts and answer policy.
- response validation rejects a claim before any SSE publication when `validate_claim` fails.

- [ ] Write failing tests for interim general/conditional claims, interim case application with answered dependencies, rejected ungrounded/missing-fact claims, full completion, and explicit conditional completion.
- [ ] Run `uv run --directory apps/api python -m pytest tests/test_clarification_answering.py tests/test_v2_question_executions.py tests/test_grounding_gate.py -v`; expect assertion failures.
- [ ] Implement structured answer schema and deterministic claim gate; preserve existing answer schemas by making new continuation fields optional.
- [ ] Integrate workflow outcome into prepare/core/finalize so interim answers use normal retrieval and frozen citations, then persist waiting status only after grounded response creation.
- [ ] Re-run focused tests; expect pass.
- [ ] Commit `feat(v2): ground clarification answer policies`.

### Task 5: V2 transport, web continuation UX, and completion docs

**Files:**
- Modify: `apps/api/app/api/v2/question_executions.py`, `apps/api/tests/test_v2_question_executions.py`
- Modify: `apps/web/lib/contracts.ts`, `apps/web/lib/v2-execution.ts`, `apps/web/lib/chat-state.ts`, `apps/web/app/page.tsx`
- Create: `apps/web/lib/clarification-state.test.ts`, `apps/web/lib/clarification-flow.test.ts`
- Modify: `docs/ROADMAP.md`, `docs/exec-plans/active/README.md`, `docs/exec-plans/todo/0047-clarification-loop-dedup-and-unanswered-handling.md`

**Interfaces:**
- Existing `POST /v2/question-executions` accepts optional `clarification_case_id` and anonymous capability; no resume endpoint is added.
- completed response optionally contains `{ case_id, status: "waiting_for_user", question_format, remaining_count }`.
- chat state attaches a pending case to the next normal composer submission and clears it on completion/cancel/new case/expiry.

- [ ] Write failing API tests for response continuation privacy and invalid/foreign case rejection; write Vitest cases for initial format, fact removal, grouped format, free-chat retention, explicit answer request, and case clearing.
- [ ] Run focused API/Vitest tests; expect failures.
- [ ] Implement transport mapping and chat UX without exposing capability in rendered messages or telemetry.
- [ ] Update roadmap: add F-006, mark only the current milestone Picked Up, retain B-001 as Task 6 regression; update active plan index and move/annotate 0047 only when its completion condition is met.
- [ ] Run focused tests, then full gates: API pytest/ruff, LlamaIndex pytest/ruff, web lint/typecheck/test, and `git diff --check`.
- [ ] Run `graphify update .`, record results, complete the active plan, move it to `completed/`, and commit documentation separately from implementation.

## Plan self-review

- Spec coverage: Tasks 1–2 cover case state, privacy, isolation, expiry, and concurrency; Task 3 covers Ultra and LlamaIndex orchestration; Task 4 covers policy-aware structured grounding; Task 5 covers existing V2 API, web UX, roadmap, B-001 linkage, verification, and graph refresh.
- No placeholder work remains: every task has explicit files, interfaces, failure-first tests, commands, and a commit boundary.
- Type consistency: the case and claim domain models originate in Task 1; repository consumes them in Task 2; workflow returns them in Task 3; v2 response and web contracts consume them only after Task 4.
