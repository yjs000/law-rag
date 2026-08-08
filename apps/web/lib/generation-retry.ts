import type { QuestionInput, QuestionResponse } from "./contracts";

/**
 * Vercel's serverless functions hard-cap execution at 60s. A single held-open
 * request can lose an entire attempt to that cutoff with no chance to retry
 * (see the 2026-08-08 504 in production). Instead we bound each attempt to
 * 59s client-side, cancel it, and immediately issue a fresh request - each
 * new request gets its own 60s budget on the server.
 */
export const GENERATION_ATTEMPT_TIMEOUT_MS = 59_000;
export const GENERATION_MAX_ATTEMPTS = 3;

export type AskQuestionWithRetryDeps = {
  ask: (input: QuestionInput, signal: AbortSignal) => Promise<QuestionResponse>;
  cancel: (clientRequestId: string) => Promise<unknown>;
  nextClientRequestId: () => string;
  outerSignal: AbortSignal;
  /** Called with the client_request_id of each attempt as it starts, including the first. */
  onAttemptChange?: (clientRequestId: string) => void;
  maxAttempts?: number;
  attemptTimeoutMs?: number;
};

function isAbortError(error: unknown): error is DOMException {
  return error instanceof DOMException && error.name === "AbortError";
}

export async function askQuestionWithRetry(
  input: QuestionInput,
  deps: AskQuestionWithRetryDeps,
): Promise<QuestionResponse> {
  const maxAttempts = deps.maxAttempts ?? GENERATION_MAX_ATTEMPTS;
  const attemptTimeoutMs = deps.attemptTimeoutMs ?? GENERATION_ATTEMPT_TIMEOUT_MS;
  let currentInput = input;
  let lastTimeoutError: unknown;

  for (let attempt = 1; attempt <= maxAttempts; attempt += 1) {
    if (deps.outerSignal.aborted) throw new DOMException("Aborted", "AbortError");
    deps.onAttemptChange?.(currentInput.client_request_id ?? "");

    const attemptController = new AbortController();
    const forwardAbort = () => attemptController.abort();
    deps.outerSignal.addEventListener("abort", forwardAbort);
    const timeoutId = setTimeout(() => attemptController.abort(), attemptTimeoutMs);

    try {
      return await deps.ask(currentInput, attemptController.signal);
    } catch (cause) {
      if (deps.outerSignal.aborted || !isAbortError(cause)) throw cause;
      lastTimeoutError = cause;
      if (attempt < maxAttempts) {
        const finishedId = currentInput.client_request_id;
        if (finishedId) await deps.cancel(finishedId).catch(() => undefined);
        currentInput = { ...currentInput, client_request_id: deps.nextClientRequestId() };
      }
    } finally {
      clearTimeout(timeoutId);
      deps.outerSignal.removeEventListener("abort", forwardAbort);
    }
  }
  throw lastTimeoutError;
}
