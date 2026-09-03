> 작업 ID: F-008-A
> 상태: Todo
> 유형: Feature
> 보조 라벨: Reliability, UX
> 선행 조건: NVIDIA provider의 실제 동시 요청 한도와 Vercel Production 환경 변수 변경 권한 확인
> 다음 행동: busy 응답을 재시도하지 않는 고정 사용자 안내 계약의 실패 테스트부터 작성한다.
> 참고 범위:
> - `apps/api/app/settings.py` L45-L50 — V2 provider lease 예산과 슬롯 기본값
> - `apps/api/app/api/v2/sse.py` L71-L102 — lease admission 실패의 `503 system_busy` 경계
> - `apps/web/app/page.tsx` L552-L845 — 질문 제출 실패 처리와 red error banner

# F-008-A V2 Provider Capacity 3 Slots and Busy Notice Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Permit up to three concurrent Terra provider phases and show users a fixed Korean red-banner notice when provider admission is busy.

**Architecture:** Keep the global PostgreSQL lease and change only its default from one to three slots. Preserve the API's internal `system_busy` code, classify it in the web client before retry policy, do not automatically retry it, and use the existing accessible red error banner.

**Tech Stack:** FastAPI/Pydantic Settings/SQLAlchemy async, pytest; Next.js/React/TypeScript/Vitest.

**Spec:** User request recorded 2026-09-03: set V2 capacity to 3 and show `시스템이 바쁩니다. 잠시 후 다시 실행해 주세요.` in a red box when busy.

## Global Constraints

- Do not change lease uniqueness, expiry cleanup, or fail-closed behavior for database failures.
- Keep `system_busy` as internal API detail; it must never appear in the UI.
- A busy response does not automatically retry; the user resubmits later.
- Do not log question text, evidence, tokens, or database exception text.
- Do not change Vercel or NVIDIA Production settings without explicit user approval.

---

### Task 1: Set the V2 provider-slot default to three

**Files:**
- Modify: `apps/api/app/settings.py:45-50`
- Test: `apps/api/tests/test_settings.py`

**Interfaces:**
- Produces: `Settings().v2_provider_slots == 3`, retaining the allowed range `1..100`.

- [ ] **Step 1: Write the failing default-value test.**

```python
def test_v2_provider_slots_default_is_three(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("V2_PROVIDER_SLOTS", raising=False)
    assert Settings().v2_provider_slots == 3
```

- [ ] **Step 2: Prove it fails.**

Run: `uv run --directory apps/api pytest tests/test_settings.py -q`

Expected: the assertion fails because the current default is `1`.

- [ ] **Step 3: Make the smallest implementation change.**

```python
v2_provider_slots: int = Field(default=3, ge=1, le=100)
```

- [ ] **Step 4: Verify settings and lease behavior.**

Run: `uv run --directory apps/api pytest tests/test_settings.py tests/test_capacity_leases.py -q`

Expected: PASS; explicit one-slot test fixtures still work.

- [ ] **Step 5: Commit.**

```bash
git add apps/api/app/settings.py apps/api/tests/test_settings.py
git commit -m "feat(api): allow three concurrent v2 provider phases"
```

### Task 2: Classify busy responses and prevent their automatic retry

**Files:**
- Modify: `apps/web/lib/api-client.ts:21-25,107-130`
- Modify: `apps/web/lib/generation-retry.ts:34-100`
- Test: `apps/web/lib/api-client-flow.test.ts`
- Test: `apps/web/lib/generation-retry.test.ts`

**Interfaces:**
- Consumes: HTTP `503` body `{ "detail": "system_busy" }`.
- Produces: `ApiError` with `code: "system_busy"`; retry policy rethrows it without another request.

- [ ] **Step 1: Write failing classification and no-retry tests.**

```ts
await expect(askQuestion(input)).rejects.toMatchObject({
  name: "ApiError", status: 503, code: "system_busy",
});
await expect(askQuestionWithRetry(input, deps)).rejects.toMatchObject({ code: "system_busy" });
expect(deps.ask).toHaveBeenCalledTimes(1);
```

- [ ] **Step 2: Prove the tests fail.**

Run: `pnpm.cmd --dir apps/web vitest run lib/api-client-flow.test.ts lib/generation-retry.test.ts`

Expected: FAIL because `ApiError` has no code and all 503s are retryable.

- [ ] **Step 3: Add a closed error code and alter only busy retry eligibility.**

```ts
export type ApiErrorCode = "system_busy" | null;

export class ApiError extends Error {
  constructor(message: string, readonly status: number, readonly code: ApiErrorCode = null) {
    super(message);
    this.name = "ApiError";
  }
}

return error instanceof ApiError
  && error.code !== "system_busy"
  && [502, 503, 504].includes(error.status);
```

Map only the exact V2 detail `system_busy` to this code; keep all other messages and retry behavior unchanged.

- [ ] **Step 4: Verify focused client regressions.**

Run: `pnpm.cmd --dir apps/web vitest run lib/api-client-flow.test.ts lib/generation-retry.test.ts`

Expected: PASS; a busy response makes exactly one phase submission.

- [ ] **Step 5: Commit.**

```bash
git add apps/web/lib/api-client.ts apps/web/lib/generation-retry.ts apps/web/lib/api-client-flow.test.ts apps/web/lib/generation-retry.test.ts
git commit -m "fix(web): stop retrying busy v2 executions"
```

### Task 3: Show the fixed busy notice in the red error banner

**Files:**
- Modify: `apps/web/app/page.tsx:582-645,845`
- Test: existing page submission test or new `apps/web/app/page.test.tsx`

**Interfaces:**
- Consumes: `ApiError { status: 503, code: "system_busy" }`.
- Produces: `시스템이 바쁩니다. 잠시 후 다시 실행해 주세요.` in `.error-banner[role="alert"]`.

- [ ] **Step 1: Write a failing page-level busy notice test.**

```tsx
expect(await screen.findByRole("alert")).toHaveTextContent(
  "시스템이 바쁩니다. 잠시 후 다시 실행해 주세요.",
);
```

- [ ] **Step 2: Prove it fails with the raw machine code.**

Run: `pnpm.cmd --dir apps/web vitest run app/page.test.tsx`

Expected: FAIL because the current catch block renders `Error.message`.

- [ ] **Step 3: Map the typed error to fixed Korean copy before `setError`.**

```ts
const message = cause instanceof ApiError && cause.code === "system_busy"
  ? "시스템이 바쁩니다. 잠시 후 다시 실행해 주세요."
  : cause instanceof Error ? cause.message : "질문 처리 중 오류가 발생했습니다.";
setError(message);
```

Do not add a second notification: the existing error banner is red and has `role="alert"`.

- [ ] **Step 4: Verify the UI and transport regressions.**

Run: `pnpm.cmd --dir apps/web vitest run app/page.test.tsx lib/api-client-flow.test.ts lib/generation-retry.test.ts`

Expected: PASS; fixed copy appears, raw `system_busy` does not, and no retry occurs.

- [ ] **Step 5: Commit.**

```bash
git add apps/web/app/page.tsx apps/web/app/page.test.tsx
git commit -m "fix(web): show busy execution notice"
```

### Task 4: Verify graph artifacts and change Production only with approval

**Files:**
- Modify: feature-caused `graphify-out/` artifacts
- Modify: deployment documentation only if it names the old default

- [ ] **Step 1: Run repository verification.**

Run: `pnpm.cmd verify`

Expected: PASS.

- [ ] **Step 2: Refresh the codebase graph.**

Run: `graphify update .`

Expected: modified API and web relationships are reflected; unrelated dirty graph artifacts are not staged.

- [ ] **Step 3: Review and commit the feature artifacts.**

```bash
git diff --check
git status --short
git add graphify-out
git commit -m "chore: update capacity feature graph"
```

- [ ] **Step 4: After explicit approval, set Vercel Production `V2_PROVIDER_SLOTS` to `3`, deploy, and perform a hosted concurrent-request check.**

The external environment mutation is not authorized by this plan alone.

## Completion Conditions

- [ ] `Settings()` defaults to three slots and preserves safe overrides.
- [ ] Exact `503 system_busy` is not auto-retried and exposes no machine code to users.
- [ ] The existing red accessible banner shows exactly `시스템이 바쁩니다. 잠시 후 다시 실행해 주세요.`.
- [ ] API/web tests pass and graph artifacts are refreshed.
- [ ] Production capacity is set to three only after explicit approval and the provider limit is checked.
