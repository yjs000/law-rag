# D-010 Single-Stage Router and Safe Routing-Unavailable Response Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `legal_search` mean only the grounded legal-answer pipeline and handle router timeout/provider failure as a safe, no-search `routing_unavailable` AI response.

**Architecture:** Replace the tier1/tier2 classifier composition with one injected NVIDIA-backed `QuestionRouter`. A successful `legal_search` decision proceeds through evidence retrieval, official-source filtering, answer generation, and answer validation; only router failure enters `routing_unavailable`, which uses an AI-mode deterministic-safe guidance fallback with no legal conclusion or citations.

**Tech Stack:** Python 3.14, FastAPI, Pydantic, OpenAI-compatible NVIDIA NIM client, `asyncio.timeout`, pytest/pytest-asyncio, Ruff, uv workspace.

**Spec:** `docs/design-docs/single-stage-router-and-failure-response.md`

## Global Constraints

- `legal_search` is emitted only for a successful router decision that enters `evidence_retrieval`; direct-path retrieval may omit query embedding but still follows evidence source validation, `answer_generation`, and `answer_validation`.
- The normal grounded sequence is `legal_search` → `evidence_retrieval` → `evidence_source_validation` → `answer_generation` → `answer_validation`.
- `routing_unavailable` must make zero embedding, repository retrieval, evidence-source-validation, normal-answer-generation, and normal-answer-validation calls.
- Router failures use only `routing_timeout` or `routing_provider_error`; never serialize or log an exception message, provider body, traceback, or question text in route diagnostics. `blocked_response_validation` is a separate empty-evidence shape check and must not emit the normal `answer_validation` stage.
- Keep `search_only_enabled=False`. No route may mutate that setting or return `mode="search_only"`; routing-unavailable fallback is `mode="ai"`, `action="unanswerable"`, and has empty sections, checklist, and citations.
- `clarification_required`, `realtime_required`, and `external_document_required` remain non-error routes. Their named stages are `clarification_generation` and `required_source_guidance_generation`; `blocked_answer_generation` is reserved for `routing_unavailable`.
- Do not make live NVIDIA calls, start a persistent local database, modify corpus data, or change retrieval/embedding/normal-answer fallback semantics outside this routing boundary.

---

## File Structure

| File | Responsibility |
| --- | --- |
| `apps/api/app/domain/routing.py` | Closed route/reason types, single router port, route decision conversion, and provider-failure decision factories. |
| `apps/api/app/adapters/nvidia_nim_route_classifier.py` | NVIDIA implementation of the single `QuestionRouter`; it accepts no tier or embedding hint. |
| `apps/api/app/main.py` | Composition root, router-failure branch, named generation/validation stages, and no-search fallback orchestration. |
| `apps/api/app/application/answering.py` | Deterministic AI-mode fallback builders for route guidance and `routing_unavailable`. |
| `apps/api/app/adapters/openai_answerer.py` | Prompt contract for valid route guidance and unavailable-router guidance. |
| `apps/api/app/application/request_budget.py` | Closed timeout stage names used by the renamed generation paths. |
| `apps/api/app/observability.py` | Closed structured route/timing events without router tier or raw errors. |
| `packages/law-rag-core/src/law_rag_core/domain/schemas.py` | Public `QuestionResponse.route` union including `routing_unavailable`. |
| `apps/api/tests/test_routing.py` | Domain/router-port unit tests without deterministic tier or embedding-hint tests. |
| `apps/api/tests/test_routing_pipeline.py` | HTTP pipeline contracts for normal legal search, valid guidance routes, and routing-unavailable zero-search behavior. |
| `apps/api/tests/test_question_timeout_budget.py` | Timeout regression for the new routing-unavailable fallback and renamed stages. |
| `apps/api/tests/test_question_cancellation.py` and `apps/api/tests/test_security_boundaries.py` | Renamed stage event and safe-log contract regressions. |
| `apps/api/scripts/evaluate_routing_fixture.py` | Explicit live-only single-router fixture evaluation; it no longer synthesizes mock/tier results. |
| `apps/api/pyproject.toml` | Removal of the unused Kiwi runtime dependency. |
| `docs/design-docs/index.md`, `docs/design-docs/pre-retrieval-question-routing.md`, `ARCHITECTURE.md`, `docs/ROADMAP.md`, `docs/CURRENT_STATE.md`, and `docs/exec-plans/active/README.md` | Current routing contract, plan lifecycle, and active-plan pointers. |

### Task 1: Replace the tiered router with a single typed router

**Files:**
- Modify: `apps/api/app/domain/routing.py`
- Modify: `apps/api/app/adapters/nvidia_nim_route_classifier.py`
- Modify: `apps/api/scripts/evaluate_routing_fixture.py`
- Modify: `apps/api/pyproject.toml`
- Delete: `apps/api/app/adapters/mock_route_classifier.py`
- Delete: `apps/api/scripts/build_tier1_term_dictionary.py`
- Modify: `apps/api/tests/test_routing.py`
- Modify: `apps/api/tests/test_routing_pipeline.py`

**Interfaces:**
- Consumes: a question string and the production NVIDIA router or a test fake.
- Produces: `QuestionRouter.route(question: str) -> RouteJudgment`; `route_question(question: str, router: QuestionRouter) -> RouteDecision`; `RouteDecision(route, reason_code, confidence, missing_fields, explanation)` with no tier field.

- [x] **Step 1: Replace tier-specific unit tests with the failing single-router contract**

```python
class FakeRouter:
    async def route(self, question: str) -> RouteJudgment:
        return RouteJudgment(
            route="clarification_required",
            confidence=0.9,
            reason="발전설비용량에 따라 달라집니다.",
            missing_fields=("발전설비용량",),
        )

async def test_route_question_converts_single_router_judgment() -> None:
    decision = await route_question("용량에 따라 허가가 달라지나요?", FakeRouter())

    assert decision.route == "clarification_required"
    assert decision.reason_code == "router_judgment"
    assert decision.missing_fields == ("발전설비용량",)
```

Delete tests for keyword matchers, `route_tier1`, cosine similarity, nearest examples, tier fields, and hint prompts. Add a test that the router output schema rejects `routing_unavailable`, because it is an application-created failure route rather than a provider judgment.

- [x] **Step 2: Run the focused test and confirm the old interface fails**

Run: `uv run --directory apps/api python -m pytest tests/test_routing.py -q`

Expected: FAIL because `QuestionRouter`, `route_question`, and the tier-free `RouteDecision` interface do not exist yet.

- [x] **Step 3: Implement the single-router domain and NVIDIA adapter**

```python
QuestionRoute = Literal[
    "legal_search",
    "clarification_required",
    "realtime_required",
    "external_document_required",
    "routing_unavailable",
]
RoutingReasonCode = Literal[
    "router_judgment", "routing_timeout", "routing_provider_error"
]

class QuestionRouter(Protocol):
    async def route(self, question: str) -> RouteJudgment: ...

async def route_question(question: str, router: QuestionRouter) -> RouteDecision:
    judgment = await router.route(question)
    return RouteDecision(
        route=judgment.route,
        reason_code="router_judgment",
        confidence=judgment.confidence,
        missing_fields=judgment.missing_fields,
        explanation=judgment.reason,
    )
```

Keep `RouteJudgment.route` restricted to the four provider-resolvable routes. Rename `NvidiaNimRouteClassifier` to `NvidiaNimQuestionRouter`, rename `classify` to `route`, remove the hint parameter and all nearest-example prompt text, and use one direct prompt containing only the closed route definitions and question. Delete the tier1 rules, the mock adapter, the Kiwi dictionary builder, and the `kiwipiepy` dependency. Change the fixture evaluator to require `NVIDIA_API_KEY`, call `QuestionRouter.route` once per case, emit no tier metrics, and do not run it during this task.

- [x] **Step 4: Run focused router tests and static checks**

Run: `uv run --directory apps/api python -m pytest tests/test_routing.py tests/test_routing_pipeline.py -q`

Expected: PASS without importing `MockRouteClassifier`, `route_tier1`, `route_tier2`, or Kiwi.

Run: `uv run --project apps/api ruff check apps/api/app/domain/routing.py apps/api/app/adapters/nvidia_nim_route_classifier.py apps/api/scripts/evaluate_routing_fixture.py apps/api/tests/test_routing.py apps/api/tests/test_routing_pipeline.py`

Expected: `All checks passed!`

- [x] **Step 5: Commit the router-boundary change**

```bash
git add apps/api/app/domain/routing.py apps/api/app/adapters/nvidia_nim_route_classifier.py apps/api/app/adapters/mock_route_classifier.py apps/api/scripts/build_tier1_term_dictionary.py apps/api/scripts/evaluate_routing_fixture.py apps/api/pyproject.toml apps/api/tests/test_routing.py apps/api/tests/test_routing_pipeline.py uv.lock
git commit -m "refactor(api): use a single question router"
```

### Task 2: Make router failure a no-search AI response with named stages

**Files:**
- Modify: `apps/api/app/main.py`
- Modify: `apps/api/app/application/answering.py`
- Modify: `apps/api/app/adapters/openai_answerer.py`
- Modify: `apps/api/app/application/request_budget.py`
- Modify: `apps/api/app/observability.py`
- Modify: `packages/law-rag-core/src/law_rag_core/domain/schemas.py`
- Modify: `apps/api/tests/test_routing_pipeline.py`
- Modify: `apps/api/tests/test_question_timeout_budget.py`
- Modify: `apps/api/tests/test_question_cancellation.py`
- Modify: `apps/api/tests/test_security_boundaries.py`
- Modify: `apps/api/tests/test_search_only_feature.py`

**Interfaces:**
- Consumes: `route_question`, `StageTimeoutError`, and a provider exception.
- Produces: `RouteDecision(route="routing_unavailable", reason_code="routing_timeout" | "routing_provider_error", confidence=0.0)`; `QuestionResponse(mode="ai", route="routing_unavailable", action="unanswerable")`; safe route and timing events.

- [x] **Step 1: Write failing HTTP contracts for timeout, provider failure, and normal legal search**

```python
class FailingRouter:
    async def route(self, question: str) -> RouteJudgment:
        raise RuntimeError("provider body must not escape")

response = TestClient(main_module.app).post(
    "/v1/questions", json={"question": "허가 절차를 알려주세요", "answer_mode": "terra"}
)
body = response.json()
assert response.status_code == 200
assert body["mode"] == "ai"
assert body["route"] == "routing_unavailable"
assert body["action"] == "unanswerable"
assert body["sections"] == []
assert body["checklist"] == []
assert body["citations"] == []
assert embedding_calls == []
assert retrieval_calls == []
assert "provider body must not escape" not in caplog.text
```

Add the equivalent timeout test with a router that awaits longer than `route_classifier_timeout_seconds`. Add a normal-router test that returns `legal_search`, then asserts exactly one embedder/repository call and records `answer_generation` followed by `answer_validation`. Add a failure test where unavailable-route guidance returns a cited or non-`unanswerable` draft; it must return the deterministic fallback instead. Set `settings.search_only_enabled=False` in every new routing-unavailable test and assert it remains false.

- [x] **Step 2: Run the routing/timeout tests and confirm existing fallback semantics fail the new contract**

Run: `uv run --directory apps/api python -m pytest tests/test_routing_pipeline.py tests/test_question_timeout_budget.py tests/test_search_only_feature.py -q`

Expected: FAIL because router failure currently reports `legal_search`, invokes embedding/retrieval, uses `blocked_route_generation`, and raises or emits `search_only` fallback when the feature is disabled.

- [x] **Step 3: Implement safe routing-unavailable orchestration and explicit stage names**

In `_answer_question`, make exactly one budgeted `route_question(payload.question, _question_router())` call. Construct only these failure decisions:

```python
except StageTimeoutError:
    route_decision = RouteDecision(
        route="routing_unavailable",
        reason_code="routing_timeout",
        confidence=0.0,
    )
except Exception:
    route_decision = RouteDecision(
        route="routing_unavailable",
        reason_code="routing_provider_error",
        confidence=0.0,
    )
```

Do not bind the caught exception to diagnostics, events, response text, or logs. Route `routing_unavailable` before query embedding and call a dedicated `_generate_blocked_answer(...)`; its deterministic fallback is built with `mode="ai"`, `action="unanswerable"`, and empty content lists regardless of `search_only_enabled`. Require a generated unavailable-route draft to pass `blocked_response_validation`: `action == "unanswerable"` and empty sections, checklist, and citations. Do not emit or count this check as normal `answer_validation`.

Rename the regular `generation` diagnostics/timing stage to `answer_generation`, add a synchronous `answer_validation` timing event around `validate_draft`, and retain `evidence_source_validation` as the named `is_allowed_source_url` filter without adding a timer or provider call. Replace `blocked_route_generation` with a shared route-guidance helper that receives an explicit stage: `clarification_generation`, `required_source_guidance_generation`, or `blocked_answer_generation`. The latter is passed only for `routing_unavailable`.

Update `TimeoutStage`, `QuestionStageTimingStage`, diagnostics keys, cancellation tests, and structured log tests to the closed replacement names. Remove `RouterTier` and the route-event `tier` field; count route metrics by route and safe reason code. Extend `QuestionResponse.route` with `routing_unavailable`. Add an explicit `routing_unavailable` prompt branch in `build_blocked_route_messages` that requests only retry guidance and an `unanswerable` empty draft. Rename the deterministic helper in `answering.py` from `route_blocked_answer` to a guidance/fallback name that always returns `mode="ai"`.

- [x] **Step 4: Run the focused safety regression suite**

Run: `uv run --directory apps/api python -m pytest tests/test_routing_pipeline.py tests/test_question_timeout_budget.py tests/test_question_cancellation.py tests/test_security_boundaries.py tests/test_search_only_feature.py -q`

Expected: PASS. The timeout/provider tests prove zero embedding and retrieval calls, no raw error in route events, `routing_unavailable` response mode `ai`, and no mutation of `search_only_enabled`.

Run: `uv run --project apps/api ruff check apps/api/app/main.py apps/api/app/application/answering.py apps/api/app/adapters/openai_answerer.py apps/api/app/application/request_budget.py apps/api/app/observability.py packages/law-rag-core/src/law_rag_core/domain/schemas.py apps/api/tests/test_routing_pipeline.py apps/api/tests/test_question_timeout_budget.py apps/api/tests/test_question_cancellation.py apps/api/tests/test_security_boundaries.py apps/api/tests/test_search_only_feature.py`

Expected: `All checks passed!`

- [x] **Step 5: Commit the safe failure path**

```bash
git add apps/api/app/main.py apps/api/app/application/answering.py apps/api/app/adapters/openai_answerer.py apps/api/app/application/request_budget.py apps/api/app/observability.py packages/law-rag-core/src/law_rag_core/domain/schemas.py apps/api/tests/test_routing_pipeline.py apps/api/tests/test_question_timeout_budget.py apps/api/tests/test_question_cancellation.py apps/api/tests/test_security_boundaries.py apps/api/tests/test_search_only_feature.py
git commit -m "fix(api): isolate unavailable routing from legal search"
```

### Task 3: Align documentation, lifecycle records, and final verification

상태: 문서 정렬·최종 로컬 검증 완료 · parent-level integration decision 대기 (2026-08-25)

**Files:**
- Modify: `docs/design-docs/index.md`
- Modify: `docs/design-docs/pre-retrieval-question-routing.md`
- Modify: `ARCHITECTURE.md`
- Modify: `docs/ROADMAP.md`
- Modify: `docs/CURRENT_STATE.md`
- Modify: `docs/exec-plans/todo/README.md`
- Modify: `docs/exec-plans/active/README.md`
- Modify: `docs/exec-plans/active/0057-single-stage-router-and-failure-response.md`
- Modify: `scripts/check_docs.py` (D-010 documentation assertions in the existing review workflow)
- Modify: `docs/design-docs/technology-stack.md` and `docs/design-docs/always-generate-answer.md`
  (current provider/routing contract and superseded-design status)
- Modify: `apps/api/app/settings.py` (runtime configuration comments only)
- Modify: `apps/api/evaluation/route-fixture-v1.json` and
  `apps/api/evaluation/route-fixture-v1-results.json` (historical metadata only; preserve values)

**Interfaces:**
- Consumes: the completed Task 1 and Task 2 route/stage names and test evidence.
- Produces: documentation that names the single router, safe failure route, normal evidence/answer sequence, and active-plan status without claiming an unrun provider evaluation.

- [x] **Step 1: Write documentation assertions before editing prose**

Add the following checks to the existing documentation review workflow: `docs/design-docs/index.md` links `single-stage-router-and-failure-response.md`; `ARCHITECTURE.md` contains `routing_unavailable`, `answer_generation`, and `answer_validation`; no current-contract prose describes a tier1/tier2 runtime path or says a router timeout proceeds as `legal_search`.

- [x] **Step 2: Run the documentation checker and observe the stale contract**

Run: `uv run --project apps/api python scripts/check_docs.py`

Expected: the checker may pass before the prose update; manual `rg -n "tier1|tier2|routing_unavailable|blocked_route_generation|legal_search" ARCHITECTURE.md docs/design-docs` must show the old runtime wording that this task replaces.

Result: the executable D-010 contract assertion passes. The repository-wide checker still exits
1 for 32 pre-existing broken links outside the D-010 current-contract prose; none is introduced
by the documentation commit below.

- [x] **Step 3: Update authoritative documentation and active-plan metadata**

Keep the approved D-010 design link and active-plan pointers already recorded when this plan was promoted. Replace the 0028 runtime description in `ARCHITECTURE.md` and `pre-retrieval-question-routing.md` with the single NVIDIA router, the exact normal sequence, and `routing_unavailable` no-search behavior. Record that `evidence_source_validation` is an official-source filter, while `answer_validation` verifies answer structure/action/citation IDs after generation and `blocked_response_validation` checks only the unavailable-route empty shape. In this plan file, check completed boxes only after the corresponding command output is recorded, and add the final commit SHA plus exact test counts in a dated progress section. Preserve all historical fixture/result values; metadata may mark superseded status, but do not claim live NVIDIA evaluation without user-authorized evidence.

- [x] **Step 4: Run complete local verification without persistent services**

Run: `uv run --project apps/api ruff check apps/api/app apps/api/scripts apps/api/tests apps/api/migrations packages/law-rag-core/src packages/law-rag-core/tests`

Expected: `All checks passed!`

Run: `uv run --project apps/api ruff check --select D100,D101,D102,D103,D107,D200,D205,D209,D400,D401,D403 apps/api/app/main.py apps/api/app/adapters/llamaindex_repository.py`

Expected: `All checks passed!`

Run (API, from the API project directory; `tests` is intentionally project-relative):
`$env:PYTHONPATH='.;..\..\packages\law-rag-core\src;..\collector\src'; uv run --directory apps/api python -m pytest --basetemp C:\Users\Family\.codex\visualizations\2026\08\25\d010-api-full-relative tests -q`

Run (core package):
`uv run --project packages/law-rag-core python -m pytest --basetemp C:\Users\Family\.codex\visualizations\2026\08\25\d010-core-full-final packages/law-rag-core/tests -q`

Expected: PASS or only pre-existing, explicitly identified skips; no Docker or persistent database startup.

Run: `uv run --project apps/api python scripts/check_docs.py`

Expected: the D-010 assertion passes; the repository checker may still report only its known
pre-existing broken-link inventory.

Result: full Ruff, the docstring Ruff selection, the focused D-010 suite, and both complete local
suites pass. The API suite reports `639 passed, 3 skipped, 1 warning` in 44.83s; the core suite
reports `26 passed` in 0.25s. The warning is the existing Starlette/httpx deprecation. The earlier
11-case failure run was resolved by a reusable successful `legal_search` router fixture for normal
AI/grounding tests, explicit search-only enablement for the historical Supabase storage flow, and
the search-only fixture on the temporal readiness case. D-010 assertions and Ruff checks pass. The
technology ADR, superseded always-generate design, settings comments, and historical fixture
metadata are now aligned with D-010 without changing production behavior or historical result
values. The
repository docs checker still reports 32 pre-existing broken links; this is separate documentation
debt, not a D-010 regression gate. No live provider or persistent service was used.

- [x] **Step 5: Commit documentation and verification evidence**

```bash
git add ARCHITECTURE.md docs/design-docs/index.md docs/design-docs/pre-retrieval-question-routing.md docs/ROADMAP.md docs/CURRENT_STATE.md docs/exec-plans/active/README.md docs/exec-plans/active/0057-single-stage-router-and-failure-response.md
git commit -m "docs: record single-stage routing contract"
```

## Task 3 progress — 2026-08-25

- Task 1 implementation and review-fix commits: `9bcd965`, `88d8964`; focused router contract
  verification was `7 passed` and the reviewed script checks passed. No live NVIDIA fixture was
  run.
- Task 2 implementation and review-fix commits: `bd70103`, `7c9707d`; focused safety regression
  verification was `38 passed, 2 warnings`, plus `3 passed, 1 warning` for request-budget tests.
- Task 3 commit sequence: `f58c5d4 docs: record single-stage routing contract`; `ea5fc59 docs:
  record D-010 Task 3 verification evidence`; `cf0a066 docs: add D-010 Task 3 report`;
  `6dd410d fix(tests): align API fixtures with single-stage routing`; `46e7040 docs: finalize
  D-010 verification evidence`; `56ae8ab docs: align D-010 lifecycle status`; `21689e0 docs:
  align superseded D-010 records`; `713d64f docs: record D-010 metadata commit`; `fd31dd2 docs:
  record D-010 alignment commit`; `e2daefe docs: correct D-010 assertion evidence`; final audit
  alignment commit `e44497c docs: reconcile D-010 lifecycle evidence`; `10b72d4 docs: record final
  D-010 lifecycle SHA`; `a2a9c1d docs: align current D-010 contract records`; `e632c86 docs:
  record D-010 contract alignment evidence`.
- Task 3 executable D-010 assertions (routing, active E-10, superseded designs, current contract
  records): exit 0
  (`d010 routing assertions passed`). Full Ruff and docstring Ruff: exit 0 (`All checks passed!`).
  Final focused D-010 suite: `43 passed, 1 warning` in 3.89s; final API suite: `639 passed,
  3 skipped, 1 warning` in 44.83s; final core suite: `26 passed` in 0.25s.
- Complete local verification used no Docker, persistent service, database, or live provider.
  The NVIDIA-keyed fixture evaluator remains intentionally unrun.
- Repository docs checker: exit 1 with 32 pre-existing broken-link reports. All four D-010 assertion
  functions pass; unrelated documentation debt is not repaired in this task. The overall plan
  remains Active only for parent-level integration decision, not because of the solved API failures.

## Plan Self-Review

- Spec coverage: Task 1 removes the tiered/mock/embedding-hint router and Kiwi dependency. Task 2 implements `routing_unavailable`, safe reason codes, zero-search behavior, AI-mode deterministic fallback, stage names, response schema, and raw-error safety. Task 3 updates all authoritative documents and runs the CI-equivalent API checks.
- Placeholder scan: no deferred implementation markers are used; each task names concrete files, interfaces, assertions, commands, and commits.
- Type consistency: `QuestionRouter.route` returns `RouteJudgment`; `route_question` returns `RouteDecision`; only `_answer_question` creates `routing_timeout` and `routing_provider_error` decisions; `QuestionResponse.route` contains `routing_unavailable`.
