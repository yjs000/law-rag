import { ApiError } from "./api-client";
import type { QuestionInput, QuestionResponse } from "./contracts";

/**
 * Coordinate Web-side retries with the API's own request budget. The API
 * bounds each request to a 52s soft deadline (see RequestBudget), and
 * Vercel's serverless functions hard-cap execution at 60s. We bound each
 * attempt to 55s so a client-side timeout only ever fires after the API has
 * already given up, while still leaving headroom before the platform kills
 * the function outright. Margin chain: API 52s < Web 55s < Vercel 60s.
 */
export const GENERATION_ATTEMPT_TIMEOUT_MS = 55_000;
export const GENERATION_MAX_ATTEMPTS = 3;
export const GENERATION_OVERALL_TIMEOUT_MS = 170_000;
export const GENERATION_CANCEL_TIMEOUT_MS = 1_000;

export type AskQuestionWithRetryDeps = {
  ask: (input: QuestionInput, signal: AbortSignal) => Promise<QuestionResponse>;
  cancel: (clientRequestId: string) => Promise<unknown>;
  nextClientRequestId: () => string;
  outerSignal: AbortSignal;
  /** Called with the client_request_id of each attempt as it starts, including the first. */
  onAttemptChange?: (clientRequestId: string) => void;
  maxAttempts?: number;
  attemptTimeoutMs?: number;
  overallTimeoutMs?: number;
  cancelTimeoutMs?: number;
};

function isAbortError(error: unknown): error is DOMException {
  return error instanceof DOMException && error.name === "AbortError";
}

function isRetryableHttpError(error: unknown): error is ApiError {
  return error instanceof ApiError
    && error.code !== "system_busy"
    && [502, 503, 504].includes(error.status);
}

function isRetryableFallback(response: QuestionResponse): boolean {
  return response.mode === "search_only" && response.fallback_reason === "generation_error";
}

/**
 * Best-effort cancellation of an abandoned (timed-out) attempt. Races
 * `cancel()` against a bounded timer so a hung or slow cancel endpoint can
 * never delay - let alone fail - the next attempt.
 */
async function cancelWithBound(
  cancel: (clientRequestId: string) => Promise<unknown>,
  clientRequestId: string,
  cancelTimeoutMs: number,
): Promise<void> {
  await Promise.race([
    cancel(clientRequestId).then(
      () => undefined,
      () => undefined,
    ),
    new Promise<void>((resolve) => setTimeout(resolve, cancelTimeoutMs)),
  ]);
}

export async function askQuestionWithRetry(
  input: QuestionInput,
  deps: AskQuestionWithRetryDeps,
): Promise<QuestionResponse> {
  const maxAttempts = deps.maxAttempts ?? GENERATION_MAX_ATTEMPTS;
  const attemptTimeoutMs = deps.attemptTimeoutMs ?? GENERATION_ATTEMPT_TIMEOUT_MS;
  const overallTimeoutMs = deps.overallTimeoutMs ?? GENERATION_OVERALL_TIMEOUT_MS;
  const cancelTimeoutMs = deps.cancelTimeoutMs ?? GENERATION_CANCEL_TIMEOUT_MS;

  const startedAt = Date.now();
  let currentInput = input;
  let latestFallback: QuestionResponse | undefined;
  let lastError: unknown;

  for (let attempt = 1; attempt <= maxAttempts; attempt += 1) {
    if (deps.outerSignal.aborted) throw new DOMException("Aborted", "AbortError");

    const remainingOverallMs = overallTimeoutMs - (Date.now() - startedAt);
    if (remainingOverallMs <= 0) break;

    deps.onAttemptChange?.(currentInput.client_request_id ?? "");

    const attemptController = new AbortController();
    const forwardAbort = () => attemptController.abort();
    deps.outerSignal.addEventListener("abort", forwardAbort);
    const timeoutId = setTimeout(
      () => attemptController.abort(),
      Math.min(attemptTimeoutMs, remainingOverallMs),
    );

    try {
      const response = await deps.ask(currentInput, attemptController.signal);

      if (!isRetryableFallback(response)) return response;

      latestFallback = response;
      const moreAttemptsAvailable = attempt < maxAttempts
        && overallTimeoutMs - (Date.now() - startedAt) > 0;
      if (moreAttemptsAvailable) {
        // The attempt already completed (it returned a response), so there is
        // nothing in flight to cancel - only a fresh client_request_id is needed.
        currentInput = { ...currentInput, client_request_id: deps.nextClientRequestId() };
      }
    } catch (cause) {
      if (deps.outerSignal.aborted) throw cause;

      const retryable = isAbortError(cause) || isRetryableHttpError(cause);
      if (!retryable) {
        if (latestFallback) return latestFallback;
        throw cause;
      }
      lastError = cause;

      const moreAttemptsAvailable = attempt < maxAttempts
        && overallTimeoutMs - (Date.now() - startedAt) > 0;
      if (moreAttemptsAvailable) {
        if (isAbortError(cause)) {
          // Our own attempt timeout fired: the request may still be running
          // server-side, so ask the server to stop it (best-effort, bounded).
          const finishedId = currentInput.client_request_id;
          if (finishedId) await cancelWithBound(deps.cancel, finishedId, cancelTimeoutMs);
        }
        currentInput = { ...currentInput, client_request_id: deps.nextClientRequestId() };
      }
    } finally {
      clearTimeout(timeoutId);
      deps.outerSignal.removeEventListener("abort", forwardAbort);
    }
  }

  if (latestFallback) return latestFallback;
  throw lastError;
}
