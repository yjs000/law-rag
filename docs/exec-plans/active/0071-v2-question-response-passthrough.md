> 작업 ID: `B-005`
> 상태: `Picked Up`
> 유형: `Bug`
> 보조 라벨: `Reliability`, `UX`
> 선행 조건: [승인된 V2 질문 응답 표시 계약](../../design-docs/v2-question-response-presentation-contract.md)
> 다음 행동: Task 1의 Core SSE 표시 필드 회귀 테스트를 RED로 만든다.
> 참고 범위:
> - `docs/design-docs/v2-question-response-presentation-contract.md` L1-L151 — 승인된 표시·오류 소유권 계약
> - `apps/api/app/application/v2/phase_service.py` L310-L451 — Core 생성과 공개 summary event
> - `apps/web/app/page.tsx` L76-L706 — Core 임시 응답, 답변 표시, 질문 실행 실패 알림

# V2 Question Response Passthrough Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. Also use `picked-up-plan-runner` to keep exactly this plan active until every task is complete and `agent-operating-harness:execution-harness` for bounded execution evidence.

**Goal:** 질문 실행 화면이 모든 정상·실패 응답에서 백엔드가 공개한 답변 문구 또는 오류 코드만 표시하고 `no_results`를 자체 문구로 치환하지 않게 한다.

**Architecture:** FastAPI Core phase가 `summary`, `citations`, `scope`, `limitations`를 한 이벤트로 공개하고 Finalize의 `complete.response`가 최종 정본을 유지한다. Web은 전송 계층의 공개 표시 값만 추출한 뒤 작은 Core view-model과 별도 `AnswerView`에서 순서대로 배치하며 의미 있는 문구를 생성하지 않는다.

**Tech Stack:** Python 3.14, FastAPI, Pydantic, pytest, Next.js 16, React 19, TypeScript 5.9, Vitest 4.

**Spec:** `docs/design-docs/v2-question-response-presentation-contract.md`

## Global Constraints

- 적용 범위는 V2 질문 실행 화면의 정상·실패 응답뿐이며 인증·이력·계정·내보내기 화면은 바꾸지 않는다.
- `result_status`, `route`, `action`은 사용자 문구 선택이나 합성에 사용하지 않는다.
- 실제 검색 무결과는 백엔드 summary를 그대로 표시하고 Web의 “검색 결과가 없습니다” 문구를 제거한다.
- HTTP는 백엔드 `message`, 문자열 `detail`, 코드 순서로, SSE는 `message` 또는 `reason_code`를 변형 없이 표시한다.
- `system_busy`, 모드 전환 안내, 진행 중 `…`, 버튼·접근성 레이블만 Web 소유 문구로 유지한다.
- Core 표시 순서는 `summary → citations → scope → limitations → …`, Finalize 이후 상세 순서는 `sections → checklist`다.
- `SafeText`, citation 필터링, retry/idempotency/cancellation/capability는 유지한다.
- Web attempt 55,000ms, overall retry 170,000ms, phase wait 57,000ms, 최대 reconnect 3회와 백엔드 provider 55초/phase 57초 예산을 변경하지 않는다.
- 질문·응답 전문, 검색 원문, 사용자 식별자, capability, 인증정보를 로그에 추가하지 않는다.

## File Structure and Change Budget

| File | Responsibility | Estimated delta |
| --- | --- | ---: |
| `apps/api/app/application/v2/phase_service.py` | Core 공개 필드 보존 | +25/-5 lines |
| `apps/api/tests/test_v2_question_executions.py` | Core SSE 계약 회귀 | +45 lines |
| `apps/web/lib/backend-display-message.ts` | 백엔드 공개 표시 값 추출 | new, 35-45 lines |
| `apps/web/lib/backend-display-message.test.ts` | HTTP/SSE payload 추출 회귀 | new, 50-65 lines |
| `apps/web/lib/api-client.ts` | V2 HTTP 오류를 `ApiError.publicMessage`로 전달 | +20/-10 lines |
| `apps/web/lib/api-client-flow.test.ts` | message/detail/code-only HTTP 회귀 | +45 lines |
| `apps/web/lib/v2-execution.ts` | SSE error/cancelled 공개 값 전달 | +20/-5 lines |
| `apps/web/lib/v2-execution.test.ts` | SSE message/reason_code 회귀 | +45 lines |
| `apps/web/lib/live-core-response.ts` | Core event를 문구 합성 없이 view-model로 검증 | new, 40-50 lines |
| `apps/web/lib/live-core-response.test.ts` | Core 필드 보존·구버전 경계 | new, 55-70 lines |
| `apps/web/app/answer-view.tsx` | 백엔드 필드 순서 렌더링 | new, 85-100 lines |
| `apps/web/app/answer-view.test.tsx` | no_results·표시 순서·SafeText 회귀 | new, 75-95 lines |
| `apps/web/app/page.tsx` | 새 Core parser/View 연결, 공개 오류만 알림 | net -70 to -40 lines |
| `apps/web/lib/contracts.ts` | 백엔드 route/action 타입 보존 | +15 lines |
| `apps/web/lib/empty-result.ts` | 프론트 의미 치환 제거 | delete, 35 lines 이하 |
| `apps/web/lib/empty-result.test.ts` | 폐기된 치환 계약 제거 | delete, 90 lines 이하 |

각 구현 태스크는 프로덕션 파일당 약 100줄 이하의 diff를 목표로 한다. 범위를 넘기면 다음 태스크로 넘기지 말고 같은 책임 안에서 helper 파일을 하나 더 분리한다.

---

### Task 1: Backend Core Presentation Payload

**Files:**
- Modify: `apps/api/app/application/v2/phase_service.py:310-451`
- Test: `apps/api/tests/test_v2_question_executions.py:1060-1088`

**Change budget:** production 20-30 lines, test 35-45 lines.

**Interfaces:**
- Consumes: existing `QuestionResponse.scope`, `QuestionResponse.limitations`, `safe_answer_limitations(action)`.
- Produces: Core `summary` event payload `{ summary: str, citations: list[dict], scope: str, limitations: list[str] }`.
- Preserves: public `core_from_frozen_evidence(execution) -> tuple[Any, list[Any]]` compatibility seam.

- [ ] **Step 1: Write the failing Core SSE contract test**

Add assertions that decode the `summary` and `complete` frames instead of only searching their event names:

```python
summary_frame = next(
    frame for frame in core.text.split("\n\n") if frame.startswith("event: summary\n")
)
summary_payload = json.loads(summary_frame.removeprefix("event: summary\ndata: "))
complete_frame = next(
    frame for frame in finalized.text.split("\n\n") if frame.startswith("event: complete\n")
)
final_response = json.loads(complete_frame.removeprefix("event: complete\ndata: "))[
    "response"
]
assert set(summary_payload) == {"summary", "citations", "scope", "limitations"}
assert summary_payload["summary"] == final_response["summary"]
assert summary_payload["citations"] == final_response["citations"]
assert summary_payload["scope"] == final_response["scope"]
assert summary_payload["limitations"] == final_response["limitations"]
```

- [ ] **Step 2: Run the focused API test and verify RED**

Run: `./scripts/run_python.ps1 -m pytest apps/api/tests/test_v2_question_executions.py -k "core and replay" -q`

Expected: FAIL because the summary event lacks `scope` and `limitations`.

- [ ] **Step 3: Preserve presentation fields in the private Core result**

Extend `_core_result_from_frozen_evidence` internally to return scope and limitations alongside the draft and citations. Every deterministic branch uses its already-created `QuestionResponse`; the generated branch uses the already-created search fallback scope plus safe backend limitations:

```python
return draft, citations_for_hits(generation_hits), fallback.scope, safe_answer_limitations(
    draft.action
), False
```

Keep `core_from_frozen_evidence()` returning only `(core, citations)` by discarding the extra private values there.

- [ ] **Step 4: Publish all four Core display fields**

```python
payload={
    "summary": core.summary,
    "citations": [citation.model_dump(mode="json") for citation in citations],
    "scope": scope,
    "limitations": limitations,
},
```

Do not add response text logging or change the stored `verified_core` contract.

- [ ] **Step 5: Run focused API tests and commit**

Run: `./scripts/run_python.ps1 -m pytest apps/api/tests/test_v2_question_executions.py apps/api/tests/test_clarification_answering.py -q`

Expected: PASS, including clarification/no-results Core payload and replay equality.

```powershell
git add apps/api/app/application/v2/phase_service.py apps/api/tests/test_v2_question_executions.py
git commit -m "fix(api): publish core presentation fields"
```

### Task 2: V2 HTTP Public Message Passthrough

**Files:**
- Create: `apps/web/lib/backend-display-message.ts`
- Create: `apps/web/lib/backend-display-message.test.ts`
- Modify: `apps/web/lib/api-client.ts:21-32,113-138`
- Test: `apps/web/lib/api-client-flow.test.ts:150-190`

**Change budget:** new helper 45 lines, production integration 20 lines, tests 90-105 lines total.

**Interfaces:**
- Produces: `backendDisplayMessage(payload: unknown): string | null`.
- Produces: `ApiError.publicMessage: string | null`; `ApiError.code: string | null`.
- Consumes: raw `V2ExecutionHttpError.detail` response body only in `askQuestion()`.

- [ ] **Step 1: Write table-driven extraction tests**

```typescript
it.each([
  [{ message: "백엔드 메시지" }, "백엔드 메시지"],
  [{ detail: { message: "상세 메시지" } }, "상세 메시지"],
  [{ detail: "문자열 상세" }, "문자열 상세"],
  [{ detail: { code: "invalid_phase" } }, "invalid_phase"],
  [{ code: "invalid_request" }, "invalid_request"],
  [{ detail: {} }, null],
])("extracts only a backend-owned display value", (payload, expected) => {
  expect(backendDisplayMessage(payload)).toBe(expected);
});
```

- [ ] **Step 2: Run helper tests and verify RED**

Run: `pnpm.cmd --dir apps/web vitest run lib/backend-display-message.test.ts`

Expected: FAIL because the module does not exist.

- [ ] **Step 3: Implement the exact precedence without fallback copy**

```typescript
export function backendDisplayMessage(payload: unknown): string | null {
  if (typeof payload === "string") return payload;
  if (!isRecord(payload)) return null;
  if (typeof payload.message === "string") return payload.message;
  const detail = payload.detail;
  if (isRecord(detail) && typeof detail.message === "string") return detail.message;
  if (typeof detail === "string") return detail;
  if (isRecord(detail) && typeof detail.code === "string") return detail.code;
  if (typeof payload.reason_code === "string") return payload.reason_code;
  return typeof payload.code === "string" ? payload.code : null;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}
```

Do not trim, translate, prefix, or append punctuation to the selected string.

- [ ] **Step 4: Make `ApiError` separate internal diagnostics from user display**

```typescript
export class ApiError extends Error {
  constructor(
    readonly publicMessage: string | null,
    readonly status: number,
    readonly code: string | null = null,
  ) {
    super(publicMessage ?? `HTTP ${status}`);
    this.name = "ApiError";
  }
}
```

In `askQuestion()`, call `backendDisplayMessage(error.detail)` and derive `system_busy` only from the raw public code/detail. Leave the generic `request<T>()` used by out-of-scope account/history screens unchanged.

- [ ] **Step 5: Add HTTP message/detail/code-only assertions and run GREEN**

Run: `pnpm.cmd --dir apps/web vitest run lib/backend-display-message.test.ts lib/api-client-flow.test.ts`

Expected: PASS; a payload with no display value yields `publicMessage: null` and never “요청을 처리하지 못했습니다.” in the V2 question path.

- [ ] **Step 6: Commit**

```powershell
git add apps/web/lib/backend-display-message.ts apps/web/lib/backend-display-message.test.ts apps/web/lib/api-client.ts apps/web/lib/api-client-flow.test.ts
git commit -m "fix(web): preserve v2 http error messages"
```

### Task 3: SSE Terminal Error Passthrough

**Files:**
- Modify: `apps/web/lib/v2-execution.ts:24-97`
- Test: `apps/web/lib/v2-execution.test.ts:1-115`
- Modify: `apps/web/lib/api-client.ts:113-138`

**Change budget:** production 20-30 lines, tests 40-50 lines.

**Interfaces:**
- Consumes: `backendDisplayMessage(event.data)` from Task 2.
- Produces: `V2ExecutionEventError.publicMessage: string | null`, `eventType: "error" | "cancelled"`.
- Produces through `askQuestion()`: `ApiError` with the same public message or code.

- [ ] **Step 1: Write failing SSE error tests**

```typescript
it.each([
  ['event: error\ndata: {"message":"상세 생성을 완료하지 못했습니다."}\n\n', "상세 생성을 완료하지 못했습니다."],
  ['event: error\ndata: {"reason_code":"phase_not_ready"}\n\n', "phase_not_ready"],
])("preserves a terminal SSE display value", async (frame, expected) => {
  await expect(runWithCoreFrame(frame)).rejects.toMatchObject({ publicMessage: expected });
});

async function runWithCoreFrame(frame: string) {
  const fetch = async (url: string) => url.endsWith("/v2/question-executions")
    ? Response.json({ execution_id: "exec-1", next_action: "generate_core" })
    : new Response(frame);
  return runV2Execution(
    { question: "질문", as_of_date: "2026-09-15", project_stage: "planning" },
    {
      fetch: fetch as typeof globalThis.fetch,
      apiUrl: "http://api",
      headers: {},
      idempotencyKey: () => "key",
    },
  );
}
```

Also assert `event: cancelled` with `{}` produces `publicMessage: null`.
Add `event: cancelled` with `{"message":"실행이 취소되었습니다."}` and assert that exact message is preserved.

- [ ] **Step 2: Run the focused test and verify RED**

Run: `pnpm.cmd --dir apps/web vitest run lib/v2-execution.test.ts`

Expected: FAIL because the current code throws “답변 실행을 완료하지 못했습니다.”.

- [ ] **Step 3: Add a typed terminal event error**

```typescript
export class V2ExecutionEventError extends Error {
  constructor(
    readonly publicMessage: string | null,
    readonly eventType: "error" | "cancelled",
  ) {
    super(publicMessage ?? `SSE ${eventType}`);
    this.name = "V2ExecutionEventError";
  }
}
```

Replace the generic terminal throw with this error and the Task 2 extractor. Convert it to `ApiError` inside `askQuestion()` without altering `publicMessage`.

- [ ] **Step 4: Run V2 execution and API client tests**

Run: `pnpm.cmd --dir apps/web vitest run lib/v2-execution.test.ts lib/api-client-flow.test.ts`

Expected: PASS for message, reason code, cancelled-without-copy, reconnect, abort, and busy cases.

- [ ] **Step 5: Commit**

```powershell
git add apps/web/lib/v2-execution.ts apps/web/lib/v2-execution.test.ts apps/web/lib/api-client.ts
git commit -m "fix(web): preserve v2 sse terminal messages"
```

### Task 4: Core Event View Model Without Copy Synthesis

**Files:**
- Create: `apps/web/lib/live-core-response.ts`
- Create: `apps/web/lib/live-core-response.test.ts`
- Modify: `apps/web/lib/contracts.ts:18-34`
- Modify: `apps/web/app/page.tsx:76-104,668-675`

**Change budget:** new parser 50 lines, tests 60-70 lines, page net -20 lines, contracts 15 lines.

**Interfaces:**
- Produces: `liveCoreResponse(requestId: string, data: Record<string, unknown>): QuestionResponse | null`.
- Preserves: exact backend `summary`, `scope`, `limitations`, validated citations; structural defaults are only `sections: []`, `checklist: []`, missing `scope: ""`, and missing `limitations: []` for old events.
- Adds Web contract fields: backend-matching optional `action` and `route` literal unions.

- [ ] **Step 1: Write failing Core parser tests**

```typescript
expect(liveCoreResponse("request-1", {
  summary: "백엔드 요약 원문",
  citations: [citation],
  scope: "백엔드 범위 원문",
  limitations: ["백엔드 한계 원문"],
})).toMatchObject({
  summary: "백엔드 요약 원문",
  citations: [citation],
  scope: "백엔드 범위 원문",
  limitations: ["백엔드 한계 원문"],
  sections: [],
  checklist: [],
});
```

Add cases for an old event missing scope/limitations, invalid citations, and blank/missing summary. Assert no Korean fallback sentence is introduced.

- [ ] **Step 2: Run parser tests and verify RED**

Run: `pnpm.cmd --dir apps/web vitest run lib/live-core-response.test.ts`

Expected: FAIL because the module does not exist.

- [ ] **Step 3: Implement strict structural parsing**

Move `coreCitations()` and `liveCoreResponse()` out of `page.tsx`. Preserve strings byte-for-byte; use empty structural values only for backward compatibility:

```typescript
// apps/web/lib/contracts.ts
action?: "fully_answerable" | "partially_answerable" | "clarification_required" | "unanswerable" | null;
route?: "legal_search" | "clarification_required" | "realtime_required" | "external_document_required" | "routing_unavailable" | null;

// apps/web/lib/live-core-response.ts
return {
  request_id: requestId,
  mode: "ai",
  summary: data.summary,
  scope: typeof data.scope === "string" ? data.scope : "",
  sections: [],
  checklist: [],
  citations: coreCitations(data.citations),
  limitations: stringArray(data.limitations),
};

function stringArray(value: unknown): string[] {
  return Array.isArray(value)
    ? value.filter((item): item is string => typeof item === "string")
    : [];
}

function coreCitations(value: unknown): QuestionResponse["citations"] {
  if (!Array.isArray(value)) return [];
  return value.filter((citation): citation is QuestionResponse["citations"][number] => (
    typeof citation === "object" && citation !== null
    && typeof (citation as { id?: unknown }).id === "string"
    && typeof (citation as { document_title?: unknown }).document_title === "string"
    && typeof (citation as { version_label?: unknown }).version_label === "string"
    && typeof (citation as { path?: unknown }).path === "string"
    && typeof (citation as { quote?: unknown }).quote === "string"
    && typeof (citation as { source_url?: unknown }).source_url === "string"
  ));
}
```

- [ ] **Step 4: Connect the parser to the summary event**

```typescript
if (activeRequest.current?.id !== requestId || event.event !== "summary") return;
const core = liveCoreResponse(requestId, event.data);
if (!core) return;
setResult(core);
setActiveChat((current) => applyLiveCoreSummary(current, requestId, core));
```

- [ ] **Step 5: Run parser, chat-state, and page tests; commit**

Run: `pnpm.cmd --dir apps/web vitest run lib/live-core-response.test.ts lib/chat-state.test.ts app/page.test.tsx`

Expected: PASS with no synthesized Core scope or limitations.

```powershell
git add apps/web/lib/live-core-response.ts apps/web/lib/live-core-response.test.ts apps/web/lib/contracts.ts apps/web/app/page.tsx
git commit -m "refactor(web): isolate v2 core response parsing"
```

### Task 5: Passthrough Answer Rendering and Alert Policy

**Files:**
- Create: `apps/web/app/answer-view.tsx`
- Create: `apps/web/app/answer-view.test.tsx`
- Modify: `apps/web/app/page.tsx:331-369,697-706,900-915`
- Delete: `apps/web/lib/empty-result.ts`
- Delete: `apps/web/lib/empty-result.test.ts`

**Change budget:** new component 85-100 lines, tests 75-95 lines, page net -80 to -50 lines, deleted legacy code at most 125 lines.

**Interfaces:**
- Consumes: `QuestionResponse`, filtered citations, existing `SafeText` and `CitationCard`.
- Produces: `AnswerView` with `pendingDetail: boolean`; no `getEmptyResultMessage()` dependency.
- Alert policy: `system_busy` retains Web copy; other `ApiError` values display `publicMessage`; absent backend display values create no alert text.

- [ ] **Step 1: Write failing render tests for no-results passthrough and order**

```typescript
const citation = {
  id: "C1",
  document_title: "원자력안전법",
  version_label: "2026-09-15 현행",
  path: "제1조",
  quote: "백엔드 인용 원문",
  source_url: "https://www.law.go.kr/법령/원자력안전법",
};
const baseResponse: QuestionResponse = {
  mode: "ai",
  summary: "백엔드 요약",
  scope: "백엔드 범위",
  sections: [],
  checklist: [],
  citations: [citation],
  limitations: ["백엔드 한계"],
};
const requiredProps = {
  asOf: "2026-09-15",
  documentKinds: new Set<DocumentKind>(["law", "decree", "rule", "administrative_rule"]),
  exportFormat: "md" as const,
  exporting: false,
  messageId: "message-1",
  onCitation: vi.fn(),
  onExport: vi.fn(),
  onExportFormat: vi.fn(),
  question: "집앞에 원전을 설치하고싶어.",
  selectedCitationId: null,
};
const html = renderToStaticMarkup(<AnswerView
  {...requiredProps}
  pendingDetail
  response={{
    ...baseResponse,
    result_status: "no_results",
    summary: "정확한 절차를 확인하려면 추가 정보가 필요합니다.",
    scope: "라우팅: clarification_required (검색 미실행)",
    limitations: ["이 서비스는 법률 자문을 대체하지 않습니다."],
  }}
/>);

expect(html).toContain("정확한 절차를 확인하려면 추가 정보가 필요합니다.");
expect(html).not.toContain("기준일에 유효한 MVP 법령 범위");
expect(html.indexOf("summary")).toBeLessThan(html.indexOf("sources"));
expect(html.indexOf("sources")).toBeLessThan(html.indexOf("limitations"));
expect(html.indexOf("limitations")).toBeLessThan(html.indexOf("detail-progress"));
```

Add a finalized response case proving `sections` and `checklist` follow the backend-owned header fields and the ellipsis disappears.

- [ ] **Step 2: Run render tests and verify RED**

Run: `pnpm.cmd --dir apps/web vitest run app/answer-view.test.tsx`

Expected: FAIL because `AnswerView` is still private to `page.tsx` and performs empty-result substitution.

- [ ] **Step 3: Extract and reorder `AnswerView`**

Render exactly this semantic order, omitting empty scope/limitations sections rather than inventing content:

```tsx
<p className="summary"><SafeText>{response.summary}</SafeText></p>
{citations.length > 0 && (
  <section className="sources">
    <h2>원문 근거 <span>{citations.length}건</span></h2>
    {citations.map((citation) => (
      <CitationCard
        citation={citation}
        htmlId={`citation-${messageId}-${citation.id}`}
        key={citation.id}
        open={selectedCitationId === `${messageId}:${citation.id}`}
      />
    ))}
  </section>
)}
{(response.scope || response.limitations.length > 0) && (
  <section className="limitations">
    <h2>범위와 한계</h2>
    {response.scope && <p><SafeText>{response.scope}</SafeText></p>}
    {response.limitations.map((item, index) => (
      <p key={`${item}-${index}`}>· <SafeText>{item}</SafeText></p>
    ))}
  </section>
)}
{pendingDetail && <p aria-label="상세 답변 생성 중" className="detail-progress">…</p>}
{response.sections.map((section, index) => (
  <section className="claim" key={`${section.claim}-${index}`}>
    <h2><SafeText>{section.claim}</SafeText></h2>
    <p><SafeText>{section.explanation}</SafeText></p>
    <div className="citation-links">
      {section.citation_ids.map((id) => (
        <button
          className={selectedCitationId === `${messageId}:${id}` ? "selected" : ""}
          key={id}
          onClick={() => onCitation(messageId, response, id)}
        >{id} 원문</button>
      ))}
    </div>
  </section>
))}
{response.checklist.length > 0 && (
  <section className="checklist">
    <div className="section-title-row">
      <h2>확인 체크리스트</h2>
      <div className="export-controls">
        <select aria-label="내보내기 형식" value={exportFormat} onChange={(event) => onExportFormat(event.target.value as ExportFormat)}>
          <option value="md">Markdown</option><option value="csv">CSV</option><option value="pdf">PDF</option>
        </select>
        <button disabled={exporting} onClick={() => onExport(response, question, asOf)}>{exporting ? "생성 중" : "내보내기"}</button>
      </div>
    </div>
    {response.checklist.map((item, index) => (
      <div className="check-item" key={`${item.label}-${index}`}>
        <span aria-hidden="true">□</span>
        <p>
          <SafeText>{item.label}</SafeText>
          {item.citation_ids.map((id) => (
            <button className="inline-cite" key={id} onClick={() => onCitation(messageId, response, id)}>{id}</button>
          ))}
        </p>
      </div>
    ))}
  </section>
)}
```

Delete the empty-result import, component branch, helper, and its obsolete tests. Keep citation filtering and `SafeText` unchanged.

- [ ] **Step 4: Apply the question-path alert policy**

```typescript
const message = cause instanceof ApiError && cause.code === "system_busy"
  ? "시스템이 바쁩니다. 잠시 후 다시 실행해 주세요."
  : cause instanceof ApiError
    ? cause.publicMessage
    : null;
if (message) {
  setActiveChat((current) => failPendingTurn(current, requestId, message));
  setError(message);
} else {
  setActiveChat((current) => stopPendingTurn(current, requestId));
}
```

Do not display `Error.message`, “연결 오류”, or a generic Korean fallback for transport/protocol failures.

- [ ] **Step 5: Run the complete Web suite and build**

Run: `pnpm.cmd --dir apps/web test`

Run: `pnpm.cmd --dir apps/web lint`

Run: `pnpm.cmd --dir apps/web typecheck`

Run: `pnpm.cmd --dir apps/web build`

Expected: all commands exit 0; busy and mode-transition tests retain their existing copy.

- [ ] **Step 6: Audit forbidden frontend copy and commit**

Run: `rg -n "기준일에 유효한 MVP 법령 범위|요청을 처리하지 못했습니다|답변 실행을 완료하지 못했습니다|연결 오류|getEmptyResultMessage" apps/web/app/page.tsx apps/web/app/answer-view.tsx apps/web/lib`

Expected: no matches in the V2 question execution path. A generic message in the out-of-scope `request<T>()` is allowed only if its callers remain account/history operations.

```powershell
git add apps/web/app/answer-view.tsx apps/web/app/answer-view.test.tsx apps/web/app/page.tsx apps/web/lib/empty-result.ts apps/web/lib/empty-result.test.ts
git commit -m "fix(web): render backend question responses unchanged"
```

### Task 6: Whole-Flow Verification and Plan Closure

**Files:**
- Modify: `docs/exec-plans/active/0071-v2-question-response-passthrough.md`
- Modify: `docs/CURRENT_STATE.md:7-15`
- Generated: `docs/ROADMAP.md`

**Change budget:** documentation 15-25 lines plus generated roadmap delta.

**Interfaces:**
- Consumes: Tasks 1-5 committed results.
- Produces: latest full verification evidence and a `Done` plan moved to `docs/exec-plans/completed/`.

- [ ] **Step 1: Run focused cross-stack regression**

Run: `./scripts/run_python.ps1 -m pytest apps/api/tests/test_v2_question_executions.py apps/api/tests/test_clarification_answering.py -q`

Run: `pnpm.cmd --dir apps/web vitest run lib/backend-display-message.test.ts lib/v2-execution.test.ts lib/api-client-flow.test.ts lib/live-core-response.test.ts app/answer-view.test.tsx app/page.test.tsx`

Expected: all focused tests PASS.

- [ ] **Step 2: Run repository verification**

Run: `./scripts/verify.ps1`

Expected: format, lint, type, unit, integration, and documentation checks exit 0. If `tmp_path` fails with access denied, rerun this command once with platform runtime escalation as required by `AGENTS.md`.

- [ ] **Step 3: Review the complete branch diff**

Run: `git diff origin/main...HEAD -- apps/api apps/web docs/design-docs docs/exec-plans docs/CURRENT_STATE.md docs/ROADMAP.md`

Confirm no secrets, response bodies, unrelated Graphify output, timeout changes, auth/history/account/export behavior, or new frontend legal/error copy entered the branch.

- [ ] **Step 4: Record completion and transition the authoritative plan**

Append a short result section containing the exact test commands and outcomes, set header state to `Done`, set next action to “완료되어 잔여 작업이 없습니다.”, move the file to `docs/exec-plans/completed/0071-v2-question-response-passthrough.md`, and update `docs/CURRENT_STATE.md` to point to the completed work.

Run in order:

```powershell
./scripts/run_python.ps1 scripts/render_roadmap.py
./scripts/run_python.ps1 scripts/check_roadmap.py
```

Expected: roadmap renderer and checker PASS with no `Picked Up` item remaining.

- [ ] **Step 5: Commit closure metadata**

```powershell
git add docs/exec-plans/completed/0071-v2-question-response-passthrough.md docs/CURRENT_STATE.md docs/ROADMAP.md
git commit -m "docs: complete v2 response passthrough plan"
```
