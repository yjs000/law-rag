# 0045: Web/API 질문 timeout 예산 정렬 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Vercel의 60초 강제 종료 전에 API가 안전한 응답을 마치고, Web은 55초마다 새 요청 ID로 최대 3회 시도하여 약 3분 안에 AI 답변 또는 보존된 검색 fallback을 확정한다.

**Architecture:** API 요청 시작 시 단 하나의 52초 monotonic deadline을 만들고 라우팅 8초, 임베딩 5초, 검색 8초, 답변 생성 40초의 단계별 상한을 남은 예산과 함께 적용한다. 생성 뒤 검증·저장·직렬화를 위해 3초를 남기며, Web은 API soft deadline보다 3초 긴 55초에 요청을 끊고 새 `client_request_id`로 재요청한다. Web은 timeout, HTTP 502/503/504, `generation_error`만 재시도하고 완료된 검색 fallback은 마지막까지 보존한다.

**Tech Stack:** Python 3.14, FastAPI, `asyncio.timeout`, Pydantic Settings, pytest/pytest-asyncio, Next.js 16, TypeScript 5.9, Vitest 4, Vercel Functions.

## Global Constraints

- Vercel Function hard limit은 `apps/api/vercel.json`의 `maxDuration: 60`을 유지한다.
- API 전체 soft deadline은 52초, 응답 마무리 reserve는 3초다.
- API 단계별 상한은 라우팅 8초, 임베딩 5초, 검색과 corpus 기준시점 조회를 합쳐 8초, 답변 생성 40초다.
- 각 단계의 실제 timeout은 `min(단계 상한, 전체 남은 시간 - 3초 reserve)`다. 단계별 상한을 단순 합산하지 않는다.
- Web 한 요청의 감시 timeout은 55초, 총 시도 횟수는 최초 요청을 포함해 3회, 전체 상한은 170초다.
- 이전 요청 취소는 최대 1초만 기다리는 best-effort 동작이며 새 요청을 막지 않는다.
- Web 재시도 대상은 자체 timeout, HTTP 502/503/504, `fallback_reason=generation_error`다.
- 402/429, `ai_disabled`, `quota_exhausted`, `billing_or_quota_error`, `embedding_error`, `grounding_failed`, `no_evidence`, 입력·인증·기준일 오류, 사용자 중지는 재시도하지 않는다.
- `generation_error` 검색 fallback을 한 번이라도 받았으면 이후 시도가 모두 실패해도 가장 최근 fallback을 반환한다.
- 로그에는 `request_id`, 닫힌 stage/outcome 값, 정수형 시간만 기록한다. 질문·근거 원문·사용자 정보·오류 전문·인증정보는 기록하지 않는다.
- `Settings.request_timeout_seconds=30`은 Supabase Auth용 기존 설정이므로 재사용하거나 이름을 바꾸지 않는다.
- 운영 환경변수 수정, 배포, push는 사용자 승인 전에는 실행하지 않는다.
- 이 계획을 착수할 때 파일을 같은 번호로 `docs/exec-plans/active/`로 이동한다.

---

## File map

- Create `apps/api/app/application/request_budget.py`: monotonic 전체 deadline과 단계별 timeout 계산의 유일한 구현.
- Create `apps/api/tests/test_request_budget.py`: 예산 계산, reserve, 단계 timeout 단위 테스트.
- Modify `apps/api/app/settings.py`, `apps/api/.env.example`: 52/3/8/5/8/40초 설정과 조합 검증.
- Modify `apps/api/app/main.py`: 요청 예산 생성, 단계별 적용, timeout별 fallback/503 처리.
- Create `apps/api/tests/test_question_timeout_budget.py`: 질문 파이프라인의 라우팅·임베딩·검색·생성 timeout 경계 테스트.
- Modify `apps/api/app/observability.py`, `apps/api/tests/test_security_boundaries.py`: 비식별 타이밍 로그와 보안 테스트.
- Modify `apps/web/lib/api-client.ts`, `apps/web/lib/api-client-flow.test.ts`: HTTP status를 보존하는 안전한 오류 경계.
- Modify `apps/web/lib/generation-retry.ts`, `apps/web/lib/generation-retry.test.ts`: 55초×3회, 170초 전체 상한, fallback 보존.
- Modify `ARCHITECTURE.md`, `docs/RELIABILITY.md`, `docs/design-docs/vercel-supabase-deployment.md`: 결정·운영 계약.
- Modify `docs/exec-plans/todo/0043-layperson-answer-contract-v2.md`: hosted 비교 전에 0045가 필요하다는 의존성 연결.

---

### Task 1: API 요청 예산과 설정 계약

**Files:**
- Create: `apps/api/app/application/request_budget.py`
- Create: `apps/api/tests/test_request_budget.py`
- Modify: `apps/api/app/settings.py`
- Modify: `apps/api/tests/test_settings.py`
- Modify: `apps/api/.env.example`

**Interfaces:**
- Produces: `RequestBudget.start(total_seconds, reserve_seconds, clock=time.monotonic) -> RequestBudget`
- Produces: `RequestBudget.remaining_seconds() -> float`
- Produces: `await RequestBudget.run(stage, operation, cap_seconds) -> T`
- Produces: `StageTimeoutError.stage: TimeoutStage`
- Consumes later: `_answer_question`가 외부 호출 단계마다 같은 `RequestBudget`을 사용한다.

- [ ] **Step 1: Write failing budget tests**

```python
# apps/api/tests/test_request_budget.py
import asyncio

import pytest

from app.application.request_budget import RequestBudget, StageTimeoutError


def test_stage_timeout_uses_smaller_of_cap_and_remaining_work_budget() -> None:
    now = {"value": 100.0}
    budget = RequestBudget.start(52, 3, clock=lambda: now["value"])
    assert budget.stage_timeout_seconds(40) == 40
    now["value"] = 120.0
    assert budget.stage_timeout_seconds(40) == 29


def test_stage_timeout_rejects_work_when_only_response_reserve_remains() -> None:
    now = {"value": 100.0}
    budget = RequestBudget.start(52, 3, clock=lambda: now["value"])
    now["value"] = 149.0
    with pytest.raises(StageTimeoutError) as caught:
        budget.stage_timeout_seconds(40, stage="generation")
    assert caught.value.stage == "generation"


@pytest.mark.asyncio
async def test_run_converts_asyncio_timeout_to_stage_timeout() -> None:
    budget = RequestBudget.start(0.02, 0.005)
    with pytest.raises(StageTimeoutError) as caught:
        await budget.run("retrieval", lambda: asyncio.sleep(1), cap_seconds=0.01)
    assert caught.value.stage == "retrieval"
```

- [ ] **Step 2: Run the new tests and verify the module is missing**

Run: `cd apps/api; uv run pytest tests/test_request_budget.py -q`

Expected: FAIL during collection with `ModuleNotFoundError: app.application.request_budget`.

- [ ] **Step 3: Implement the request-budget primitive**

```python
# apps/api/app/application/request_budget.py
from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Literal, TypeVar

TimeoutStage = Literal["routing", "embedding", "retrieval", "generation"]
T = TypeVar("T")


class StageTimeoutError(TimeoutError):
    def __init__(self, stage: TimeoutStage) -> None:
        super().__init__(f"{stage} exceeded its request budget")
        self.stage = stage


@dataclass(frozen=True)
class RequestBudget:
    deadline: float
    reserve_seconds: float
    clock: Callable[[], float]

    @classmethod
    def start(
        cls,
        total_seconds: float,
        reserve_seconds: float,
        *,
        clock: Callable[[], float] = time.monotonic,
    ) -> "RequestBudget":
        return cls(clock() + total_seconds, reserve_seconds, clock)

    def remaining_seconds(self) -> float:
        return max(0.0, self.deadline - self.clock())

    def stage_timeout_seconds(
        self, cap_seconds: float, *, stage: TimeoutStage = "generation"
    ) -> float:
        timeout = min(cap_seconds, self.remaining_seconds() - self.reserve_seconds)
        if timeout <= 0:
            raise StageTimeoutError(stage)
        return timeout

    async def run(
        self,
        stage: TimeoutStage,
        operation: Callable[[], Awaitable[T]],
        *,
        cap_seconds: float,
    ) -> T:
        timeout = self.stage_timeout_seconds(cap_seconds, stage=stage)
        try:
            async with asyncio.timeout(timeout):
                return await operation()
        except TimeoutError as exc:
            raise StageTimeoutError(stage) from exc
```

- [ ] **Step 4: Add exact settings defaults and cross-field validation**

Add these fields to `Settings` and replace the three existing provider defaults:

```python
question_request_timeout_seconds: float = Field(default=52, gt=0, le=55)
response_reserve_seconds: float = Field(default=3, ge=1, le=10)
route_classifier_timeout_seconds: float = Field(default=8, gt=0, le=20)
embedding_timeout_seconds: float = Field(default=5, gt=0, le=30)
retrieval_timeout_seconds: float = Field(default=8, gt=0, le=20)
answer_timeout_seconds: float = Field(default=40, gt=0, le=52)
```

Extend the existing `model_validator`:

```python
if self.response_reserve_seconds >= self.question_request_timeout_seconds:
    raise ValueError("response reserve must be smaller than question request timeout")
if self.answer_timeout_seconds > (
    self.question_request_timeout_seconds - self.response_reserve_seconds
):
    raise ValueError("answer timeout must fit before the response reserve")
```

Add tests for all six defaults and both invalid combinations. Assert `request_timeout_seconds == 30` separately so the Supabase Auth timeout cannot be accidentally repurposed.

- [ ] **Step 5: Document the environment contract**

Replace outdated timeout comments in `apps/api/.env.example` with:

```dotenv
# /v1/questions: 60초 Vercel hard limit보다 8초 먼저 끝내고 응답 마무리에 3초를 남긴다.
QUESTION_REQUEST_TIMEOUT_SECONDS=52
RESPONSE_RESERVE_SECONDS=3
ROUTE_CLASSIFIER_TIMEOUT_SECONDS=8
EMBEDDING_TIMEOUT_SECONDS=5
RETRIEVAL_TIMEOUT_SECONDS=8
ANSWER_TIMEOUT_SECONDS=40
ANSWER_GENERATION_MAX_ATTEMPTS=3

# Supabase Auth HTTP 요청용이며 /v1/questions 전체 예산과 별개다.
REQUEST_TIMEOUT_SECONDS=30
```

- [ ] **Step 6: Verify and commit Task 1**

Run: `cd apps/api; uv run pytest tests/test_request_budget.py tests/test_settings.py -q`

Expected: all selected tests PASS.

Run: `cd apps/api; uv run ruff check app/application/request_budget.py app/settings.py tests/test_request_budget.py tests/test_settings.py`

Expected: exit code 0.

```bash
git add apps/api/app/application/request_budget.py apps/api/app/settings.py apps/api/.env.example apps/api/tests/test_request_budget.py apps/api/tests/test_settings.py
git commit -m "feat(api): define coordinated question timeout budget"
```

---

### Task 2: Apply the shared budget to the API pipeline

**Files:**
- Modify: `apps/api/app/main.py:206-430`
- Create: `apps/api/tests/test_question_timeout_budget.py`
- Modify: `apps/api/tests/test_ai_fallback.py`
- Modify: `apps/api/tests/test_question_cancellation.py`

**Interfaces:**
- Consumes: `RequestBudget`, `StageTimeoutError`, Task 1 settings.
- Produces: `_answer_question(payload, request, user, budget) -> QuestionResponse`.
- Produces: generation timeout as HTTP 200 search-only response with `fallback_reason="generation_error"` when evidence already exists.
- Produces: retrieval timeout as HTTP 503 with a fixed message because no trustworthy evidence response exists.

- [ ] **Step 1: Write failing API boundary tests**

Create `test_question_timeout_budget.py` with ready legal-hit and deterministic slow doubles. Cover these assertions:

```python
def test_retrieval_timeout_returns_safe_503(client, monkeypatch):
    response = client.post("/v1/questions", json=_payload_json())
    assert response.status_code == 503
    assert response.json()["detail"] == (
        "법령 검색 시간이 초과되었습니다. 잠시 후 다시 시도해 주세요."
    )


def test_generation_timeout_returns_search_fallback(client, monkeypatch):
    response = client.post("/v1/questions", json=_payload_json())
    assert response.status_code == 200
    assert response.json()["mode"] == "search_only"
    assert response.json()["fallback_reason"] == "generation_error"
    assert response.json()["citations"]
```

Also cover: routing timeout continues as `legal_search`; embedding timeout passes `vector=None` and `profile_key=None` to lexical retrieval; generation is never started when only the 3-second reserve remains. Set millisecond values with `monkeypatch`; no test may wait real seconds.

- [ ] **Step 2: Run the new tests and verify current behavior fails**

Run: `cd apps/api; uv run pytest tests/test_question_timeout_budget.py -q`

Expected: FAIL because `_answer_question` has no shared budget and retrieval has no bounded timeout.

- [ ] **Step 3: Start one deadline at endpoint ingress**

Create the budget at the beginning of `question`, before validation/auth:

```python
budget = RequestBudget.start(
    settings.question_request_timeout_seconds,
    settings.response_reserve_seconds,
)
```

Pass it to `_answer_question`. Around that call, use `asyncio.timeout(budget.remaining_seconds())` as a final safety net. Convert only this outer expiry to HTTP 503 with `"질문 처리 시간이 초과되었습니다. 잠시 후 다시 시도해 주세요."`. Keep `CancelledError -> 499` unchanged so user stop never becomes a retryable server failure.

- [ ] **Step 4: Bound routing and embedding with safe degradation**

```python
route_decision = await budget.run(
    "routing",
    lambda: route_tier2(payload.question, _route_classifier()),
    cap_seconds=settings.route_classifier_timeout_seconds,
)

query_embedding = (
    await budget.run(
        "embedding",
        lambda: _embedder().embed([payload.question]),
        cap_seconds=settings.embedding_timeout_seconds,
    )
)[0]
```

Catch `StageTimeoutError` before the broad exception. Routing timeout sets diagnostics status `timed_out` and continues as `legal_search`; embedding timeout sets `embedding_failed=True`, status `timed_out`, and continues with lexical retrieval. Other provider errors keep current behavior.

- [ ] **Step 5: Bound retrieval as one 8-second stage**

Add a private helper so search and corpus timestamp share one stage cap:

```python
async def _retrieve_question_evidence(
    payload: QuestionRequest,
    query_embedding: list[float] | None,
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

Call it through `budget.run("retrieval", ...)`. Map its `StageTimeoutError` to the fixed retrieval 503. Keep corpus-unready and generic search failure mappings distinct.

- [ ] **Step 6: Bound generation by 40 seconds and remaining budget**

```python
draft = await budget.run(
    "generation",
    lambda: _answerer().answer(payload, generation_hits),
    cap_seconds=settings.answer_timeout_seconds,
)
```

Map `StageTimeoutError("generation")` to the already-built evidence fallback: `fallback_reason=GENERATION_ERROR`, diagnostics status `timed_out`, then return it. Keep 402/429 as `BILLING_OR_QUOTA_ERROR`. The answerer's provider attempts still share one 40-second slice, so only fast transient provider failures can retry internally.

- [ ] **Step 7: Verify cancellation and fallback regressions**

Update direct `_answer_question` callers to pass a budget. Run:

`cd apps/api; uv run pytest tests/test_question_timeout_budget.py tests/test_ai_fallback.py tests/test_question_cancellation.py tests/test_nvidia_nim_answerer.py -q`

Expected: all selected tests PASS; user cancel still unregisters and yields 499; quota, embedding, no-evidence, grounding, and generation outcomes remain distinct.

Run: `cd apps/api; uv run ruff check app/main.py tests/test_question_timeout_budget.py tests/test_ai_fallback.py tests/test_question_cancellation.py`

Expected: exit code 0.

- [ ] **Step 8: Commit Task 2**

```bash
git add apps/api/app/main.py apps/api/tests/test_question_timeout_budget.py apps/api/tests/test_ai_fallback.py apps/api/tests/test_question_cancellation.py
git commit -m "feat(api): enforce stage-aware question deadlines"
```

---

### Task 3: Align Web retries with API outcomes

**Files:**
- Modify: `apps/web/lib/api-client.ts`
- Modify: `apps/web/lib/api-client-flow.test.ts`
- Modify: `apps/web/lib/generation-retry.ts`
- Modify: `apps/web/lib/generation-retry.test.ts`

**Interfaces:**
- Produces: `ApiError.status: number`; its message remains the existing safe user message.
- Produces: `GENERATION_ATTEMPT_TIMEOUT_MS = 55_000`, `GENERATION_OVERALL_TIMEOUT_MS = 170_000`, `GENERATION_CANCEL_TIMEOUT_MS = 1_000`.
- Preserves: `askQuestionWithRetry(...) -> Promise<QuestionResponse>` and `onAttemptChange` fresh-ID notification.

- [ ] **Step 1: Write failing typed HTTP error tests**

Add 503 and 429 cases to `api-client-flow.test.ts`:

```typescript
await expect(askQuestion(history.request)).rejects.toMatchObject({
  name: "ApiError",
  status: 503,
  message: "법령 검색을 일시적으로 사용할 수 없습니다.",
});
```

- [ ] **Step 2: Preserve HTTP status at the Web boundary**

```typescript
export class ApiError extends Error {
  constructor(message: string, readonly status: number) {
    super(message);
    this.name = "ApiError";
  }
}
```

Throw `new ApiError(message, response.status)` from `request()`. Do not attach response bodies, headers, tokens, or URLs.

- [ ] **Step 3: Write the full retry-matrix tests**

Cover all cases below with Vitest fake timers:

- first `generation_error` fallback followed by AI returns AI and uses a fresh ID;
- three `generation_error` responses return the third fallback;
- fallback followed by two retryable failures returns the stored fallback;
- HTTP 502/503/504 retry, while 400/401/402/409/429 stop immediately;
- `grounding_failed`, `no_evidence`, `embedding_error`, billing/quota fallbacks return immediately;
- attempt aborts at 55,000ms and the next starts even when `cancel()` never settles;
- cancel wait consumes at most 1,000ms;
- workflow stops by 170,000ms;
- user `outerSignal.abort()` stops without retry.

- [ ] **Step 4: Implement constants and retry classification**

```typescript
export const GENERATION_ATTEMPT_TIMEOUT_MS = 55_000;
export const GENERATION_MAX_ATTEMPTS = 3;
export const GENERATION_OVERALL_TIMEOUT_MS = 170_000;
export const GENERATION_CANCEL_TIMEOUT_MS = 1_000;

function isRetryableHttpError(error: unknown): error is ApiError {
  return error instanceof ApiError && [502, 503, 504].includes(error.status);
}

function isRetryableFallback(response: QuestionResponse): boolean {
  return response.mode === "search_only" && response.fallback_reason === "generation_error";
}
```

Replace the 59-second comment with the margin chain `API 52 < Web 55 < Vercel 60`.

- [ ] **Step 5: Retain fallback and bound cancel/overall time**

Inside `askQuestionWithRetry`, retain `latestFallback` on each retryable structured response. If another attempt is available, assign a fresh ID and continue. At attempt/overall exhaustion, return `latestFallback` if present; otherwise throw the last timeout/HTTP error.

Race `cancel(id)` against a 1,000ms timer and always settle. Before each attempt, use `Math.min(55_000, remainingOverallMs)` for its timer. Clear timers and abort listeners in `finally`. Cancellation failure or delay must not block a fresh request.

- [ ] **Step 6: Verify and commit Task 3**

Run: `pnpm.cmd --filter @law-rag/web test -- generation-retry.test.ts api-client-flow.test.ts`

Run: `pnpm.cmd --filter @law-rag/web typecheck`

Run: `pnpm.cmd --filter @law-rag/web lint`

Expected: every command exits 0.

```bash
git add apps/web/lib/api-client.ts apps/web/lib/api-client-flow.test.ts apps/web/lib/generation-retry.ts apps/web/lib/generation-retry.test.ts
git commit -m "feat(web): align generation retries with API deadlines"
```

---

### Task 4: Add privacy-safe timeout observability and decision docs

**Files:**
- Modify: `apps/api/app/observability.py`
- Modify: `apps/api/app/main.py`
- Modify: `apps/api/tests/test_security_boundaries.py`
- Modify: `ARCHITECTURE.md`
- Modify: `docs/RELIABILITY.md`
- Modify: `docs/design-docs/vercel-supabase-deployment.md`
- Modify: `docs/exec-plans/todo/0043-layperson-answer-contract-v2.md`

**Interfaces:**
- Produces: `emit_question_stage_timing(request_id, stage, outcome, elapsed_ms, remaining_ms)`.
- Produces: one safe JSON event per completed/timed-out stage.
- Consumes later: hosted verification filters by a known synthetic `request_id`.

- [ ] **Step 1: Write a failing observability privacy test**

Emit one timeout event and assert parsed JSON is exactly:

```python
{
    "request_id": "request-safe-id",
    "stage": "generation",
    "outcome": "timed_out",
    "elapsed_ms": 40000,
    "remaining_ms": 3000,
}
```

Assert a secret marker, question, exception message, document title, and evidence content are absent from `caplog.text`. Arbitrary stage/outcome strings must fail validation.

- [ ] **Step 2: Implement and wire timing events**

Add a Pydantic event with closed fields:

```python
stage: Literal["routing", "embedding", "retrieval", "generation", "request"]
outcome: Literal["succeeded", "failed", "timed_out", "degraded"]
elapsed_ms: int
remaining_ms: int
```

Use monotonic timestamps around each budgeted stage. Emit integer milliseconds only and never pass caught exceptions to the logger. Emit one final `request` event from the endpoint `finally` block, including early returns.

- [ ] **Step 3: Record the architecture and reliability decision**

Add a 2026-08-09 `ARCHITECTURE.md` decision recording:

- 60 seconds is the platform kill switch, not an application timeout;
- 52 seconds is shared across one API request;
- provider retries share the 40-second generation slice;
- 55 seconds starts a fresh server request and fresh budget;
- three means three total Web attempts, not one plus three retries;
- retained `generation_error` fallback prevents later timeout from erasing retrieved evidence.

In `docs/RELIABILITY.md`, add `52 < 55 < 60`, the 170-second UX cap, retry matrix, and safe log fields. Acceptance target: each hosted request returns by API 52 seconds or Web starts a retry by 55 seconds; no request ends only as Vercel 60-second 504.

In `docs/design-docs/vercel-supabase-deployment.md`, list the six non-secret API timeout variables, Web constants, and the instruction to remove stale Vercel overrides before comparison.

- [ ] **Step 4: Link answer-quality evaluation to this prerequisite**

In `0043-layperson-answer-contract-v2.md`, state that hosted D-10 v1/v2 comparisons begin only after 0045 passes; otherwise a platform 504 can be mistaken for answer-quality failure. Keep scopes separate: 0045 owns transport/retry timing, 0043 owns beginner-readable generation/evaluation.

- [ ] **Step 5: Verify and commit Task 4**

Run: `cd apps/api; uv run pytest tests/test_security_boundaries.py tests/test_question_timeout_budget.py -q`

Run: `uv run python scripts/check_docs.py`

Expected: tests and docs checks PASS; captured logs contain no question/evidence/error text.

```bash
git add apps/api/app/observability.py apps/api/app/main.py apps/api/tests/test_security_boundaries.py ARCHITECTURE.md docs/RELIABILITY.md docs/design-docs/vercel-supabase-deployment.md docs/exec-plans/todo/0043-layperson-answer-contract-v2.md
git commit -m "docs: record coordinated timeout reliability contract"
```

---

### Task 5: Full regression and approved hosted verification

**Files:**
- Modify during execution: `docs/exec-plans/active/0045-coordinated-question-timeout-budget.md` with dated evidence.
- Move after completion: the same file to `docs/exec-plans/completed/`.
- Modify: lifecycle `README.md` indexes under `todo/`, `active/`, and `completed/` as state changes require.

**Interfaces:**
- Consumes: Tasks 1-4.
- Produces: local verification evidence and, only after explicit approval, production evidence correlated by request ID.

- [ ] **Step 1: Run full local verification**

Run: `powershell -ExecutionPolicy Bypass -File scripts/verify.ps1`

Expected: format/lint/type checks, API tests, Web tests, and docs checks all PASS.

- [ ] **Step 2: Inspect diff and stale values**

Run: `git diff --check`

Expected: no whitespace errors.

Run: `rg -n "59_000|ANSWER_TIMEOUT_SECONDS=45|ROUTE_CLASSIFIER_TIMEOUT_SECONDS=20|EMBEDDING_TIMEOUT_SECONDS=30" apps docs`

Expected: no active configuration or current operating instruction retains superseded values; explicitly labeled historical evidence may remain.

Run: `git status --short --branch`

Expected: only planned files are modified, plus untouched pre-existing user changes.

- [ ] **Step 3: Stop at the external-change approval gate**

Report local results and request explicit approval before changing Vercel environment variables, deploying API/Web, pushing, or creating a PR. Without approval, leave the plan in `active/` with hosted verification unchecked.

- [ ] **Step 4: After approval, align Vercel settings and deploy**

Set only the non-secret timeout values 52, 3, 8, 5, 8, and 40 under Task 1 names. Preserve `maxDuration: 60`. Deploy API and Web from the same reviewed commit. Never print or copy NVIDIA/Supabase/auth secrets.

- [ ] **Step 5: Run one controlled hosted verification**

Submit D-10 first question `lay-energy-0201` through production Web with `answer_mode=terra`, `project_stage=planning`, and the supported `as_of_date`:

```text
태양광 발전소 허가를 준비하고 있는데, 어떤 허가나 신고가 필요한지 어떻게 구분하나요?
```

Record only attempt number, each `client_request_id`, HTTP status, elapsed seconds, mode, fallback reason, route, citation count, and safe stage timings. Do not place question/evidence text in Vercel operational logs.

Expected, in priority order:

1. AI completes on attempt 1 before 52 seconds.
2. API returns `generation_error` fallback before 52 seconds and attempt 2 or 3 returns AI.
3. All transient attempts fail, but Web displays the latest evidence-backed fallback by 170 seconds.

Fail if any Vercel 60-second timeout occurs, Web stops while an approved retry remains, an ID is reused, fallback is replaced by an empty error, or the workflow exceeds 170 seconds beyond explicitly recorded device scheduling noise.

- [ ] **Step 6: Record evidence and complete lifecycle**

Add dated local/hosted evidence. When every completion condition passes, move the file to `completed/`, update lifecycle indexes, run `uv run python scripts/check_docs.py`, then commit:

```bash
git add docs/exec-plans apps/api apps/web ARCHITECTURE.md docs/RELIABILITY.md docs/design-docs/vercel-supabase-deployment.md
git commit -m "docs: complete coordinated timeout rollout"
```

---

## Completion conditions

- API uses one 52-second budget and every external stage uses the smaller of its cap and remaining work budget.
- API completes or safely degrades before Vercel's 60-second kill switch in deterministic tests.
- Web starts a fresh ID at 55 seconds, attempts at most three times, and stops by 170 seconds.
- Web retries only the approved transient matrix and returns the latest `generation_error` fallback if no later AI response succeeds.
- User cancellation remains immediate and never becomes an automatic retry.
- Unit, integration, lint, typecheck, docs, and full repository verification pass.
- Timing logs distinguish routing, embedding, retrieval, generation, and platform delay without sensitive/free-text input.
- After separately approved deployment, the D-10 hosted check produces no Vercel 60-second 504 and safe request IDs reconstruct all attempts.

## Rollback

- Revert functional commits in reverse order; keep Vercel `maxDuration: 60` unchanged.
- Restore previous non-secret environment values only together with the corresponding code rollback so Web/API contracts do not diverge.
- If 40 seconds measurably increases valid-answer `generation_error`, keep the 52/55/60 safety margins and use stage timings to reduce pre-generation latency or seek approval for a longer-running architecture. Do not restore Web 59 seconds.

## Decision log

- 2026-08-09: 59-second Web timeout was rejected because it leaves only one second before Vercel's forced termination.
- 2026-08-09: 45 seconds is not assigned independently to each provider attempt; attempts share one generation slice inside the same Vercel invocation.
- 2026-08-09: Recommended balance is API 52 seconds, Web 55 seconds, Vercel 60 seconds, three total Web attempts, 170-second overall cap.
- 2026-08-09: Queue/background execution is excluded because current observed latency fits the simpler serverless request model and added infrastructure is not approved.
- 2026-08-09: `generation_error` is retryable and retained; `grounding_failed` and `no_evidence` are correctness outcomes and are not retried.
- 2026-08-09: Final whole-branch review found `embedding_timeout_seconds` (Task 1's literal field name) collides with 5 unrelated batch/offline embedding scripts that need the original 30s HTTP timeout, not the new 5s per-question budget value. Resolved (human-approved deviation from the plan's literal Task 1 field name) by splitting into `question_embedding_timeout_seconds` (5s, live request-budget path only) and restoring `embedding_timeout_seconds` (30s, batch/offline scripts + `_embedder()` factory's own client timeout). The non-secret Vercel timeout variable count is therefore seven, not six.

## Task 5 evidence — local verification (2026-08-09)

- Tasks 1-4 implemented via superpowers:subagent-driven-development: each task had an independent implementer + task-level reviewer (spec ✅ + quality Approved on all four; Task 4 required one fix round for a missing regression test, re-review confirmed addressed).
- Final whole-branch review (commit range 564a04e..7fec52c) found 0 Critical, 3 Important, 8 Minor findings. All 3 Important findings fixed in one fix wave (commit 2921354), scoped re-review confirmed all addressed with no new breakage. The 8 Minor findings were triaged by the reviewer as safe to defer (not blocking merge); see `.superpowers/sdd/0045-coordinated-question-timeout-budget/` review artifacts for full text.
- `scripts/verify.ps1` (Python unit tests for `packages/law-rag-core`, `apps/api`, `apps/collector`; ruff for all three; `scripts/check_docs.py`; web lint/typecheck/test/build) exits 0 at HEAD (5a3eb2c).
- `git diff --check`: no whitespace errors. `git status --short --branch`: clean, only plan-scoped commits since branch point.
- Stale-value grep (`59_000|ANSWER_TIMEOUT_SECONDS=45|ROUTE_CLASSIFIER_TIMEOUT_SECONDS=20|EMBEDDING_TIMEOUT_SECONDS=30`) has one expected match: `apps/api/.env.example:33 EMBEDDING_TIMEOUT_SECONDS=30`, which is the correct restored batch-script default from the embedding-timeout split above, not a superseded value.
- Hosted verification (Task 5 Steps 4-6) not yet run — awaiting explicit user approval to align Vercel env vars, deploy, and run the D-10 hosted check.
