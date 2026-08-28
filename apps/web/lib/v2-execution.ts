import type { QuestionInput, QuestionResponse } from "./contracts";

export type V2NextAction = "generate_core" | "generate_detail" | "repair_core" | "complete";

type PreparedExecution = {
  execution_id: string;
  next_action: V2NextAction;
  execution_capability?: string;
};

type SseEvent = { event: string; data: Record<string, unknown> };

export type V2ExecutionDependencies = {
  fetch: typeof fetch;
  apiUrl: string;
  headers: HeadersInit;
  idempotencyKey: () => string;
  reconnectDelayMs?: (attempt: number) => number;
  maxReconnects?: number;
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
const DEFAULT_MAX_RECONNECTS = 3;

export async function runV2Execution(
  input: QuestionInput,
  deps: V2ExecutionDependencies,
  signal?: AbortSignal,
): Promise<QuestionResponse> {
  const prepared = await json<PreparedExecution>(
    deps.fetch(`${deps.apiUrl}/v2/question-executions`, {
      method: "POST",
      headers: {
        ...deps.headers,
        "Content-Type": "application/json",
        "Idempotency-Key": deps.idempotencyKey(),
      },
      body: JSON.stringify(input),
      signal,
    }),
  );
  if (!isPreparedExecution(prepared)) throw new Error("실행 준비 응답이 올바르지 않습니다.");

  try {
    return await followExecution(prepared, deps, signal);
  } catch (error) {
    if (signal?.aborted) await cancelExecution(prepared, deps);
    throw error;
  }
}

async function followExecution(
  prepared: PreparedExecution,
  deps: V2ExecutionDependencies,
  signal?: AbortSignal,
): Promise<QuestionResponse> {
  let action = prepared.next_action;
  while (action !== "complete") {
    if (!KNOWN_ACTIONS.has(action)) throw new Error("알 수 없는 실행 다음 단계입니다.");
    const phase = action === "generate_core" ? "core" : "finalize";
    const events = await reconnectablePhase(prepared, phase, deps, signal);
    let advanced = false;
    for (const event of events) {
      if (event.event === "complete") {
        if (!isQuestionResponse(event.data.response)) {
          throw new Error("최종 응답 event가 올바르지 않습니다.");
        }
        return event.data.response;
      }
      if (event.event === "error" || event.event === "cancelled") {
        throw new Error("답변 실행을 완료하지 못했습니다.");
      }
      if (event.event === "phase_complete") {
        const candidate = event.data.next_action;
        if (typeof candidate !== "string" || !KNOWN_ACTIONS.has(candidate as V2NextAction)) {
          throw new Error("알 수 없는 실행 다음 단계입니다.");
        }
        action = candidate as V2NextAction;
        advanced = true;
      }
    }
    if (!advanced) throw new Error("실행 phase가 완료되지 않았습니다.");
  }
  throw new Error("최종 응답 event가 없습니다.");
}

async function reconnectablePhase(
  prepared: PreparedExecution,
  phase: "core" | "finalize",
  deps: V2ExecutionDependencies,
  signal?: AbortSignal,
): Promise<SseEvent[]> {
  const maxReconnects = deps.maxReconnects ?? DEFAULT_MAX_RECONNECTS;
  for (let attempt = 0; attempt <= maxReconnects; attempt += 1) {
    try {
      const events = await streamPhase(prepared, phase, deps, signal);
      if (events.some((event) => ["phase_complete", "complete", "error", "cancelled"].includes(event.event))) {
        return events;
      }
    } catch (error) {
      if (signal?.aborted || error instanceof V2ExecutionHttpError) throw error;
      if (attempt === maxReconnects) throw error;
    }
    if (attempt === maxReconnects) break;
    await wait(deps.reconnectDelayMs?.(attempt) ?? 250 * 2 ** attempt, signal);
  }
  throw new Error("실행 phase 재연결 횟수를 초과했습니다.");
}

async function streamPhase(
  prepared: PreparedExecution,
  phase: "core" | "finalize",
  deps: V2ExecutionDependencies,
  signal?: AbortSignal,
): Promise<SseEvent[]> {
  const response = await deps.fetch(
    `${deps.apiUrl}/v2/question-executions/${encodeURIComponent(prepared.execution_id)}/${phase}`,
    {
      method: "POST",
      headers: phaseHeaders(deps.headers, prepared.execution_capability),
      signal,
    },
  );
  if (!response.ok) {
    throw new V2ExecutionHttpError(response.status, await response.json().catch(() => null));
  }
  if (!response.body) throw new Error("SSE 응답 본문이 없습니다.");
  const events: SseEvent[] = [];
  for await (const event of parseSse(response.body)) events.push(event);
  return events;
}

async function cancelExecution(prepared: PreparedExecution, deps: V2ExecutionDependencies): Promise<void> {
  try {
    await deps.fetch(`${deps.apiUrl}/v2/question-executions/${encodeURIComponent(prepared.execution_id)}`, {
      method: "DELETE",
      headers: phaseHeaders(deps.headers, prepared.execution_capability),
    });
  } catch {
    // Cancellation is best effort; the local AbortSignal still stops UI work.
  }
}

function phaseHeaders(headers: HeadersInit, capability: string | undefined): HeadersInit {
  return capability ? { ...headers, "X-Execution-Capability": capability } : headers;
}

async function json<T>(response: Promise<Response>): Promise<T> {
  const resolved = await response;
  if (!resolved.ok) {
    throw new V2ExecutionHttpError(resolved.status, await resolved.json().catch(() => null));
  }
  return resolved.json() as Promise<T>;
}

async function* parseSse(body: ReadableStream<Uint8Array>): AsyncGenerator<SseEvent> {
  const reader = body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  try {
    for (;;) {
      const chunk = await reader.read();
      if (chunk.done) break;
      buffer += decoder.decode(chunk.value, { stream: true });
      const frames = buffer.split(/\r?\n\r?\n/);
      buffer = frames.pop() ?? "";
      for (const frame of frames) {
        const event = parseFrame(frame);
        if (event) yield event;
      }
    }
    buffer += decoder.decode();
    const finalEvent = parseFrame(buffer);
    if (finalEvent) yield finalEvent;
  } finally {
    reader.releaseLock();
  }
}

function parseFrame(frame: string): SseEvent | null {
  const lines = frame.split(/\r?\n/);
  const event = lines.find((line) => line.startsWith("event:"))?.slice(6).trim();
  const data = lines.find((line) => line.startsWith("data:"))?.slice(5).trim();
  if (!event || !data) return null;
  try {
    const parsed: unknown = JSON.parse(data);
    return isRecord(parsed) ? { event, data: parsed } : null;
  } catch {
    return null;
  }
}

function isPreparedExecution(value: unknown): value is PreparedExecution {
  return isRecord(value)
    && typeof value.execution_id === "string"
    && typeof value.next_action === "string"
    && KNOWN_ACTIONS.has(value.next_action as V2NextAction)
    && (value.execution_capability === undefined || typeof value.execution_capability === "string");
}

function isQuestionResponse(value: unknown): value is QuestionResponse {
  return isRecord(value)
    && typeof value.summary === "string"
    && typeof value.scope === "string"
    && Array.isArray(value.sections)
    && Array.isArray(value.checklist)
    && Array.isArray(value.citations)
    && Array.isArray(value.limitations);
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function wait(delayMs: number, signal?: AbortSignal): Promise<void> {
  return new Promise((resolve, reject) => {
    const timeout = setTimeout(resolve, delayMs);
    signal?.addEventListener("abort", () => {
      clearTimeout(timeout);
      reject(new DOMException("Aborted", "AbortError"));
    }, { once: true });
  });
}
