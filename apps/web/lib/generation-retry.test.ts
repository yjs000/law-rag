import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  askQuestionWithRetry,
  GENERATION_ATTEMPT_TIMEOUT_MS,
  GENERATION_MAX_ATTEMPTS,
} from "./generation-retry";
import type { QuestionInput, QuestionResponse } from "./contracts";

const response: QuestionResponse = {
  mode: "ai",
  summary: "요약",
  scope: "범위",
  sections: [],
  checklist: [],
  citations: [],
  limitations: [],
};

const input: QuestionInput = {
  client_request_id: "attempt-1",
  question: "질문",
  as_of_date: "2026-08-08",
  project_stage: "planning",
};

function abortError(): DOMException {
  return new DOMException("Aborted", "AbortError");
}

beforeEach(() => {
  vi.useFakeTimers();
});

afterEach(() => {
  vi.useRealTimers();
});

describe("askQuestionWithRetry", () => {
  it("returns the response immediately when the first attempt succeeds", async () => {
    const ask = vi.fn().mockResolvedValue(response);
    const cancel = vi.fn().mockResolvedValue({ cancelled: true });
    const outerSignal = new AbortController().signal;

    const result = await askQuestionWithRetry(input, {
      ask,
      cancel,
      nextClientRequestId: () => "attempt-2",
      outerSignal,
    });

    expect(result).toBe(response);
    expect(ask).toHaveBeenCalledTimes(1);
    expect(cancel).not.toHaveBeenCalled();
  });

  it("cancels and retries with a fresh client_request_id after a per-attempt timeout", async () => {
    let calls = 0;
    const ask = vi.fn().mockImplementation((_input: QuestionInput, signal: AbortSignal) => {
      calls += 1;
      return new Promise<QuestionResponse>((resolve, reject) => {
        if (calls === 1) {
          signal.addEventListener("abort", () => reject(abortError()));
        } else {
          resolve(response);
        }
      });
    });
    const cancel = vi.fn().mockResolvedValue({ cancelled: true });
    const outerSignal = new AbortController().signal;

    const promise = askQuestionWithRetry(input, {
      ask,
      cancel,
      nextClientRequestId: () => "attempt-2",
      outerSignal,
    });

    await vi.advanceTimersByTimeAsync(GENERATION_ATTEMPT_TIMEOUT_MS);
    const result = await promise;

    expect(result).toBe(response);
    expect(ask).toHaveBeenCalledTimes(2);
    expect(cancel).toHaveBeenCalledWith("attempt-1");
    expect(ask.mock.calls[1][0].client_request_id).toBe("attempt-2");
  });

  it("gives up after the max attempt count and throws the timeout error", async () => {
    const ask = vi.fn().mockImplementation((_input: QuestionInput, signal: AbortSignal) => {
      return new Promise<QuestionResponse>((_resolve, reject) => {
        signal.addEventListener("abort", () => reject(abortError()));
      });
    });
    const cancel = vi.fn().mockResolvedValue({ cancelled: true });
    const outerSignal = new AbortController().signal;
    let ids = 1;

    const promise = askQuestionWithRetry(input, {
      ask,
      cancel,
      nextClientRequestId: () => `attempt-${++ids}`,
      outerSignal,
    });
    promise.catch(() => undefined); // keep unhandled-rejection warnings quiet while timers advance

    for (let i = 0; i < GENERATION_MAX_ATTEMPTS; i += 1) {
      await vi.advanceTimersByTimeAsync(GENERATION_ATTEMPT_TIMEOUT_MS);
    }

    await expect(promise).rejects.toMatchObject({ name: "AbortError" });
    expect(ask).toHaveBeenCalledTimes(GENERATION_MAX_ATTEMPTS);
    expect(cancel).toHaveBeenCalledTimes(GENERATION_MAX_ATTEMPTS - 1);
  });

  it("does not retry a real server error - only timeouts are retried", async () => {
    const ask = vi.fn().mockRejectedValue(new Error("오늘의 계정 사용 한도를 초과했습니다."));
    const cancel = vi.fn();
    const outerSignal = new AbortController().signal;

    await expect(
      askQuestionWithRetry(input, { ask, cancel, nextClientRequestId: () => "attempt-2", outerSignal }),
    ).rejects.toThrow("오늘의 계정 사용 한도를 초과했습니다.");
    expect(ask).toHaveBeenCalledTimes(1);
    expect(cancel).not.toHaveBeenCalled();
  });

  it("propagates a user-initiated cancel (outer abort) without retrying", async () => {
    const controller = new AbortController();
    const ask = vi.fn().mockImplementation((_input: QuestionInput, signal: AbortSignal) => {
      return new Promise<QuestionResponse>((_resolve, reject) => {
        signal.addEventListener("abort", () => reject(abortError()));
      });
    });
    const cancel = vi.fn();

    const promise = askQuestionWithRetry(input, {
      ask,
      cancel,
      nextClientRequestId: () => "attempt-2",
      outerSignal: controller.signal,
    });
    controller.abort();

    await expect(promise).rejects.toMatchObject({ name: "AbortError" });
    expect(ask).toHaveBeenCalledTimes(1);
    expect(cancel).not.toHaveBeenCalled();
  });

  it("reports each new attempt id via onAttemptChange as it happens", async () => {
    let calls = 0;
    const ask = vi.fn().mockImplementation((_input: QuestionInput, signal: AbortSignal) => {
      calls += 1;
      return new Promise<QuestionResponse>((resolve, reject) => {
        if (calls === 1) signal.addEventListener("abort", () => reject(abortError()));
        else resolve(response);
      });
    });
    const onAttemptChange = vi.fn();

    const promise = askQuestionWithRetry(input, {
      ask,
      cancel: vi.fn().mockResolvedValue({ cancelled: true }),
      nextClientRequestId: () => "attempt-2",
      outerSignal: new AbortController().signal,
      onAttemptChange,
    });
    await vi.advanceTimersByTimeAsync(GENERATION_ATTEMPT_TIMEOUT_MS);
    await promise;

    expect(onAttemptChange.mock.calls.map((call) => call[0])).toEqual(["attempt-1", "attempt-2"]);
  });
});
