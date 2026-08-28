import type { QuestionInput, QuestionResponse } from "./contracts";

export type V2NextAction = "generate_core" | "generate_detail" | "repair_core" | "complete";

type PreparedExecution = {
  execution_id: string;
  next_action: V2NextAction;
};

type SseEvent = { event: string; data: Record<string, unknown> };

export type V2ExecutionDependencies = {
  fetch: typeof fetch;
  apiUrl: string;
  headers: HeadersInit;
  idempotencyKey: () => string;
};

export class V2ExecutionHttpError extends Error {
  constructor(readonly status: number, readonly detail: unknown) {
    super(`HTTP ${status}`);
  }
}

const KNOWN_ACTIONS = new Set<V2NextAction>([
  "generate_core",
  "generate_detail",
  "repair_core",
  "complete",
]);

export async function runV2Execution(
  input: QuestionInput,
  deps: V2ExecutionDependencies,
  signal?: AbortSignal,
): Promise<QuestionResponse> {
  const prepared = await json<PreparedExecution>(
    deps.fetch(`${deps.apiUrl}/v2/question-executions`, {
      method: "POST",
      headers: { ...deps.headers, "Content-Type": "application/json", "Idempotency-Key": deps.idempotencyKey() },
      body: JSON.stringify(input),
      signal,
    }),
  );
  let action = prepared.next_action;
  while (action !== "complete") {
    if (!KNOWN_ACTIONS.has(action)) throw new Error("알 수 없는 실행 다음 단계입니다.");
    const phase = action === "generate_core" ? "core" : "finalize";
    const events = await stream(
      deps.fetch(`${deps.apiUrl}/v2/question-executions/${encodeURIComponent(prepared.execution_id)}/${phase}`, {
        method: "POST",
        headers: deps.headers,
        signal,
      }),
    );
    for (const event of events) {
      if (event.event === "complete") return event.data.response as QuestionResponse;
      if (event.event === "error") throw new Error("답변 실행을 완료하지 못했습니다.");
      if (event.event === "phase_complete") {
        const candidate = event.data.next_action;
        if (typeof candidate !== "string" || !KNOWN_ACTIONS.has(candidate as V2NextAction)) {
          throw new Error("알 수 없는 실행 다음 단계입니다.");
        }
        action = candidate as V2NextAction;
      }
    }
  }
  throw new Error("최종 응답 event가 없습니다.");
}

async function json<T>(response: Promise<Response>): Promise<T> {
  const resolved = await response;
  if (!resolved.ok) throw new V2ExecutionHttpError(resolved.status, await resolved.json().catch(() => null));
  return resolved.json() as Promise<T>;
}

async function stream(response: Promise<Response>): Promise<SseEvent[]> {
  const resolved = await response;
  if (!resolved.ok) throw new V2ExecutionHttpError(resolved.status, await resolved.json().catch(() => null));
  const text = await resolved.text();
  return text.split("\n\n").flatMap((frame) => {
    const event = /^event: (.+)$/m.exec(frame)?.[1];
    const data = /^data: (.+)$/m.exec(frame)?.[1];
    if (!event || !data) return [];
    return [{ event, data: JSON.parse(data) as Record<string, unknown> }];
  });
}
